"""
Readiness service: glues storage (store.py) to the math (baseline.py, scoring.py).

The key rule: a session is ALWAYS compared to the sessions that came
BEFORE it. It never takes part in its own baseline, otherwise a strange
session would partly "explain itself away".
"""
from __future__ import annotations

import os

from . import responsiveness, store
from .baseline import EXCLUDE_FROM_BASELINE, compute_baseline, select_baseline_sessions
from .features import FEATURE_NAMES
from .scoring import insufficient_data_view, score_session
from .tasks import DEFAULT_TASK_TYPE

# How many of the most recent sessions the trend carries. The dashboard draws one line
# per session (the "stacked sessions" art), so this is also the number of lines.
TREND_POINTS = 14

# Which scoring model the product uses. "nb" = per-person count model for pauses (benchmark: docs/ML_RESULTS.md);
# "robust" = the original median/MAD z-score for every feature. Env override: CREW_PAUSE_MODEL.
PAUSE_MODEL = os.environ.get("CREW_PAUSE_MODEL", "nb")


def _session_summary(s: dict) -> dict:
    return {
        "id": s["id"],
        "created_at": s["created_at"],
        "source": s["source"],
        "data_quality": s["data_quality"],
        "quality_notes": s["quality_notes"],
        "features": {n: s[n] for n in FEATURE_NAMES},
    }


def _walk(history: list[dict], task_type: str) -> list[tuple]:
    """Score every session against the earlier sessions that count as "normal for this person".

    Returns [(view, baseline, excluded)] in the same order as `history`. A session scored at or above
    EXCLUDE_FROM_BASELINE is `excluded`: it does not shape the baseline for later sessions, otherwise a
    sustained change would be absorbed and stop being flagged (experiment: docs/ML_RESULTS.md). A person
    can accept a flagged run as the new normal; those sessions then carry `accepted_at`, count, and the baseline
    restarts from the start of that run (so fewer than MIN_BASELINE_SESSIONS of them means CALIBRATING, honestly).
    """
    pool: list[dict] = []
    out = []
    prev_accepted = False
    for s in history:
        accepted = bool(s.get("accepted_at"))
        if accepted and not prev_accepted:
            pool = []          # a human accepted a new normal: the baseline restarts from that run
        prev_accepted = accepted
        baseline = compute_baseline(select_baseline_sessions(pool), FEATURE_NAMES, task_type)
        view = score_session(s, baseline, s["data_quality"], PAUSE_MODEL)
        excluded = (view.status == "SCORED" and view.score >= EXCLUDE_FROM_BASELINE
                    and not s.get("accepted_at"))
        out.append((view, baseline, excluded))
        if not excluded:
            pool.append(s)
    return out


score_history = _walk      # public name: scores every session in a history exactly as the product does


def _pending_run(walked: list[tuple], history: list[dict]) -> list[int]:
    """Ids of the unbroken run of excluded sessions that ends at the latest session (may be empty)."""
    ids: list[int] = []
    for (_v, _b, excluded), s in zip(reversed(walked), reversed(history)):
        if not excluded:
            break
        ids.append(s["id"])
    return list(reversed(ids))


def accept_new_normal(db, profile: dict, task_type: str = DEFAULT_TASK_TYPE) -> list[int]:
    """A human accepts the latest flagged run as this person's new normal. Returns the session ids accepted."""
    history = store.list_sessions(db, profile["id"], task_type)
    ids = _pending_run(_walk(history, task_type), history)
    store.accept_sessions(db, ids)
    return ids


def readiness_for_profile(db, profile: dict, task_type: str = DEFAULT_TASK_TYPE,
                          with_trend: bool = True) -> dict:
    history = store.list_sessions(db, profile["id"], task_type)
    result: dict = {
        "profile": profile,
        "task_type": task_type,
        "latest_session": None,
        "readiness": insufficient_data_view().to_dict(),
        "baseline": None,
        "trend": [],
        "attention": store.latest_attention_result(db, profile["id"]),
        "responsiveness": responsiveness.assess(store.list_attention_results(db, profile["id"])),
        "baseline_review": None,
    }
    if not history:
        return result

    walked = _walk(history, task_type)
    view, baseline, _ = walked[-1]
    pending = _pending_run(walked, history)
    if pending:
        result["baseline_review"] = {
            "excluded_sessions": len(pending),
            "message": (f"The last {len(pending)} session{'s' if len(pending) != 1 else ''} differed so much from "
                        "this person's usual pattern that they are not used to learn what is normal. If this is a "
                        "genuine new normal (a new keyboard, practice, a changed routine), a reviewer can accept it."),
        }
    result["latest_session"] = _session_summary(history[-1])
    result["readiness"] = view.to_dict()
    result["baseline"] = baseline.to_dict()

    if with_trend:
        start = max(0, len(history) - TREND_POINTS)
        for i in range(start, len(history)):
            v, _b, excluded = walked[i]
            result["trend"].append({
                "session_id": history[i]["id"],
                "created_at": history[i]["created_at"],
                "source": history[i]["source"],
                "status": v.status,
                "band": v.band,
                "score": None if v.score is None else round(v.score, 2),
                "excluded_from_baseline": excluded,
                # Per-feature directional deviation that fed the score (0 = usual or faster,
                # capped at 4). None while CALIBRATING, because there is no baseline to
                # deviate from. The dashboard art draws exactly these numbers, nothing else.
                "deviations": (
                    {d.feature: round(d.deviation, 2) for d in v.deviations}
                    if v.status == "SCORED" else None
                ),
            })
    return result


def readiness_for_all(db, task_type: str = DEFAULT_TASK_TYPE) -> list[dict]:
    return [readiness_for_profile(db, p, task_type, with_trend=False)
            for p in store.list_profiles(db)]
