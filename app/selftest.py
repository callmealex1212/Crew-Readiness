"""
"Health of the monitor" (task R1): the software checks itself and says, check by check, what passed and why.

Used by GET /api/selftest, the /status page and `flask selftest`. Each check returns {id, name, ok, detail}.

What it does NOT show: anything about a crew member; that the hardware, power or storage medium is sound; behaviour under
radiation; that scoring is right for real people (it checks one fixed, hand-worked example only); or that the network is
physically absent (it checks that no page asks for another host).
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import current_app

from .baseline import compute_baseline
from .db import get_db
from .features import FEATURE_NAMES
from .readiness import PAUSE_MODEL
from .scoring import score_session

TASK_TYPE = "docking_checklist_v1"
EARLIEST_SANE = datetime(2024, 1, 1, tzinfo=timezone.utc)
FUTURE_SLACK = timedelta(days=1)

# ---- the fixed scoring fixture, worked out by hand from app/scoring.py (do NOT copy it from a run) ----
# Five identical baseline sessions, so every spread falls back to its floor:
#   typing rhythm   usual 100 ms, today 120 ms, floor 10 ms  -> deviation 2.0
#   typing spread   usual  50 ms, today  60 ms, floor 10 ms  -> deviation 1.0   => typing group 1.5
#   pauses          0 and 0 (count and time)                 -> 0               => pauses group 0
#   checklist       usual 1000 ms, today 1300 ms, floor 150  -> deviation 2.0   => checklist group 2.0
#   score = 0.4 * 1.5 + 0.3 * 0 + 0.3 * 2.0 = 1.2  -> YELLOW (1.0 <= score < 2.0). Same under both pause models.
FIXTURE_BASELINE = dict(keystroke_count=120, iki_median_ms=100.0, iki_iqr_ms=50.0, pause_count=0, pause_total_ms=0.0,
                        checklist_response_median_ms=1000.0, task_duration_ms=20000.0, correction_count=0, retry_count=0)
FIXTURE_TODAY = dict(FIXTURE_BASELINE, iki_median_ms=120.0, iki_iqr_ms=60.0, checklist_response_median_ms=1300.0)
FIXTURE_EXPECTED_SCORE = 1.2
FIXTURE_EXPECTED_BAND = "YELLOW"

# the same rule as tests/test_api.py::test_no_page_calls_out_to_the_network
EXTERNAL_LOAD = re.compile(r'<(?:script|link|img)[^>]+(?:src|href)=["\'](https?://[^"\']+)')
JS_EXTERNAL = re.compile(r'(?:fetch|import)\s*\(?\s*["\'`](https?://[^"\'`]+)')

DOES_NOT_SHOW = ("It says nothing about any crew member. It does not test the hardware, power or storage medium, behaviour "
                 "under radiation, or whether scoring is right for real people: the scoring check is one fixed example worked "
                 "out by hand. 'No outside network' means no page or script asks for another host, not that a network is absent.")


def external_loads(html: str) -> list[str]:
    """Addresses of scripts, stylesheets or images a page would load from another host."""
    return EXTERNAL_LOAD.findall(html)


def _check(cid: str, name: str, fn) -> dict:
    try:
        ok, detail = fn()
    except Exception as e:  # a check that crashes is a failed check, with its reason
        ok, detail = False, f"the check itself failed: {type(e).__name__}: {e}"
    return {"id": cid, "name": name, "ok": bool(ok), "detail": detail}


def check_database() -> tuple[bool, str]:
    db = get_db()
    db.execute("SAVEPOINT selftest")
    try:
        db.execute("INSERT INTO profiles (id, display_name, mission_role, kind, created_at) VALUES (?, ?, ?, 'demo', ?)",
                   ("selftest-probe", "Self-test probe", "none", "2024-01-01T00:00:00Z"))
        row = db.execute("SELECT display_name FROM profiles WHERE id = 'selftest-probe'").fetchone()
    finally:
        db.execute("ROLLBACK TO SAVEPOINT selftest")
        db.execute("RELEASE SAVEPOINT selftest")
    gone = db.execute("SELECT 1 FROM profiles WHERE id = 'selftest-probe'").fetchone() is None
    if row is None or row[0] != "Self-test probe":
        return False, "a row written to the database could not be read back"
    if not gone:
        return False, "the test row was not rolled back"
    return True, "opened; a test row was written, read back and rolled back (nothing kept)"


def check_scoring() -> tuple[bool, str]:
    base = compute_baseline([dict(FIXTURE_BASELINE, data_quality="ok") for _ in range(5)], FEATURE_NAMES, TASK_TYPE)
    view = score_session(FIXTURE_TODAY, base, "ok", PAUSE_MODEL)
    got = view.score
    if got is None or abs(got - FIXTURE_EXPECTED_SCORE) > 1e-9 or view.band != FIXTURE_EXPECTED_BAND:
        return False, f"fixed example scored {got} {view.band}; expected {FIXTURE_EXPECTED_SCORE} {FIXTURE_EXPECTED_BAND}"
    return True, f"fixed example scores {FIXTURE_EXPECTED_SCORE} {FIXTURE_EXPECTED_BAND}, as worked out by hand (pause model: {PAUSE_MODEL})"


def check_clock(now: datetime | None = None) -> tuple[bool, str]:
    now = now or datetime.now(timezone.utc)
    if now < EARLIEST_SANE:
        return False, f"clock reads {now:%Y-%m-%d %H:%M} UTC, before 2024"
    row = get_db().execute("SELECT MAX(created_at) FROM sessions").fetchone()
    latest = row[0] if row else None
    if latest:
        latest_dt = datetime.strptime(latest, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if latest_dt > now + FUTURE_SLACK:
            return False, (f"clock reads {now:%Y-%m-%d %H:%M} UTC, but a stored session is dated {latest_dt:%Y-%m-%d %H:%M}: "
                           "the clock may have jumped backwards")
        return True, f"{now:%Y-%m-%d %H:%M} UTC; after 2024 and not behind the latest stored session ({latest_dt:%Y-%m-%d %H:%M})"
    return True, f"{now:%Y-%m-%d %H:%M} UTC; after 2024 (no sessions stored to compare with)"


def check_no_outside_network(app_root: Path | None = None) -> tuple[bool, str]:
    root = app_root or Path(current_app.root_path)
    found = []
    for f in sorted((root / "templates").glob("*.html")):
        found += [f"{f.name}: {u}" for u in external_loads(f.read_text(encoding="utf-8"))]
    for f in sorted((root / "static" / "js").glob("*.js")):
        found += [f"{f.name}: {u}" for u in JS_EXTERNAL.findall(f.read_text(encoding="utf-8"))]
    if found:
        return False, "loads from another host: " + "; ".join(found[:5])
    return True, "no page template or script asks for another host"


def check_version() -> tuple[bool, str]:
    v = current_app.config.get("APP_VERSION")
    return bool(v), f"version {v}" if v else "no version configured"


def run_selftest(now: datetime | None = None) -> dict:
    checks = [
        _check("database", "Database opens, writes and reads", check_database),
        _check("scoring", "Scoring gives the known answer", check_scoring),
        _check("clock", "System clock is sane", lambda: check_clock(now)),
        _check("network", "No outside network", check_no_outside_network),
        _check("version", "App version", check_version),
    ]
    return {
        "ok": all(c["ok"] for c in checks),
        "checked_at": (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "version": current_app.config.get("APP_VERSION"),
        "checks": checks,
        "does_not_show": DOES_NOT_SHOW,
    }
