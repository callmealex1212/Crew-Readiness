"""
Reliability runs (task R2). Called by `python -m ml.export_reliability`, which writes app/reliability_data.json.

  fuzz(...)        malformed and hostile payloads to POST /api/sessions and POST /api/attention, in-process (Flask test client,
                   throwaway database). A "crash" is an HTTP 500 or an exception escaping the app. Expected: 0.
  soak(...)        simulated crew (ml/synth.py), many days, several sessions a day, stored and scored exactly as POST
                   /api/sessions does (store.insert_session, then readiness_for_profile). Times each scoring call, and records
                   the database size and the process's peak memory.
  clock_jump(...)  the same person's sessions stored once with times moving forward and once with times jumping backwards;
                   scoring must not crash and must give the same answers (order comes from the stored order, not the clock).

What it does NOT show: behaviour on flight hardware, under radiation, with a failing disk or full storage, under concurrent users,
or on real crew data. Timings depend on the machine it ran on (recorded in the output).
"""
from __future__ import annotations

import json
import math
import random
import resource
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app, store  # noqa: E402
from app.db import get_db, init_db  # noqa: E402
from app.features import FEATURE_NAMES  # noqa: E402
from app.readiness import readiness_for_profile  # noqa: E402
from app.seed import seed_demo  # noqa: E402

TASK = "docking_checklist_v1"
GOOD = {"keystroke_count": 125, "iki_median_ms": 190.0, "iki_iqr_ms": 75.0, "pause_count": 1, "pause_total_ms": 2600.0,
        "checklist_response_median_ms": 1500.0, "task_duration_ms": 45000.0, "correction_count": 2, "retry_count": 0}
GOOD_ATTENTION = {"profile_id": "plt-okafor", "trials": 10, "median_rt_ms": 310.0, "premature_count": 1, "miss_count": 0}
HOSTILE_VALUES = [
    None, True, False, "", "190", "CORRIDOR CLEAR", "x" * 100_000, [], [1, 2], {}, {"a": 1}, {"$gt": 0},
    float("nan"), float("inf"), float("-inf"), -1, -1e308, 0, 1e308, 10**30, -(10**30), 2**63, 1e-320, 0.5, "NaN",
    "<script>alert(1)</script>", "'; DROP TABLE sessions; --", "\u0000", "\ud800",
]


def _app(tmp: Path, name: str, seed: bool = True):
    app = create_app({"TESTING": True, "DATABASE": str(tmp / name), "AUTO_SEED": False})
    with app.app_context():
        init_db()
        if seed:
            seed_demo(get_db())
    return app


# ------------------------------------------------------------------ (a) fault injection

def _session_cases(rng: random.Random):
    """Yield (category, raw JSON text) for a hostile /api/sessions body."""
    kind = rng.choice(["wrong_value", "missing_field", "extra_field", "extra_top", "nested", "not_object", "bad_json",
                       "huge_string", "typed_text", "bad_profile", "bad_task"])
    body = {"profile_id": "plt-okafor", "task_type": TASK, "features": dict(GOOD)}
    if kind == "wrong_value":
        body["features"][rng.choice(FEATURE_NAMES)] = rng.choice(HOSTILE_VALUES)
    elif kind == "missing_field":
        if rng.random() < 0.5:
            del body["features"][rng.choice(FEATURE_NAMES)]
        else:
            del body[rng.choice(list(body))]
    elif kind == "extra_field":
        body["features"][rng.choice(["typed_text", "keys", "keystroke_timeline", "x"])] = rng.choice(HOSTILE_VALUES)
    elif kind == "extra_top":
        body[rng.choice(["typed_text", "session_id", "admin", "__proto__"])] = rng.choice(HOSTILE_VALUES)
    elif kind == "nested":
        body["features"] = rng.choice([[GOOD], {"features": GOOD}, "features", 7, None])
    elif kind == "not_object":
        return kind, json.dumps(rng.choice([[], [body], "body", 42, None, [{"a": 1}], [["x"]]]))
    elif kind == "bad_json":
        return kind, rng.choice(['{"profile_id": ', "{", "nul", "[1,", '{"a":1}}', "\x00\x01", "{'single': 'quotes'}"])
    elif kind == "huge_string":
        body[rng.choice(["profile_id", "task_type"])] = "x" * rng.choice([1000, 100_000, 1_000_000])
    elif kind == "typed_text":
        body["features"][rng.choice(FEATURE_NAMES)] = rng.choice(["CORRIDOR CLEAR", "TARGET LOCK", "Approach checklist complete"])
    elif kind == "bad_profile":
        body["profile_id"] = rng.choice(HOSTILE_VALUES)
    elif kind == "bad_task":
        body["task_type"] = rng.choice(HOSTILE_VALUES)
    return kind, json.dumps(body, allow_nan=True)


def _attention_cases(rng: random.Random):
    kind = rng.choice(["wrong_value", "missing_field", "extra_field", "not_object", "bad_json", "huge_string", "typed_text"])
    body = dict(GOOD_ATTENTION)
    if kind == "wrong_value":
        body[rng.choice(list(body))] = rng.choice(HOSTILE_VALUES)
    elif kind == "missing_field":
        del body[rng.choice(list(body))]
    elif kind == "extra_field":
        body[rng.choice(["typed_text", "trial_times", "x"])] = rng.choice(HOSTILE_VALUES)
    elif kind == "not_object":
        return kind, json.dumps(rng.choice([[], [body], "body", 42, None, [{"a": 1}], [["x"]], ["profile_id"]]))
    elif kind == "bad_json":
        return kind, rng.choice(['{"trials": ', "{", "nul", "[1,", "\x00"])
    elif kind == "huge_string":
        body["profile_id"] = "x" * rng.choice([1000, 100_000, 1_000_000])
    elif kind == "typed_text":
        body[rng.choice(["median_rt_ms", "trials", "miss_count"])] = "CORRIDOR CLEAR"
    return kind, json.dumps(body, allow_nan=True)


def fuzz(n: int = 1000, seed: int = 20261115) -> dict:
    rng = random.Random(seed)
    with tempfile.TemporaryDirectory() as tmp:
        app = _app(Path(tmp), "fuzz.sqlite3")
        client = app.test_client()
        statuses: dict[str, int] = {}
        by_kind: dict[str, int] = {}
        crashes = []
        stored_before = _count_rows(app)
        for i in range(n):
            endpoint = "/api/sessions" if i % 2 == 0 else "/api/attention"
            kind, raw = (_session_cases if i % 2 == 0 else _attention_cases)(rng)
            key = f"{endpoint} {kind}"
            by_kind[key] = by_kind.get(key, 0) + 1
            try:
                r = client.post(endpoint, data=raw.encode("utf-8", "surrogatepass"), content_type="application/json")
                code = r.status_code
            except Exception as e:  # an exception escaping the app is a crash
                code = f"exception {type(e).__name__}"
            statuses[str(code)] = statuses.get(str(code), 0) + 1
            if code == 500 or isinstance(code, str):
                crashes.append({"endpoint": endpoint, "kind": kind, "result": str(code)})
        stored_after = _count_rows(app)
    return {
        "payloads": n, "seed": seed, "crashes": len(crashes), "crash_examples": crashes[:10],
        "status_counts": dict(sorted(statuses.items())), "by_kind": dict(sorted(by_kind.items())),
        "rows_added": {t: stored_after[t] - stored_before[t] for t in stored_after},
    }


def _count_rows(app) -> dict:
    with app.app_context():
        return {t: get_db().execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("sessions", "attention_results")}


# ------------------------------------------------------------------ (b) long-mission soak

def _iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def soak(people: int = 6, days: int = 700, per_day: int = 3, seed: int = 7) -> dict:
    from ml.synth import simulate_person   # synthetic people only

    rng = np.random.default_rng(seed)
    n = days * per_day
    crew = {f"soak-{i + 1:02d}": simulate_person(rng, n)[0] for i in range(people)}
    start = datetime(2027, 1, 1, 6, 0, tzinfo=timezone.utc)
    times = []
    with tempfile.TemporaryDirectory() as tmp:
        app = _app(Path(tmp), "soak.sqlite3", seed=False)
        db_path = Path(app.config["DATABASE"])
        with app.app_context():
            db = get_db()
            for pid in crew:
                store.insert_profile(db, pid, pid, "Simulated", kind="demo")
            db.commit()
            t0 = time.perf_counter()
            for k in range(n):                                  # session k of every person, in time order
                when = start + timedelta(days=k // per_day, hours=8 * (k % per_day))
                for pid, sessions in crew.items():
                    s = sessions[k]
                    store.insert_session(db, profile_id=pid, task_type=TASK, features={f: s[f] for f in FEATURE_NAMES},
                                         source="synthetic", data_quality="ok", quality_notes=None, created_at=_iso(when))
                    db.commit()
                    c0 = time.perf_counter()
                    readiness_for_profile(db, store.get_profile(db, pid), TASK)   # what POST /api/sessions does next
                    times.append((time.perf_counter() - c0) * 1000)
            wall = time.perf_counter() - t0
            stored = db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        size = db_path.stat().st_size
    a = np.array(times)
    return {
        "people": people, "days": days, "sessions_per_day": per_day, "sessions_stored": int(stored), "seed": seed,
        "scoring_ms": {"median": round(float(np.median(a)), 2), "p95": round(float(np.percentile(a, 95)), 2),
                       "max": round(float(a.max()), 2), "calls": int(a.size)},
        "scoring_ms_first_100_median": round(float(np.median(a[:100])), 2),
        "scoring_ms_last_100_median": round(float(np.median(a[-100:])), 2),
        "database_bytes": int(size), "wall_seconds": round(wall, 1),
        "peak_memory_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),   # Linux reports KiB
    }


# ------------------------------------------------------------------ (c) clock jumping backwards

def clock_jump(sessions: int = 40, jump_from: int = 25, jump_days: int = 30, seed: int = 3) -> dict:
    from ml.synth import simulate_person

    person = simulate_person(np.random.default_rng(seed), sessions)[0]
    start = datetime(2027, 1, 1, 6, 0, tzinfo=timezone.utc)
    forward = [start + timedelta(hours=8 * i) for i in range(sessions)]
    backward = [t - timedelta(days=jump_days) if i >= jump_from else t for i, t in enumerate(forward)]
    results, crashes = {}, 0
    with tempfile.TemporaryDirectory() as tmp:
        for label, stamps in (("forward", forward), ("backward", backward)):
            app = _app(Path(tmp), f"clock-{label}.sqlite3", seed=False)
            scores = []
            with app.app_context():
                db = get_db()
                store.insert_profile(db, "clock-01", "clock-01", "Simulated", kind="demo")
                for s, when in zip(person, stamps):
                    store.insert_session(db, profile_id="clock-01", task_type=TASK, features={f: s[f] for f in FEATURE_NAMES},
                                         source="synthetic", data_quality="ok", quality_notes=None, created_at=_iso(when))
                    db.commit()
                    try:
                        r = readiness_for_profile(db, store.get_profile(db, "clock-01"), TASK)["readiness"]
                        scores.append((r["status"], r["band"], None if r["score"] is None else round(r["score"], 9)))
                    except Exception:
                        crashes += 1
                        scores.append(("CRASH", None, None))
            results[label] = scores
    return {
        "sessions": sessions, "jump": f"from session {jump_from + 1} on, times are {jump_days} days EARLIER than the session before",
        "crashes": crashes, "same_answers_as_forward_clock": results["forward"] == results["backward"],
    }


if __name__ == "__main__":
    print(json.dumps({"fuzz": fuzz(200)}, indent=1)[:3000])
