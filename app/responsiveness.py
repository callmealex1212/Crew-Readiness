"""
Responsiveness against a person's OWN earlier reaction checks (plan v3, H1).

The optional reaction check (10 trials) stores a median response time, early presses and misses. This module compares today's check
with the same person's earlier checks, in the same spirit as the typing baseline: robust centre and spread, never a population norm.

What it is: "is your response time today within your usual range?"  What it is not: a test of attention, alertness, consciousness,
fatigue or health. It is context for a human, it never changes the typing readiness band, and its cutoffs are illustrative and
NOT validated on real people (docs/ML_RESULTS.md has a simulated check only).
"""
from __future__ import annotations

import numpy as np

MIN_BASELINE_CHECKS = 5          # earlier valid checks needed before we say anything about "usual"
SLOWER_AT = 2.0                  # robust SDs above the person's own median: "slower than usual" (illustrative)
MUCH_SLOWER_AT = 3.5             # "much slower than usual" (illustrative)
SPREAD_FLOOR_FRACTION = 0.06     # the spread is never below 6 % of the median, so a very steady person is not over-flagged
SPREAD_FLOOR_MS = 15.0


def _valid(r: dict) -> bool:
    return r.get("median_rt_ms") is not None


def assess(history: list[dict]) -> dict:
    """`history`: this person's reaction checks, oldest first; the LAST one is "today". Each has median_rt_ms (or None),
    miss_count, premature_count, trials, created_at. Returns a plain-language view. Never raises on odd input."""
    if not history:
        return {"status": "NONE", "level": None, "summary": "No reaction check yet.", "reasons": [], "n_checks": 0}
    today, earlier = history[-1], history[:-1]
    base = [r for r in earlier if _valid(r)]
    out = {"status": "SCORED", "level": None, "n_checks": len(history), "reasons": [],
           "today": {"median_rt_ms": today.get("median_rt_ms"), "miss_count": today.get("miss_count"),
                     "trials": today.get("trials"), "created_at": today.get("created_at")}}
    if not _valid(today):
        out.update(status="NO_RESPONSE", level=None,
                   summary="No valid response was recorded in this check (every trial was missed). That says nothing about the person: check the device and try again.")
        return out
    if len(base) < MIN_BASELINE_CHECKS:
        out.update(status="CALIBRATING", level=None,
                   summary=f"Building your usual response time: {len(base)} of {MIN_BASELINE_CHECKS} earlier checks so far, so there is nothing to compare with yet.")
        return out

    rts = np.array([r["median_rt_ms"] for r in base], dtype=float)
    centre = float(np.median(rts))
    spread = max(1.4826 * float(np.median(np.abs(rts - centre))), SPREAD_FLOOR_FRACTION * centre, SPREAD_FLOOR_MS)
    z = (float(today["median_rt_ms"]) - centre) / spread
    out["baseline"] = {"n": len(base), "median_rt_ms": round(centre, 1), "spread_ms": round(spread, 1)}
    out["deviation"] = round(z, 2)
    level = "MUCH_SLOWER" if z >= MUCH_SLOWER_AT else "SLOWER" if z >= SLOWER_AT else "USUAL"
    out["level"] = level
    rt = round(float(today["median_rt_ms"]))
    usual = round(centre)
    if level == "USUAL":
        out["summary"] = f"Your response time today ({rt} ms) is within your own usual range (about {usual} ms)."
    else:
        word = "much slower than" if level == "MUCH_SLOWER" else "slower than"
        out["summary"] = f"Your response time today ({rt} ms) is {word} your own usual (about {usual} ms)."
        out["reasons"].append(f"Response time (median of {today.get('trials', 10)} trials): {rt} ms against your usual {usual} ms "
                              f"({z:+.1f} robust SD, slower than usual).")
    base_misses = [r.get("miss_count", 0) for r in base]
    miss = today.get("miss_count") or 0
    if miss >= 2 and miss > max(base_misses):
        out["reasons"].append(f"Missed responses: {miss} of {today.get('trials', 10)}, more than in any of your {len(base)} earlier checks.")
    return out
