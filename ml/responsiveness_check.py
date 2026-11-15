"""
How does the responsiveness rule (app/responsiveness.py) behave on SIMULATED people? Run: python -m ml.responsiveness_check

ILLUSTRATIVE ASSUMPTIONS, not measurements: each person's usual median response time is uniform in 230-350 ms, and one check's median
varies around it with a coefficient of variation of 7 %. Real reaction checks may differ a lot (this is exactly what is not validated).
For each person we simulate N earlier checks, then one check that is either normal or slower by a stated fraction.
"""
import numpy as np

from app.responsiveness import assess

N_PEOPLE, N_EARLIER, CV, SEED = 2000, 8, 0.07, 3


def run(slowdown: float, n_earlier: int = N_EARLIER, seed: int = SEED) -> float:
    """Share of simulated people flagged (SLOWER or MUCH_SLOWER) when today's check is `slowdown` slower than their usual."""
    rng = np.random.default_rng(seed)
    flagged = 0
    for _ in range(N_PEOPLE):
        usual = rng.uniform(230, 350)
        hist = [{"median_rt_ms": float(rng.normal(usual, CV * usual)), "miss_count": 0, "trials": 10} for _ in range(n_earlier)]
        today = {"median_rt_ms": float(rng.normal(usual, CV * usual)) * (1 + slowdown), "miss_count": 0, "trials": 10}
        flagged += assess(hist + [today])["level"] in ("SLOWER", "MUCH_SLOWER")
    return flagged / N_PEOPLE


if __name__ == "__main__":
    print(f"{N_PEOPLE} simulated people, {N_EARLIER} earlier checks each, per-check variation {CV:.0%} (assumed)")
    print(f"normal check flagged (false alerts): {run(0.0):.1%}")
    for s in (0.10, 0.20, 0.30):
        print(f"{s:.0%} slower flagged: {run(s):.1%}")
