"""
Synthetic demo data for FICTIONAL crew members.

Every row created here is stored with source='synthetic' and every profile
with kind='demo', so the UI can label it. Do not present these numbers as
measurements of real people.

Each person gets their own "personality" (some type faster, some pause
more). That is the whole point of a *personal* baseline: 220 ms between
keys can be normal for one person and a big change for another.

Demo states this produces (protected by tests/test_api.py):
  * cdr-vega   GREEN        — 14 normal sessions
  * plt-okafor YELLOW       — 14 normal sessions, then a seeded deviation
  * fe-sato    GREEN        — 14 normal sessions
  * ms-ibarra  CALIBRATING  — only 3 sessions so far
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np

from . import store
from .features import assess_quality
from .tasks import DEFAULT_TASK_TYPE

SEED = 42  # fixed, so every teammate's demo DB is identical

CREW = [
    ("cdr-vega",   "Cmdr. Lena Vega", "Commander"),
    ("plt-okafor", "Kai Okafor",      "Pilot"),
    ("fe-sato",    "Mira Sato",       "Flight Engineer"),
    ("ms-ibarra",  "Tomas Ibarra",    "Mission Specialist"),
]

# Personal typing "style": typical value and day-to-day variability.
STYLES = {
    "cdr-vega":   dict(iki=165, iki_sd=10, iqr=60,  iqr_sd=8,  pause_rate=0.6, resp=1300, resp_sd=150),
    "plt-okafor": dict(iki=190, iki_sd=12, iqr=75,  iqr_sd=9,  pause_rate=0.8, resp=1500, resp_sd=170),
    "fe-sato":    dict(iki=145, iki_sd=9,  iqr=50,  iqr_sd=6,  pause_rate=0.4, resp=1100, resp_sd=120),
    "ms-ibarra":  dict(iki=230, iki_sd=15, iqr=95,  iqr_sd=12, pause_rate=1.2, resp=1800, resp_sd=200),
}
SESSIONS_PER_PERSON = {"cdr-vega": 14, "plt-okafor": 14, "fe-sato": 14, "ms-ibarra": 3}

TASK_CHARS = 121       # characters in docking_checklist_v1 confirmations
TASK_ITEMS = 7


def _synth_features(rng: np.random.Generator, style: dict, *, slowdown: float = 1.0,
                    extra_pauses: int = 0, resp_factor: float = 1.0) -> dict:
    iki = max(40.0, rng.normal(style["iki"], style["iki_sd"]) * slowdown)
    iqr = max(5.0, rng.normal(style["iqr"], style["iqr_sd"]) * slowdown)
    pause_count = int(rng.poisson(style["pause_rate"])) + extra_pauses
    pause_total = float(sum(2000 + rng.exponential(1200) for _ in range(pause_count)))
    resp = max(300.0, rng.normal(style["resp"], style["resp_sd"]) * resp_factor)
    corrections = int(rng.poisson(2))
    retries = int(rng.poisson(0.2))
    keys = TASK_CHARS + 2 * corrections
    duration = keys * iki + pause_total + TASK_ITEMS * resp + rng.normal(4000, 500)
    return {
        "keystroke_count": keys,
        "iki_median_ms": round(iki, 1),
        "iki_iqr_ms": round(iqr, 1),
        "pause_count": pause_count,
        "pause_total_ms": round(pause_total, 1),
        "checklist_response_median_ms": round(resp, 1),
        "task_duration_ms": round(duration, 1),
        "correction_count": corrections,
        "retry_count": retries,
    }


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def seed_demo(db) -> None:
    """Insert fictional crew + synthetic sessions. Assumes an empty, initialised DB."""
    rng = np.random.default_rng(SEED)
    now = datetime.now(timezone.utc).replace(microsecond=0)

    for profile_id, name, role in CREW:
        store.insert_profile(db, profile_id, name, role, kind="demo")
        n = SESSIONS_PER_PERSON[profile_id]
        for i in range(n):
            # one session per simulated day, most recent last
            created = now - timedelta(days=n - i, hours=int(rng.integers(0, 4)))
            if profile_id == "ms-ibarra":
                created -= timedelta(days=2)      # illustrative: this crew member has not checked in for about three days (watchdog demo)
            features = _synth_features(rng, STYLES[profile_id])
            quality, notes = assess_quality(features)
            store.insert_session(
                db, profile_id=profile_id, task_type=DEFAULT_TASK_TYPE,
                features=features, source="synthetic", data_quality=quality,
                quality_notes="; ".join(notes) or None, created_at=_iso(created),
            )

    # ILLUSTRATIVE CASE for the demo story, not evidence: the primary pilot, this morning, is somewhat
    # slower, pauses more and responds slower than *their own* usual pattern. The size (15 % slower, two
    # extra pauses, 30 % slower responses) was CHOSEN so the case lands comfortably inside YELLOW (score
    # about 1.25, between the 1.0 YELLOW line and the 1.5 baseline-exclusion line). It shows what a flag
    # looks like. It says nothing about how well the model works: that is the benchmark (docs/ML_RESULTS.md).
    deviating = _synth_features(rng, STYLES["plt-okafor"], slowdown=1.15,
                                extra_pauses=2, resp_factor=1.30)
    quality, notes = assess_quality(deviating)
    store.insert_session(
        db, profile_id="plt-okafor", task_type=DEFAULT_TASK_TYPE, features=deviating,
        source="synthetic", data_quality=quality, quality_notes="; ".join(notes) or None,
        created_at=_iso(now - timedelta(hours=1)),
    )

    # Reaction-check history, so Responsiveness has an own-baseline to compare with. ILLUSTRATIVE and synthetic, like everything
    # here. The primary pilot's latest check is ~15 % slower than their own usual, matching their seeded typing story.
    rrng = np.random.default_rng(SEED + 1)             # its own generator: the draws above are untouched
    usual_rt = {"plt-okafor": 285.0, "cdr-vega": 265.0, "fe-sato": 310.0, "ms-ibarra": 295.0}
    n_checks = {"plt-okafor": 8, "cdr-vega": 8, "fe-sato": 8, "ms-ibarra": 3}
    for profile_id, base in usual_rt.items():
        n = n_checks[profile_id]
        for i in range(n):
            store.insert_attention_result(
                db, profile_id=profile_id, session_id=None, trials=10,
                median_rt_ms=round(float(rrng.normal(base, 0.05 * base)), 1), premature_count=int(rrng.integers(0, 2)),
                miss_count=0, created_at=_iso(now - timedelta(days=n - i + 1, hours=int(rrng.integers(0, 3)))))
    store.insert_attention_result(
        db, profile_id="plt-okafor", session_id=None, trials=10, median_rt_ms=round(usual_rt["plt-okafor"] * 1.15, 1),
        premature_count=0, miss_count=1, created_at=_iso(now - timedelta(hours=1)))
    db.commit()
