"""
F4 feasibility check: our personal-baseline rule on NASA's public WinSCAT bed-rest data (real people). Read docs/DATA_SEARCH.md first.

The data are NOT in this repository. Download them yourself from the NASA Life Sciences Portal (experiment "Neurocognitive
Assessment (WinSCAT) (Flight Analog)", DOI 10.83263/sbne-th55: "Download UTMB Bedrest Campaign 3 WinSCAT"), unzip, then:

    python scripts/nasa_winscat_check.py path/to/MR085G_Campaign_3_WinSCAT

What it does, per person: the baseline is their own pre-bed-rest sessions (run 1, their first exposure to the test, is dropped as
practice); every later session (in bed rest, after bed rest) is compared with it using the product's per-measure rule: robust z
(median and 1.4826 x MAD, the same statistics and constants as app/baseline.py, spread floored at 5 % of the median as in app/scoring.py), one-sided (slower
or less accurate only), capped at 4. A session is "flagged" on a measure when that deviation is >= 1.0, the level at which the
product writes a reason. This is ONE measure at a time, not the product's weighted score, and WinSCAT is not our typing task.

Ground truth: the original study reports no consistent cognitive decrement across subjects or time in bed rest. So flags here are
best read as alerts where no change was induced on purpose; they are not proven false alarms, and nothing here is about health.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from app.baseline import MAD_TO_SD, MIN_BASELINE_SESSIONS  # noqa: E402

FLOOR = 0.05      # app/scoring.py RELATIVE_SPREAD_FLOOR
CAP = 4.0         # app/scoring.py DEVIATION_CAP
FLAG_AT = 1.0     # app/scoring.py REASON_THRESHOLD
# measure -> direction (+1: higher is worse, -1: lower is worse)
MEASURES = {"CPTRT": +1, "MTHRT": +1, "MTSRT": +1, "CDDRT": +1, "CPTA": -1}


def load(folder: Path) -> dict[str, list[dict]]:
    people: dict[str, list[dict]] = {}
    for f in sorted(folder.iterdir()):
        if not f.is_file() or "ReadMe" in f.name or f.name.endswith("_All") or f.suffix == ".md5sum":
            continue
        with open(f, newline="", encoding="utf-8", errors="replace") as fh:
            rows = [r for r in csv.DictReader(fh) if r.get("Run")]
        for r in rows:
            try:
                r["_run"] = int(float(r["Run"]))
                for m in MEASURES:
                    r[m] = float(r[m])
            except (KeyError, ValueError):
                r["_bad"] = True
        rows = [r for r in rows if not r.get("_bad")]
        if rows:
            people[f.name] = sorted(rows, key=lambda r: r["_run"])
    return people


def deviation(value: float, median: float, spread: float, direction: int) -> float:
    spread = max(spread, FLOOR * abs(median), 1e-9)
    return min(max(0.0, direction * (value - median) / spread), CAP)


def main(folder: Path) -> int:
    people = load(folder)
    used, flags, scored, per_phase = 0, {m: 0 for m in MEASURES}, 0, {}
    any_flag = 0
    for pid, rows in people.items():
        pre = [r for r in rows if r.get("Test_Phase") == "PRE_TEST" and r["_run"] != 1]   # run 1 = first exposure (practice)
        later = [r for r in rows if r.get("Test_Phase") in ("IN_TEST", "POST_TEST")]
        if len(pre) < MIN_BASELINE_SESSIONS or not later:
            continue
        used += 1
        base = {}
        for m in MEASURES:   # the same statistics as app/baseline.compute_baseline, for one measure
            v = np.array([r[m] for r in pre])
            med = float(np.median(v))
            base[m] = (med, MAD_TO_SD * float(np.median(np.abs(v - med))))
        for r in later:
            scored += 1
            phase = r["Test_Phase"]
            hit = False
            for m, direction in MEASURES.items():
                med, spread = base[m]
                if deviation(r[m], med, spread, direction) >= FLAG_AT:
                    flags[m] += 1
                    hit = True
            any_flag += hit
            p = per_phase.setdefault(phase, [0, 0])
            p[0] += 1
            p[1] += hit
    print(f"people with >= {MIN_BASELINE_SESSIONS} baseline sessions and later sessions: {used} (of {len(people)} files)")
    print(f"later sessions scored: {scored}")
    if not scored:
        print("nothing to score: no person has enough baseline sessions and later sessions in this folder")
        return 1
    for m in MEASURES:
        print(f"  flagged on {m:6s}: {flags[m]:3d} / {scored}  ({flags[m] / scored:.0%})")
    print(f"  flagged on at least one of the {len(MEASURES)} measures: {any_flag} / {scored}  ({any_flag / scored:.0%})")
    for phase, (n, k) in sorted(per_phase.items()):
        print(f"  {phase}: {k} / {n} sessions flagged on at least one measure")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2 or not Path(sys.argv[1]).is_dir():
        print(__doc__)
        sys.exit(2)
    sys.exit(main(Path(sys.argv[1])))
