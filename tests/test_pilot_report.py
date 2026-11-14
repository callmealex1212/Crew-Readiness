"""Task C4: ml/pilot_report.py reads the export + session sheet exactly as docs/PILOT.md defines them.

The fixture below is SYNTHETIC (ml/synth.py), written in the real file formats. It stands in for volunteers only so the
code can be tested before the pilot happens; no number from it may be quoted as a pilot result.
"""
import csv

import numpy as np
import pytest

from app.features import FEATURE_NAMES
from ml.pilot_report import build_report, load_pilot, main, render, suggest_population, variability
from ml.synth import Event, PopulationSpec, simulate_person


def write_fixture(tmp_path, n_people=8, magnitude=0.35, pop=PopulationSpec(), seed=3):
    """SYNTHETIC pilot: 12 sessions each, sessions 9-11 perturbed (events at 0-based 8..10), like docs/PILOT.md."""
    rng = np.random.default_rng(seed)
    sessions, sheet = [], []
    for p in range(1, n_people + 1):
        pid = f"pilot-{p:02d}"
        kind = "non_dominant_hand" if p % 2 else "counting_backwards"
        feats, _t = simulate_person(rng, 12, pop, (Event("step", 8, 3, magnitude),))
        for i, f in enumerate(feats, start=1):
            sessions.append({"pseudonym": pid, "session_number": i, **{k: f[k] for k in FEATURE_NAMES}})
            hot = 9 <= i <= 11
            sheet.append({"pseudonym": pid, "consent": "yes", "session_number": i,
                          "condition": "perturbed" if hot else "normal", "perturbation": kind if hot else "none", "issue": "none"})
    sp, sh = tmp_path / "pilot_sessions.csv", tmp_path / "session_sheet.csv"
    for path, rows in ((sp, sessions), (sh, sheet)):
        with open(path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    return sp, sh


def test_report_has_the_three_answers_and_the_limits(tmp_path):
    sp, sh = write_fixture(tmp_path)
    r = build_report(sp, sh)
    assert r["n_people"] == 8 and r["n_sessions"] == 96
    fa = r["false_alerts_on_normal"]["yellow"]
    assert fa["n"] > 0 and 0 <= fa["rate"] <= 1 and fa["ci95"][0] <= fa["rate"] <= fa["ci95"][1]
    de = r["detection_on_perturbed"]
    assert de["all"]["yellow"]["n"] == 24                      # 8 people x 3 perturbed sessions, all scored (sessions 9-11 follow 8 normal)
    assert set(de) == {"all", "non_dominant_hand", "counting_backwards"}
    assert de["all"]["yellow"]["rate"] > fa["rate"]            # a 35 % slowdown must be flagged more often than normal sessions are
    assert r["limits"] and "not astronauts" in render(r).lower()


def test_an_interval_never_collapses_to_a_point_with_few_people(tmp_path):
    de = build_report(*write_fixture(tmp_path))["detection_on_perturbed"]["all"]["yellow"]
    assert de["rate"] == 1.0 and de["ci95"][0] < 0.95          # 24 of 24 is "very likely high", not "certain"


def test_calibrating_sessions_are_not_counted(tmp_path):
    sp, sh = write_fixture(tmp_path)
    r = build_report(sp, sh)
    # sessions 1-5 build the baseline (CALIBRATING), so a person has at most sessions 6,7,8 and 12 as scored normals
    assert all(len(p["normal_scores"]) <= 4 for p in r["per_person"])


def test_export_and_sheet_must_describe_the_same_sessions(tmp_path):
    sp, sh = write_fixture(tmp_path)
    lines = sh.read_text().splitlines()
    sh.write_text("\n".join(lines[:-1]) + "\n")                # drop the last sheet row
    with pytest.raises(ValueError, match="disagree"):
        load_pilot(sp, sh)


def test_sheet_without_consent_or_with_a_bad_label_is_refused(tmp_path):
    sp, sh = write_fixture(tmp_path)
    text = sh.read_text()
    sh.write_text(text.replace(",yes,", ",no,", 1))
    with pytest.raises(ValueError, match="consent"):
        load_pilot(sp, sh)
    sh.write_text(text.replace("normal,none", "normal,non_dominant_hand", 1))
    with pytest.raises(ValueError, match="not allowed"):
        load_pilot(sp, sh)


def test_variability_matches_the_simulator_when_the_data_come_from_it(tmp_path):
    sp, sh = write_fixture(tmp_path, n_people=30, seed=8)
    v = variability(load_pilot(sp, sh))
    assert v["n_people"] == 30 and v["simulator_assumptions_hold"]
    assert 0.6 < v["iki_cv"]["ratio"] < 1.4


def test_variability_flags_a_wrong_simulator(tmp_path):
    sp, sh = write_fixture(tmp_path, n_people=30, seed=9, pop=PopulationSpec(iki_cv=0.20, resp_cv=0.30))
    v = variability(load_pilot(sp, sh))
    assert not v["simulator_assumptions_hold"]
    spec = suggest_population(v)
    assert spec.iki_cv > 0.14 and spec.resp_cv > 0.2           # moves toward what was measured


def test_calibration_only_with_enough_people(tmp_path):
    small = build_report(*write_fixture(tmp_path, n_people=3))
    assert small["calibration_on_normal"] is None
    (tmp_path / "b").mkdir()
    big = build_report(*write_fixture(tmp_path / "b", n_people=8))
    assert len(big["calibration_on_normal"]) == 3


def test_report_holds_only_aggregates_and_pseudonyms(tmp_path):
    import json
    r = build_report(*write_fixture(tmp_path))
    assert all(p["pseudonym"].startswith("pilot-") for p in r["per_person"])
    assert set(r) == {"source", "n_people", "n_sessions", "cutoffs", "false_alerts_on_normal", "detection_on_perturbed",
                      "calibration_on_normal", "per_person", "variability", "limits"}
    assert set(r["per_person"][0]) == {"pseudonym", "perturbation", "normal_scores", "perturbed_scores", "n_sessions", "n_low_quality"}
    assert not any(name in json.dumps(r) for name in FEATURE_NAMES if name.endswith("_ms") and name.startswith("task"))


def test_cli_explains_missing_files(tmp_path, capsys):
    assert main(["--sessions", str(tmp_path / "nope.csv"), "--sheet", str(tmp_path / "nope2.csv")]) == 1
    assert "export_pilot.py" in capsys.readouterr().err


def test_cli_writes_json(tmp_path, capsys):
    sp, sh = write_fixture(tmp_path)
    out = tmp_path / "r.json"
    assert main(["--sessions", str(sp), "--sheet", str(sh), "--out", str(out)]) == 0
    assert out.exists() and "False alerts" in capsys.readouterr().out
