"""
Task C4: analyse the REAL pilot (docs/PILOT.md) with the same scoring the product uses.

Inputs (both made by people, see docs/PILOT.md):
  * the export from `python scripts/export_pilot.py`   columns: pseudonym, session_number + the nine features
  * the session sheet `docs/pilot/session_sheet.csv`    columns: pseudonym, consent, session_number, condition, perturbation, issue

    python -m ml.pilot_report --sessions docs/pilot/pilot_sessions.csv --sheet docs/pilot/session_sheet.csv

It answers three questions and states how little a pilot of this size can say:
  1. False alerts: on sessions labelled NORMAL, how often does the shipped YELLOW cutoff (1.0) fire?
  2. Detection: on sessions labelled PERTURBED (non-dominant hand / counting backwards), how often?
  3. Is the simulator realistic: are real people's session-to-session variability and pause counts close to what
     ml/synth.py assumes? If not, `suggest_population` gives the numbers to put into the benchmark and re-run it.

Nothing here reads or stores anything but the aggregate features. Every figure is from a handful of volunteers on one
laptop: say so wherever it is quoted (the "limits" list in the output). It is not validation on crews or astronauts.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

from app.features import FEATURE_NAMES, assess_quality
from app.readiness import score_history
from app.scoring import BAND_CUTOFFS

from .calibrate_cutoffs import BUDGETS, heldout_calibration
from .synth import PopulationSpec

TASK_TYPE = "docking_checklist_v1"
YELLOW, RED = BAND_CUTOFFS[0][0], BAND_CUTOFFS[1][0]            # 1.0 and 2.0: the cutoffs the product uses
CONDITIONS = {"normal": {"none"}, "perturbed": {"non_dominant_hand", "counting_backwards"}}
MIN_PEOPLE_FOR_CALIBRATION = 5
MIN_NORMAL_FOR_VARIABILITY = 4
SIM_TOLERANCE = 1.5          # real/assumed outside [1/1.5, 1.5] means the simulator should change

LIMITS = [
    "A handful of volunteers on one laptop; a few dozen scored sessions, so every rate has a wide interval.",
    "The perturbations (non-dominant hand, counting backwards) are stand-ins for a change in how someone works; they are not fatigue, illness or any health state.",
    "Volunteers are not astronauts or crew, and a typed checklist is a stand-in task.",
    "Sessions 1 to 5 of each person are CALIBRATING (no score), so false alerts are counted on the few normal sessions after that.",
]


# ---------------------------------------------------------------- loading

def _rows(path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_pilot(sessions_csv, sheet_csv) -> dict[str, list[dict]]:
    """{pseudonym: [session, ...]} in session order, each session shaped like a stored session, plus its label.

    The export and the sheet must describe exactly the same sessions; any difference is an error, not something to paper over.
    """
    sheet = {}
    for r in _rows(sheet_csv):
        key = (r["pseudonym"], int(r["session_number"]))
        if key in sheet:
            raise ValueError(f"session sheet lists {key} twice")
        if r["consent"] != "yes":
            raise ValueError(f"session sheet row without consent: {key}")
        if r["condition"] not in CONDITIONS or r["perturbation"] not in CONDITIONS[r["condition"]]:
            raise ValueError(f"session sheet row {key}: condition/perturbation not allowed: {r['condition']}/{r['perturbation']}")
        sheet[key] = r
    sessions = {}
    for r in _rows(sessions_csv):
        key = (r["pseudonym"], int(r["session_number"]))
        if key in sessions:
            raise ValueError(f"export lists {key} twice")
        sessions[key] = r
    if set(sheet) != set(sessions):
        only_sheet, only_export = sorted(set(sheet) - set(sessions)), sorted(set(sessions) - set(sheet))
        raise ValueError(f"export and session sheet disagree. Only on the sheet: {only_sheet}. Only in the export: {only_export}")

    people: dict[str, list[dict]] = {}
    for (pid, n) in sorted(sessions):
        feats = {name: float(sessions[(pid, n)][name]) for name in FEATURE_NAMES}
        quality, _notes = assess_quality(feats)                  # the same rule the app applied when the session was stored
        s = dict(feats, id=n, data_quality=quality, accepted_at=None,
                 condition=sheet[(pid, n)]["condition"], perturbation=sheet[(pid, n)]["perturbation"])
        people.setdefault(pid, []).append(s)
    return people


# ---------------------------------------------------------------- scoring and rates

def score_people(people: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Add `score` (None while CALIBRATING or unusable) and `band` to each session, scoring exactly as the product does."""
    out = {}
    for pid, history in people.items():
        walked = score_history(history, TASK_TYPE)
        out[pid] = [dict(s, score=v.score if v.status == "SCORED" else None, band=v.band)
                    for s, (v, _b, _x) in zip(history, walked)]
    return out


def _wilson(k: int, n: int, z=1.96) -> tuple[float, float]:
    """Wilson 95 % interval for k of n. Treats sessions as independent, which they are not, so it is only a FLOOR on the width."""
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def _rate(per_person: list[list[float]], cutoff: float, n_boot=2000, seed=0) -> dict:
    """Share of scored sessions at or above `cutoff`, pooled over people.

    The 95 % interval is the WIDER of (a) resampling PEOPLE (sessions of one person are not independent) and (b) a Wilson interval
    on the sessions. With only a few people (a) can collapse to a single value ("100 % to 100 %"), which is not certainty."""
    people = [np.array(p) for p in per_person if len(p)]
    n = sum(len(p) for p in people)
    if not n:
        return {"flagged": 0, "n": 0, "rate": None, "ci95": None}
    flagged = int(sum((p >= cutoff).sum() for p in people))
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        pick = [people[i] for i in rng.integers(0, len(people), len(people))]
        boots.append(sum((p >= cutoff).sum() for p in pick) / sum(len(p) for p in pick))
    w_lo, w_hi = _wilson(flagged, n)
    return {"flagged": flagged, "n": n, "rate": round(flagged / n, 4),
            "ci95": [round(float(min(np.quantile(boots, .025), w_lo)), 4), round(float(max(np.quantile(boots, .975), w_hi)), 4)]}


def _scores(scored, condition, perturbation=None) -> list[list[float]]:
    return [[s["score"] for s in ss if s["condition"] == condition and s["score"] is not None
             and (perturbation is None or s["perturbation"] == perturbation)] for ss in scored.values()]


# ---------------------------------------------------------------- is the simulator realistic?

def variability(people: dict[str, list[dict]]) -> dict:
    """How much do real people vary from one normal session to the next, in the terms ml/synth.py uses?"""
    cv_iki, cv_resp, means, ods, ikis, ns = [], [], [], [], [], []
    for ss in people.values():
        normal = [s for s in ss if s["condition"] == "normal"]
        if len(normal) < MIN_NORMAL_FOR_VARIABILITY:
            continue
        ns.append(len(normal))
        iki = np.array([s["iki_median_ms"] for s in normal])
        resp = np.array([s["checklist_response_median_ms"] for s in normal])
        pauses = np.array([s["pause_count"] for s in normal])
        cv_iki.append(float(iki.std(ddof=1) / iki.mean()))
        cv_resp.append(float(resp.std(ddof=1) / resp.mean()))
        means.append(float(pauses.mean()))
        ikis.append(float(np.median(iki)))
        if pauses.mean() > 0:
            ods.append(max(0.0, (float(pauses.var(ddof=1)) - float(pauses.mean())) / float(pauses.mean()) ** 2))
    if not cv_iki:
        return {"n_people": 0}
    pop = PopulationSpec()
    # A CV estimated from n sessions has a relative standard error of about 1/sqrt(2(n-1)); spread between people that is
    # no bigger than that is just sampling noise, so it is subtracted before we call people "differently erratic".
    sampling = 1 / (2 * (float(np.mean(ns)) - 1))
    observed = float(np.var(np.log(cv_iki), ddof=1)) if len(cv_iki) > 1 else 0.0
    sigma = float(np.sqrt(max(0.0, observed - sampling)))
    result = {
        "n_people": len(cv_iki),
        "iki_cv": {"real_median": round(float(np.median(cv_iki)), 4), "assumed": pop.iki_cv},
        "resp_cv": {"real_median": round(float(np.median(cv_resp)), 4), "assumed": pop.resp_cv},
        "pause_mean_per_session": {"real_min": round(min(means), 2), "real_median": round(float(np.median(means)), 2),
                                   "real_max": round(max(means), 2), "assumed_range": list(pop.pause_rate)},
        "pause_overdispersion": {"real_median": round(float(np.median(ods)), 3) if ods else None, "assumed": pop.pause_overdispersion},
        "iki_median_ms": {"real_min": round(min(ikis)), "real_max": round(max(ikis)), "assumed_range": list(pop.iki_ms)},
        "noise_sigma": {"real_estimate": round(sigma, 3), "assumed": pop.noise_sigma},
    }
    for k in ("iki_cv", "resp_cv"):
        result[k]["ratio"] = round(result[k]["real_median"] / result[k]["assumed"], 2)
    result["simulator_assumptions_hold"] = all(1 / SIM_TOLERANCE <= result[k]["ratio"] <= SIM_TOLERANCE for k in ("iki_cv", "resp_cv"))
    return result


def suggest_population(var: dict) -> PopulationSpec:
    """The benchmark's PopulationSpec with the variability measured on the pilot. Use it to re-run `python -m ml.export_results`
    only if `simulator_assumptions_hold` is false, and say in the docs that the numbers moved because of it."""
    if not var.get("n_people"):
        raise ValueError("no pilot variability to learn from")
    od = var["pause_overdispersion"]["real_median"]
    return replace(PopulationSpec(), iki_cv=var["iki_cv"]["real_median"], resp_cv=var["resp_cv"]["real_median"],
                   pause_overdispersion=od if od else 0.0, noise_sigma=var["noise_sigma"]["real_estimate"])


# ---------------------------------------------------------------- the report

def build_report(sessions_csv, sheet_csv) -> dict:
    people = load_pilot(sessions_csv, sheet_csv)
    scored = score_people(people)
    normal, perturbed = _scores(scored, "normal"), _scores(scored, "perturbed")

    def both(per_person):
        return {"yellow": _rate(per_person, YELLOW), "red": _rate(per_person, RED)}

    detection = {"all": both(perturbed)}
    for kind in ("non_dominant_hand", "counting_backwards"):
        detection[kind] = both(_scores(scored, "perturbed", kind))

    usable = [np.array(p) for p in normal if len(p)]
    calibration = None
    if len(usable) >= MIN_PEOPLE_FOR_CALIBRATION:
        calibration = [heldout_calibration(usable, b, k=min(10, len(usable))) for b in BUDGETS]

    per_person = []
    for pid, ss in scored.items():
        n_sc = [s["score"] for s in ss if s["condition"] == "normal" and s["score"] is not None]
        p_sc = [s["score"] for s in ss if s["condition"] == "perturbed" and s["score"] is not None]
        per_person.append({"pseudonym": pid, "perturbation": next((s["perturbation"] for s in ss if s["condition"] == "perturbed"), "none"),
                           "normal_scores": [round(x, 2) for x in n_sc], "perturbed_scores": [round(x, 2) for x in p_sc],
                           "n_sessions": len(ss), "n_low_quality": sum(s["data_quality"] != "ok" for s in ss)})

    var = variability(people)
    return {
        "source": {"sessions": str(sessions_csv), "sheet": str(sheet_csv)},
        "n_people": len(people), "n_sessions": sum(len(v) for v in people.values()),
        "cutoffs": {"yellow": YELLOW, "red": RED},
        "false_alerts_on_normal": both(normal),
        "detection_on_perturbed": detection,
        "calibration_on_normal": calibration,
        "per_person": per_person,
        "variability": var,
        "limits": LIMITS,
    }


def _pct(x):
    return "n/a" if x is None else f"{100 * x:.0f}%"


def render(r: dict) -> str:
    fa, de = r["false_alerts_on_normal"]["yellow"], r["detection_on_perturbed"]
    lines = [f"Pilot: {r['n_people']} people, {r['n_sessions']} sessions (REAL volunteers; not astronauts, not crews).",
             f"False alerts on normal sessions (score >= {r['cutoffs']['yellow']}): {fa['flagged']} of {fa['n']} = {_pct(fa['rate'])}"
             + (f"  95% interval {_pct(fa['ci95'][0])} to {_pct(fa['ci95'][1])}" if fa["ci95"] else ""),
             "Detection on perturbed sessions:"]
    for kind, d in de.items():
        y = d["yellow"]
        lines.append(f"  {kind:20s} {y['flagged']} of {y['n']} = {_pct(y['rate'])}"
                     + (f"  95% interval {_pct(y['ci95'][0])} to {_pct(y['ci95'][1])}" if y["ci95"] else ""))
    v = r["variability"]
    if v.get("n_people"):
        lines += ["Is the simulator realistic?",
                  f"  keystroke-interval variability  real {v['iki_cv']['real_median']}  assumed {v['iki_cv']['assumed']}  (x{v['iki_cv']['ratio']})",
                  f"  checklist-response variability  real {v['resp_cv']['real_median']}  assumed {v['resp_cv']['assumed']}  (x{v['resp_cv']['ratio']})",
                  f"  pauses per session  real {v['pause_mean_per_session']['real_min']} to {v['pause_mean_per_session']['real_max']}  assumed {v['pause_mean_per_session']['assumed_range'][0]} to {v['pause_mean_per_session']['assumed_range'][1]}",
                  "  -> " + ("assumptions hold (within a factor of 1.5)" if v["simulator_assumptions_hold"]
                             else "assumptions are off by more than 1.5x: re-run the benchmark with suggest_population() and say so")]
    lines += ["Limits: " + " ".join(r["limits"])]
    return "\n".join(lines)


def main(argv=None) -> int:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--sessions", type=Path, default=root / "docs" / "pilot" / "pilot_sessions.csv")
    ap.add_argument("--sheet", type=Path, default=root / "docs" / "pilot" / "session_sheet.csv")
    ap.add_argument("--out", type=Path, default=root / "docs" / "pilot" / "pilot_report.json")
    a = ap.parse_args(argv)
    for p in (a.sessions, a.sheet):
        if not p.exists():
            print(f"missing {p}. Run scripts/export_pilot.py and fill docs/pilot/session_sheet.csv first (docs/PILOT.md).", file=sys.stderr)
            return 1
    report = build_report(a.sessions, a.sheet)
    a.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(render(report))
    print(f"\nwritten to {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
