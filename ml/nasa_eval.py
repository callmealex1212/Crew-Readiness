"""
Our method on REAL NASA repeated measures (task N1): NASA Life Sciences Data Archive, "Neurocognitive Assessment (WinSCAT)
(Cognitive Assessment Tool for Windows) (Flight Analog)", DOI 10.83263/sbne-th55, UTMB bed-rest Campaign 3. See docs/NASA_DATA.md.

    python -m ml.nasa_eval <unzipped Campaign 3 folder> --zip <the downloaded zip>      # writes app/nasa_results.json

The raw files are NOT in this repository and nothing per session or per person is written: the output holds aggregates and counts
only. Remove app/nasa_results.json and the Evidence page section disappears (one step).

What it computes (shape: docs/DATA_CONTRACT.md "NASA bed-rest results file"):
  (a) ICC: how much of the variation in each WinSCAT median response time is BETWEEN people rather than within a person, on
      pre-bed-rest sessions only (one-way random effects, ICC(1)); 95 % interval by resampling PEOPLE.
  (b) The product's own-baseline rule against one threshold for everyone, at the SAME alert budget, judged on HELD-OUT people
      (leave one person out: each cutoff is fitted on the other people's pre-bed-rest sessions only). A session's score is the mean,
      over the four response-time measures, of the product's per-measure deviation (robust z, spread floored at 5 % of the median,
      one-sided: slower only, capped at 4). Own baseline = the person's own pre-bed-rest sessions (for a pre-bed-rest session, the
      person's OTHER pre-bed-rest sessions); population = all OTHER people's pre-bed-rest sessions pooled. Reported: the share of
      pre-bed-rest sessions flagged (no change induced on purpose) and of during-bed-rest sessions flagged, with 95 % intervals by
      resampling people, and how many people the population rule flags in most of their sessions.
  (c) "Any of five measures": the figure in docs/DATA_SEARCH.md, regenerated with scripts/nasa_winscat_check.py.
It says nothing about anyone's health. The original study reports no consistent cognitive decrement in bed rest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import nasa_winscat_check as wc  # noqa: E402

OUT = ROOT / "app" / "nasa_results.json"
SOURCE = {
    "title": "WinSCAT test battery, UTMB bed-rest Campaign 3 (Flight Analog)",   # short name shown on the page
    "full_title": "Neurocognitive Assessment (WinSCAT) (Cognitive Assessment Tool for Windows) (Flight Analog)",   # the archive's title
    "doi": "10.83263/sbne-th55",
    "url": "https://nlsp.nasa.gov/explore/data/details/80ee3231-7c42-5be4-b6c2-b8c788feeb50?dataType=EXPERIMENTS",
    "archive": "NASA Life Sciences Data Archive (NASA Life Sciences Portal)",
}
RT_MEASURES = {   # WinSCAT ReadMe names; all are median response times in ms, higher = slower
    "CPTRT": "Running memory response time",
    "MTHRT": "Mathematics response time",
    "MTSRT": "Match to sample response time",
    "CDDRT": "Code substitution (delayed) response time",
}
FIVE_LABELS = dict(RT_MEASURES, CPTA="Running memory accuracy")
MIN_SESSIONS = 8          # the dataset fit criterion in docs/DATA_SEARCH.md
MIN_PRE = 3               # pre-bed-rest sessions (after dropping run 1) needed to score one against the others
ALERT_BUDGET = 0.05       # 1 in 20, the product's stated budget for YELLOW (docs/ML_RESULTS.md)
N_BOOT = 2000
LIMITS = [
    "WinSCAT is not our typing task: it is a cognitive test battery, used here to check the method, not the product.",
    "Sessions are days to weeks apart, unlike routine check-ins before an operation.",
    "Each person's baseline has only a few sessions (about five before bed rest), fewer than a long mission would give.",
    "This is a check of the METHOD on real NASA repeated measures. It is not validation of the product, and it is not on astronauts or crews.",
    "It says nothing about health, fatigue, illness or fitness for duty.",
    "The original study reports no consistent cognitive decrement during bed rest, so a flag means \"differs from this person's own pattern\", never impairment.",
    "Practice effect: people get faster at the test over its first sessions. Pre-bed-rest sessions include that learning; bed-rest sessions come after it, so they tend to look faster than the baseline, which lowers flag rates during bed rest for both rules.",
    "One study, one campaign, about two dozen people, all on the ground; intervals are wide.",
]


# ------------------------------------------------------------------ data

def usable(people: dict[str, list[dict]]) -> list[dict]:
    """People with >= MIN_SESSIONS sessions; per person: pre (run 1 dropped) and during-bed-rest rows."""
    out = []
    for rows in people.values():
        if len(rows) < MIN_SESSIONS:
            continue
        pre = [r for r in rows if r.get("Test_Phase") == "PRE_TEST" and r["_run"] != 1]
        during = [r for r in rows if r.get("Test_Phase") == "IN_TEST"]
        out.append({"pre": pre, "during": during})
    return out


# ------------------------------------------------------------------ (a) ICC

def icc1(groups: list[np.ndarray]) -> float:
    """One-way random-effects ICC(1) for unequal group sizes (between-person share of variance)."""
    groups = [g for g in groups if len(g) >= 2]
    k = len(groups)
    n = np.array([len(g) for g in groups], dtype=float)
    N = n.sum()
    grand = np.concatenate(groups).mean()
    ssb = float(sum(len(g) * (g.mean() - grand) ** 2 for g in groups))
    ssw = float(sum(((g - g.mean()) ** 2).sum() for g in groups))
    msb, msw = ssb / (k - 1), ssw / (N - k)
    n0 = (N - (n ** 2).sum() / N) / (k - 1)
    return float((msb - msw) / (msb + (n0 - 1) * msw))


def icc_table(people: list[dict], seed: int = 1) -> list[dict]:
    rng = np.random.default_rng(seed)
    out = []
    for m, label in RT_MEASURES.items():
        groups = [np.array([r[m] for r in p["pre"]]) for p in people if len(p["pre"]) >= 2]
        point = icc1(groups)
        boots = [icc1([groups[i] for i in rng.integers(0, len(groups), len(groups))]) for _ in range(N_BOOT)]
        out.append({"measure": m, "label": label, "icc": round(point, 3),
                    "ci95": [round(float(np.quantile(boots, .025)), 3), round(float(np.quantile(boots, .975)), 3)]})
    return out


# ------------------------------------------------------------------ (b) own baseline vs one threshold for everyone

def _stats(values) -> tuple[float, float]:
    v = np.asarray(values, dtype=float)
    med = float(np.median(v))
    return med, wc.MAD_TO_SD * float(np.median(np.abs(v - med)))


def score(row: dict, stats: dict) -> float:
    """Mean of the product's per-measure deviations (one-sided, floored spread, capped) over the four response times."""
    return float(np.mean([wc.deviation(row[m], *stats[m], +1) for m in RT_MEASURES]))


def own_scores(p: dict) -> tuple[list[float], list[float]]:
    """Pre sessions: each against the person's OTHER pre sessions. During: against their most recent pre sessions, one fewer than
    all, so both phases use a baseline of the SAME size (a smaller baseline gives larger deviations; mixing sizes would bias the
    comparison). The earliest pre session is the one left out, as a rolling window would."""
    pre = [score(r, {m: _stats([o[m] for j, o in enumerate(p["pre"]) if j != i]) for m in RT_MEASURES})
           for i, r in enumerate(p["pre"])]
    base = {m: _stats([o[m] for o in p["pre"][1:]]) for m in RT_MEASURES}
    return pre, [score(r, base) for r in p["during"]]


def population_scores(p: dict, others: list[dict]) -> tuple[list[float], list[float]]:
    base = {m: _stats([o[m] for q in others for o in q["pre"]]) for m in RT_MEASURES}
    return [score(r, base) for r in p["pre"]], [score(r, base) for r in p["during"]]


def _cutoff(train_scores: list[float], budget: float) -> float:
    s = np.asarray(train_scores, dtype=float)
    cut = float(np.quantile(s, 1 - budget))
    if cut <= 0:                                   # most normal sessions score exactly 0; a cutoff of 0 would flag them all
        positive = s[s > 0]
        cut = float(positive.min()) if positive.size else float("inf")
    return cut


def _rate(per_person: list[tuple[int, int]], seed: int) -> tuple[float, list[float]]:
    """Pooled flags/sessions, with a 95 % interval by resampling PEOPLE (sessions of one person are not independent)."""
    k = np.array([a for a, _ in per_person], dtype=float)
    n = np.array([b for _, b in per_person], dtype=float)
    keep = n > 0
    k, n = k[keep], n[keep]
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(N_BOOT):
        i = rng.integers(0, len(n), len(n))
        boots.append(k[i].sum() / n[i].sum())
    return round(float(k.sum() / n.sum()), 4), [round(float(np.quantile(boots, .025)), 4), round(float(np.quantile(boots, .975)), 4)]


def compare_rules(people: list[dict], budget: float = ALERT_BUDGET) -> dict:
    people = [p for p in people if len(p["pre"]) >= MIN_PRE]
    own = [own_scores(p) for p in people]
    counts = {"own": {"pre": [], "during": []}, "pop": {"pre": [], "during": []}}
    mostly_flagged = 0
    for i, p in enumerate(people):
        others = [q for j, q in enumerate(people) if j != i]
        # cutoffs fitted on OTHER people's pre-bed-rest (normal) sessions only
        own_cut = _cutoff([s for j, (pre, _d) in enumerate(own) if j != i for s in pre], budget)
        pop_train = [s for j, q in enumerate(people) if j != i
                     for s in population_scores(q, [o for k2, o in enumerate(people) if k2 not in (i, j)])[0]]
        pop_cut = _cutoff(pop_train, budget)
        o_pre, o_dur = own[i]
        p_pre, p_dur = population_scores(p, others)
        counts["own"]["pre"].append((sum(s >= own_cut for s in o_pre), len(o_pre)))
        counts["own"]["during"].append((sum(s >= own_cut for s in o_dur), len(o_dur)))
        counts["pop"]["pre"].append((sum(s >= pop_cut for s in p_pre), len(p_pre)))
        counts["pop"]["during"].append((sum(s >= pop_cut for s in p_dur), len(p_dur)))
        flagged = sum(s >= pop_cut for s in p_pre + p_dur)
        mostly_flagged += flagged > (len(p_pre) + len(p_dur)) / 2
    out = {"alert_budget": budget, "people": len(people), "evaluation": "leave one person out; cutoffs fitted on the other people's pre-bed-rest sessions only"}
    for phase, key in (("pre_bed_rest", "false_alert_rate"), ("during_bed_rest", "flag_rate")):
        out[phase] = {}
        for rule, name in (("own", "own_baseline"), ("pop", "population")):
            rate, ci = _rate(counts[rule]["pre" if phase == "pre_bed_rest" else "during"], seed=7)
            n = sum(b for _, b in counts[rule]["pre" if phase == "pre_bed_rest" else "during"])
            out[phase][name] = {key: rate, "ci95": ci, "sessions": int(n)}
    # The page prints this as evidence that one threshold keeps flagging the same people; when nobody is, the key is left out
    # (a "0 people ... keeps flagging the same individuals" sentence would say the opposite of the data).
    if mostly_flagged:
        out["people_flagged_by_population_rule_in_most_sessions"] = int(mostly_flagged)
    # the average can meet the budget while some individuals do not: per person, more than twice the budget on normal sessions
    # with about five normal sessions per person, ONE flag is already 20 % (over twice a 5 % budget), so compare with chance alone
    from ml.calibrate_cutoffs import expected_share_over_2x
    sizes = [np.zeros(n) for _k, n in counts["own"]["pre"]]
    out["people_over_twice_budget_before_bed_rest"] = {
        **{name: int(sum(k / n > 2 * budget for k, n in counts[rule]["pre"] if n))
           for rule, name in (("own", "own_baseline"), ("pop", "population"))},
        "expected_by_chance_alone": round(expected_share_over_2x(sizes, budget) * len(sizes), 1),
        "note": "With about five normal sessions per person one flag is 20 %, so this count is mostly chance; "
                "'expected_by_chance_alone' is what a rule flagging everyone at exactly the budget would give."}
    return out


# ------------------------------------------------------------------ (c) any of five

def any_of_five(raw_people: dict[str, list[dict]]) -> dict:
    r = wc.any_of_five(raw_people)
    n = r["scored"]
    return {"people": r["people"], "sessions": n, "flag_rate": round(r["any"] / n, 4),
            "per_measure": [{"measure": m, "label": FIVE_LABELS[m], "flag_rate": round(r["flags"][m] / n, 4)} for m in wc.MEASURES],
            "rule": "per measure, deviation >= 1.0 against the person's own pre-bed-rest sessions; sessions during and after bed rest"}


# ------------------------------------------------------------------ run

def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def evaluate(folder: Path, zip_path: Path | None = None, accessed: str | None = None) -> dict:
    raw = wc.load(folder)
    people = usable(raw)
    if len(people) < 3:
        raise SystemExit(f"only {len(people)} people with >= {MIN_SESSIONS} sessions in {folder}; is this the Campaign 3 folder?")
    return {
        "source": dict(SOURCE, accessed=accessed or date.today().isoformat(),
                       sha256=sha256_of(zip_path) if zip_path else None),
        "people": len(people),
        "pre_bed_rest_sessions": int(sum(len(p["pre"]) for p in people)),
        "icc": icc_table(people),
        "rules": compare_rules(people),
        "any_of_five": any_of_five(raw),
        "limits": LIMITS,
        "generated_by": "python -m ml.nasa_eval <unzipped Campaign 3 folder> --zip <zip>",
        "notes": "Aggregates and counts only; no per-session or per-person values. Run 1 (each person's first exposure) is dropped as practice.",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=Path, help="the unzipped MR085G_Campaign_3_WinSCAT folder")
    ap.add_argument("--zip", type=Path, help="the downloaded zip, to record its SHA-256")
    ap.add_argument("--accessed", help="date the data were downloaded (YYYY-MM-DD); default today")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    result = evaluate(a.folder, a.zip, a.accessed)
    a.out.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {a.out}")
    print(json.dumps({k: result[k] for k in ("people", "pre_bed_rest_sessions", "icc", "rules", "any_of_five")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
