"""
Run the benchmark and write app/results_data.json, which the /evidence page renders.
The page never contains typed-in numbers: regenerate this file and the page changes.
Run: python -m ml.export_results      (takes a few minutes; synthetic, illustrative assumptions)
"""
import json
from pathlib import Path

import numpy as np

from . import candidates
from .compare import N_PEOPLE, N_SESS, collect
from .calibrate_cutoffs import BUDGETS, heldout_calibration, null_scores, what_budget_is_the_shipped_cutoff
from .evaluate import evaluate, evaluate_ci, incumbent_detector

FAR, SEED = 0.05, 7
OUT = Path(__file__).resolve().parents[1] / "app" / "results_data.json"
DETS = {"incumbent": incumbent_detector, "gamma_poisson": candidates.candidate_pause_model,
        "neg_binomial": candidates.candidate_nb}


def detection(det, mag, od):
    normal, event = collect(det, mag, SEED, od)
    return round(float(np.mean(event > np.quantile(normal, 1 - FAR))), 2)


if __name__ == "__main__":
    table = []
    for od, od_label in ((0.0, "none"), (1.5, "high")):
        for mag in (0.06, 0.10, 0.15):
            row = {"slowdown": mag, "burstiness": od_label}
            row.update({k: detection(d, mag, od) for k, d in DETS.items()})
            table.append(row)
            print(row, flush=True)
    stress = []
    for p in (0.05, 0.5, 2.0):
        candidates.pause_model.PRIOR_DISPERSION = p
        stress.append({"assumed_prior": p, **{f"true_od_{od}": detection(candidates.candidate_nb, 0.10, od) for od in (0.0, 0.5, 1.5)}})
    candidates.pause_model.PRIOR_DISPERSION = 0.5
    stress.append({"assumed_prior": "incumbent", **{f"true_od_{od}": detection(incumbent_detector, 0.10, od) for od in (0.0, 0.5, 1.5)}})
    fa = evaluate(incumbent_detector, shape="step", magnitude=0.10, length=5, n_people=N_PEOPLE, seed=SEED).false_alert_rate
    # the product's own operating point: alert at score >= 1.0 (YELLOW), no threshold matching
    op = []
    for mag in (0.06, 0.10, 0.15):
        row = {"slowdown": mag}
        for key, det in (("before", incumbent_detector), ("now", candidates.candidate_nb)):
            r = evaluate_ci(det, shape="step", magnitude=mag, length=5, n_people=N_PEOPLE, seed=SEED, alert_threshold=1.0)
            row[key] = {"detection": round(r["detection"], 2), "false_alerts": round(r["false_alerts"], 3),
                        "detection_ci": [round(x, 2) for x in r["detection_ci"]], "false_alerts_ci": [round(x, 3) for x in r["false_alerts_ci"]]}
        op.append(row)
        print(row, flush=True)
    # alert budget: a cutoff fitted on some people, measured on held-out people (ml/calibrate_cutoffs.py)
    people = null_scores(n_people=300)
    budget = {"people": len(people), "normal_sessions": int(sum(len(p) for p in people)),
              "shipped": what_budget_is_the_shipped_cutoff(people),
              "rows": [heldout_calibration(people, b) for b in BUDGETS]}
    print(budget, flush=True)
    OUT.write_text(json.dumps({
        "synthetic": True,
        "setup": {"false_alert_rate": FAR, "event": "5-session step slowdown", "people_per_cell": N_PEOPLE,
                  "sessions_per_person": N_SESS, "seed": SEED},
        "incumbent_false_alerts_at_yellow": round(fa, 3),
        "table": table, "stress": stress, "operating_point": op, "budget_calibration": budget,
        "commands": ["python -m ml.compare 0.5", "python -m ml.stress_prior", "python -m ml.calibrate_cutoffs", "python -m ml.export_results"],
    }, indent=2) + "\n")
    print("wrote", OUT)
