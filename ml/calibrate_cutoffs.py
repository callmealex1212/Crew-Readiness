"""
Alert-budget calibration: choose the cutoff for a STATED false-alert budget, then check it on people it was NOT fitted on.

A "budget" of 1 in 20 means: on a normal session, about 1 in 20 would be flagged by chance. We fit the cutoff on the pooled normal-session
scores of some people and measure the false-alert rate on held-out people (k folds, split by PERSON, never by session). The average
can be right while some individuals are not, so we also report how many people exceed twice the budget.

Works on any list of per-person score lists: simulated crews here, the real pilot later (ml/pilot_report.py).
Run: python -m ml.calibrate_cutoffs   (synthetic, illustrative assumptions)
"""
from math import comb

import numpy as np

from .calibration import scores_of
from .synth import PopulationSpec, simulate_person

BUDGETS = (1 / 10, 1 / 20, 1 / 50)
SHIPPED_YELLOW = 1.0          # the cutoff the product uses today (app/scoring.py BAND_CUTOFFS)


def null_scores(n_people=300, n_sessions=40, seed=21, pop=PopulationSpec()):
    """Per person, the product's scores on event-free sessions (None while calibrating are dropped)."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n_people):
        s, _t = simulate_person(rng, n_sessions, pop)
        out.append(np.array([x for x in scores_of(s) if x is not None]))
    return out


def far_at(cutoff, scores):
    return float(np.mean(scores >= cutoff)) if len(scores) else float("nan")


def expected_share_over_2x(people, budget):
    """What chance ALONE would give: if everyone had exactly this false-alert rate, how many people (with their own number of
    sessions) would still show more than twice the budget? Without this, 'people over 2x' mostly measures too few sessions."""
    shares = []
    for p in people:
        n = len(p)
        if n:
            limit = int(2 * budget * n)                                   # more than twice the budget means strictly more flags than this
            shares.append(1 - sum(comb(n, k) * budget ** k * (1 - budget) ** (n - k) for k in range(limit + 1)))
    return float(np.mean(shares))


def heldout_calibration(people, budget, k=10, seed=0, n_boot=1000):
    """Per-person false-alert rate with the cutoff fitted on OTHER people only. Returns a summary dict."""
    idx = np.random.default_rng(seed).permutation(len(people))
    folds = np.array_split(idx, k)
    per_person = np.full(len(people), np.nan)
    cutoffs = []
    for f in folds:
        train = np.concatenate([people[i] for i in idx if i not in set(f)])
        cut = float(np.quantile(train, 1 - budget))
        cutoffs.append(cut)
        for i in f:
            per_person[i] = far_at(cut, people[i])
    boot = np.random.default_rng(seed + 1)
    means = [np.mean(boot.choice(per_person, len(per_person))) for _ in range(n_boot)]
    return {"budget": budget, "cutoff": round(float(np.mean(cutoffs)), 3),
            "observed": round(float(np.mean(per_person)), 4), "ci95": [round(float(np.quantile(means, .025)), 4), round(float(np.quantile(means, .975)), 4)],
            "share_over_2x_budget": round(float(np.mean(per_person > 2 * budget)), 3),
            "share_over_2x_by_chance_alone": round(expected_share_over_2x(people, budget), 3),
            "worst_person": round(float(np.nanmax(per_person)), 3)}


def what_budget_is_the_shipped_cutoff(people, cutoff=SHIPPED_YELLOW):
    allscores = np.concatenate(people)
    rate = far_at(cutoff, allscores)
    per_person = np.array([far_at(cutoff, p) for p in people])
    return {"cutoff": cutoff, "false_alert_rate": round(rate, 4), "one_in": round(1 / max(rate, 1e-9), 1),
            "share_of_people_over_2x": round(float(np.mean(per_person > 2 * rate)), 3),
            "share_over_2x_by_chance_alone": round(expected_share_over_2x(people, rate), 3)}


if __name__ == "__main__":
    for label, pop in (("everyone alike", PopulationSpec()), ("people differ in how erratic they are (sigma 0.5)", PopulationSpec(noise_sigma=0.5))):
        people = null_scores(pop=pop)
        s = what_budget_is_the_shipped_cutoff(people)
        print(f"\n== {label}  ({len(people)} people, {sum(len(p) for p in people)} normal sessions)")
        print(f"shipped YELLOW cutoff {s['cutoff']}: false-alert rate {s['false_alert_rate']:.1%} = about 1 normal session in {s['one_in']}; "
              f"{s['share_of_people_over_2x']:.0%} of people see more than twice that (chance alone gives {s['share_over_2x_by_chance_alone']:.0%})")
        print(f"{'budget':>8} {'cutoff':>7} {'observed (held-out)':>20} {'95% CI':>16} {'people >2x budget':>18} {'by chance alone':>16} {'worst person':>13}")
        for b in BUDGETS:
            r = heldout_calibration(people, b)
            print(f"{'1 in %d' % round(1 / b):>8} {r['cutoff']:>7} {r['observed']:>20.1%} {str(['%.1f%%' % (100 * x) for x in r['ci95']]):>16} {r['share_over_2x_budget']:>18.0%} {r['share_over_2x_by_chance_alone']:>16.0%} {r['worst_person']:>13.0%}")
