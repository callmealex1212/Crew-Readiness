"""
Is "how rare is today FOR THIS PERSON" calibrated?   Run: python -m ml.calibration   (synthetic, illustrative assumptions)

Idea: rank today's score among the person's own recent past scores. That rank is a conformal p-value,
    p = (1 + #{past scores >= today}) / (1 + n),
and if the person's sessions are exchangeable it is (conservatively) uniform, so "alert when p <= alpha" has a
false-alert rate of at most alpha WHATEVER the shape of their noise. We test that, not assume it.

Part A  event-free people: observed false-alert rate vs the target alpha.
Part B  people with a real change: detection at the SAME false-alert rate as a population-wide score threshold.
        Run twice: everyone alike, and people who differ in how erratic they are (the sensitivity that matters).
"""
import numpy as np

from app.readiness import score_history

from .synth import Event, PopulationSpec, simulate_person

WINDOW, MIN_PAST, ALPHAS = 20, 8, (0.20, 0.10, 0.05)


def scores_of(sessions):
    return [v.score for v, _b, _x in score_history(sessions, "docking_checklist_v1")]


def rarity(scores, i, window=WINDOW, min_past=MIN_PAST):
    """Conformal p-value of scores[i] against this person's own earlier scores, or None if we cannot say yet."""
    past = [s for s in scores[:i] if s is not None][-window:]
    if scores[i] is None or len(past) < min_past:
        return None
    return (1 + sum(s >= scores[i] for s in past)) / (len(past) + 1)


def part_a(n_people=400, n_sessions=40, seed=11, pop=PopulationSpec()):
    rng = np.random.default_rng(seed)
    ps = []
    for _ in range(n_people):
        s, _t = simulate_person(rng, n_sessions, pop)
        sc = scores_of(s)
        ps += [p for i in range(len(s)) if (p := rarity(sc, i)) is not None]
    ps = np.array(ps)
    return {a: float(np.mean(ps <= a)) for a in ALPHAS}, len(ps)


def part_b(magnitude, n_people=400, n_sessions=40, start=18, length=5, seed=7, pop=PopulationSpec()):
    rng = np.random.default_rng(seed)
    ev = Event("step", start, length, magnitude)
    null_sc, null_p, evt_sc, evt_p = [], [], [], []
    for _ in range(n_people):
        s, t = simulate_person(rng, n_sessions, pop, events=(ev,))
        sc = scores_of(s)
        for i in range(n_sessions):
            if sc[i] is None:
                continue
            p = rarity(sc, i)
            if t[i] > 0:
                evt_sc.append(sc[i]); evt_p.append(p)
            elif i < start:
                null_sc.append(sc[i]); null_p.append(p)
    out = {}
    for a in ALPHAS:
        pers = [p for p in evt_p if p is not None]
        far = float(np.mean(np.array([p for p in null_p if p is not None]) <= a))          # the personal rule's OBSERVED false-alert rate (below alpha: coarse p-values)
        th = np.quantile(null_sc, 1 - far) if far > 0 else np.inf                           # a population threshold with that SAME observed rate: the fair comparison
        out[a] = {"population_threshold": round(float(np.mean(np.array(evt_sc) > th)), 3),
                  "personal_rarity": round(float(np.mean(np.array(pers) <= a)), 3) if pers else None,
                  "personal_false_alerts": round(far, 3)}
    return out


if __name__ == "__main__":
    for label, pop in (("everyone alike", PopulationSpec()), ("people differ in how erratic they are (sigma 0.5)", PopulationSpec(noise_sigma=0.5))):
        rates, n = part_a(pop=pop)
        print(f"\n== {label}\nA) false-alert rate on event-free sessions ({n} sessions): " +
              "  ".join(f"target {a:.2f} -> observed {r:.3f}" for a, r in rates.items()))
        for mag in (0.10, 0.20):
            b = part_b(mag, pop=pop)
            print(f"B) {mag:.0%} slowdown, detection at matched false-alert rate:")
            for a, r in b.items():
                print(f"     alpha {a:.2f}: population threshold {r['population_threshold']:.2f} | personal rarity {r['personal_rarity']:.2f} (its false alerts {r['personal_false_alerts']:.3f})")
