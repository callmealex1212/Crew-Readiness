"""Task N1: ml/nasa_eval.py. Uses a small SYNTHETIC fixture in the WinSCAT file layout. NO real NASA rows are in this repository."""
import json
import re
from pathlib import Path

import numpy as np
import pytest

from ml import nasa_eval as ne

ROOT = Path(__file__).resolve().parents[1]
HEADER = "ID,Campaign,Subject,Test,Run,Test_Phase,BR_Day,Date,Time,CPTRT,CPTA,CPTL,MTHRT,MTHA,MTSRT,MTSA,CDDRT,CDDA\n"
MARKER = 777.77   # a raw value that must never appear in the output


def write_fixture(folder: Path, n_people=8, slow_person=False, seed=0):
    """SYNTHETIC: people with clearly different typical speeds (between-person variation) and small session-to-session noise.
    12 runs each: 6 before bed rest (run 1 = practice), 4 during, 2 after."""
    rng = np.random.default_rng(seed)
    folder.mkdir(parents=True, exist_ok=True)
    for p in range(n_people):
        level = 350 + 60 * p + (400 if slow_person and p == n_people - 1 else 0)
        rows = []
        for run in range(1, 13):
            phase = "PRE_TEST" if run <= 6 else ("IN_TEST" if run <= 10 else "POST_TEST")
            rts = [level * f * (1 + rng.normal(0, 0.03)) for f in (1.0, 3.5, 3.8, 2.0)]
            if p == 0 and run == 1:
                rts[0] = MARKER
            rows.append(f"{run},CXA,{1000 + p},Nasa1,{run},{phase},{run},1/{run}/2005,10:00:00,"
                        f"{rts[0]:.2f},95,0,{rts[1]:.2f},90,{rts[2]:.2f},100,{rts[3]:.2f},100\n")
        (folder / f"MR085G_Campaign_X_WinSCAT_CXA_{1000 + p}").write_text(HEADER + "".join(rows))
    (folder / "MR085G_Campaign_X_WinSCAT_All").write_text(HEADER)       # a summary file, not a person
    return folder


@pytest.fixture
def result(tmp_path):
    folder = write_fixture(tmp_path / "fixture")
    z = tmp_path / "fixture.zip"
    z.write_bytes(b"synthetic zip stand-in")
    return ne.evaluate(folder, z, accessed="2026-11-15")


def test_output_has_the_contract_shape(result):
    assert set(result) >= {"source", "people", "pre_bed_rest_sessions", "icc", "rules", "any_of_five", "limits"}
    assert set(result["source"]) >= {"title", "doi", "url", "accessed", "sha256"} and result["source"]["doi"] == "10.83263/sbne-th55"
    assert result["people"] == 8 and result["pre_bed_rest_sessions"] == 8 * 5          # run 1 dropped
    assert [m["measure"] for m in result["icc"]] == list(ne.RT_MEASURES)
    r = result["rules"]
    assert r["alert_budget"] == 0.05
    for phase, key in (("pre_bed_rest", "false_alert_rate"), ("during_bed_rest", "flag_rate")):
        for rule in ("own_baseline", "population"):
            v = r[phase][rule]
            assert 0 <= v[key] <= 1 and v["ci95"][0] <= v[key] <= v["ci95"][1]
    assert r.get("people_flagged_by_population_rule_in_most_sessions", 1) >= 1     # left out when 0 (the page would misread a 0)
    assert 0 <= result["any_of_five"]["flag_rate"] <= 1 and len(result["any_of_five"]["per_measure"]) == 5


def test_output_holds_aggregates_only(result):
    text = json.dumps(result)
    assert str(MARKER) not in text and "777.7" not in text                            # no raw value
    assert not re.search(r"\d{1,2}/\d{1,2}/20\d\d|10:00:00|CXA|100[0-9]\b", text)     # no session dates, times or subject ids


def test_the_zip_checksum_is_recorded(result, tmp_path):
    assert result["source"]["sha256"] == ne.sha256_of(tmp_path / "fixture.zip")


def test_icc_is_high_when_people_differ_and_low_when_they_do_not():
    rng = np.random.default_rng(1)
    differ = [np.full(5, 100.0 * i) + rng.normal(0, 1, 5) for i in range(1, 9)]
    same = [100 + rng.normal(0, 10, 5) for _ in range(8)]
    assert ne.icc1(differ) > 0.95
    assert ne.icc1(same) < 0.2


def test_fixture_people_differ_so_the_icc_is_high(result):
    assert all(m["icc"] > 0.9 and m["ci95"][0] <= m["icc"] <= m["ci95"][1] for m in result["icc"])


def test_a_cutoff_of_zero_never_flags_every_normal_session():
    assert ne._cutoff([0.0] * 97 + [0.5, 1.0, 2.0], 0.05) > 0


def test_one_threshold_for_everyone_keeps_flagging_a_naturally_slow_person(tmp_path):
    """The method difference the page explains: a person who is simply slower than others is flagged again and again by a
    population threshold, but not by their own baseline."""
    res = ne.evaluate(write_fixture(tmp_path / "slow", slow_person=True), None, accessed="2026-11-15")
    assert res["rules"]["people_flagged_by_population_rule_in_most_sessions"] >= 1
    assert res["rules"]["pre_bed_rest"]["own_baseline"]["false_alert_rate"] < res["rules"]["pre_bed_rest"]["population"]["false_alert_rate"]


def test_any_of_five_matches_the_data_search_script(tmp_path):
    folder = write_fixture(tmp_path / "f")
    raw = ne.wc.load(folder)
    r = ne.wc.any_of_five(raw)
    out = ne.any_of_five(raw)
    assert out["sessions"] == r["scored"] and out["flag_rate"] == round(r["any"] / r["scored"], 4)


def test_too_little_data_is_refused(tmp_path):
    with pytest.raises(SystemExit):
        ne.evaluate(write_fixture(tmp_path / "tiny", n_people=2), None)


# ---- the shipped results file (from the real NASA data, run locally; the data itself is not in the repository) ----
SHIPPED = ROOT / "app" / "nasa_results.json"


@pytest.mark.skipif(not SHIPPED.exists(), reason="no NASA results file (removed until the terms are confirmed)")
def test_the_shipped_file_credits_nasa_and_states_its_limits():
    d = json.loads(SHIPPED.read_text(encoding="utf-8"))
    assert d["source"]["doi"] == "10.83263/sbne-th55" and "nlsp.nasa.gov" in d["source"]["url"]
    assert re.fullmatch(r"[0-9a-f]{64}", d["source"]["sha256"])
    limits = " ".join(d["limits"])
    for phrase in ("not our typing task", "days to weeks apart", "only a few sessions", "not validation of the product",
                   "says nothing about health", "never impairment"):
        assert phrase in limits, phrase
    assert d["people"] >= 20 and d["rules"]["alert_budget"] == 0.05


@pytest.mark.skipif(not SHIPPED.exists(), reason="no NASA results file (removed until the terms are confirmed)")
def test_every_number_in_nasa_data_md_comes_from_the_results_file():
    d = json.loads(SHIPPED.read_text(encoding="utf-8"))
    doc = re.sub(r"\s+", " ", (ROOT / "docs" / "NASA_DATA.md").read_text(encoding="utf-8"))
    pct = lambda x: f"{x * 100:.0f} %"            # noqa: E731
    pct1 = lambda x: f"{x * 100:.1f} %"           # noqa: E731
    assert f"{d['people']} people" in doc
    for m in d["icc"]:
        assert f"**{pct(m['icc'])}** ({pct(m['ci95'][0])} to {pct(m['ci95'][1])})" in doc, m["measure"]
    r = d["rules"]
    for phase, key in (("pre_bed_rest", "false_alert_rate"), ("during_bed_rest", "flag_rate")):
        for rule in ("own_baseline", "population"):
            v = r[phase][rule]
            assert f"**{pct1(v[key])}** ({pct1(v['ci95'][0])} to {pct1(v['ci95'][1])})" in doc, (phase, rule)
    a = d["any_of_five"]
    per = [m["flag_rate"] for m in a["per_measure"]]
    assert f"**{pct(a['flag_rate'])}**" in doc and f"{pct(min(per))} to {pct(max(per))} for one measure" in doc


@pytest.mark.skipif(not SHIPPED.exists(), reason="no NASA results file (removed until the terms are confirmed)")
def test_the_paste_ready_nasa_answer_matches_the_results_file():
    d = json.loads(SHIPPED.read_text(encoding="utf-8"))
    doc = re.sub(r"\s+", " ", (ROOT / "docs" / "NASA_DATA.md").read_text(encoding="utf-8"))
    iccs = [m["icc"] for m in d["icc"]]
    r = d["rules"]
    assert f"On {d['people']} people" in doc
    assert f"an intraclass correlation of {min(iccs) * 100:.0f} % to {max(iccs) * 100:.0f} % across {dict([(4, 'four')]).get(len(iccs), len(iccs))} measures" in doc
    assert f"kept its budget before bed rest ({r['pre_bed_rest']['own_baseline']['false_alert_rate'] * 100:.1f} %)" in doc
    assert r["during_bed_rest"]["own_baseline"]["flag_rate"] == 0 and "flagged none of the bed-rest sessions" in doc


# ---- task N4: docs/SUBMISSION.md copies its blocks from the source docs, and its numbers come from result files ----
SUB = (ROOT / "docs" / "SUBMISSION.md").read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    """The body under a '## heading' line, up to the next '## ' heading."""
    m = re.search(r"^## " + re.escape(heading) + r"[^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    assert m, heading
    return m.group(1).strip()


@pytest.mark.parametrize("field, source", [
    ("Use of Super Intelligence (SI)", "AI_USE.md"),
    ("NASA Data", "NASA_DATA.md"),
    ("Space Agency Partner Data and Other References", "REFERENCES.md"),
])
def test_submission_fields_are_pasted_from_their_source_docs(field, source):
    src = (ROOT / "docs" / source).read_text(encoding="utf-8")
    assert _section(SUB, field) == _section(src, "Paste-ready answer"), f"{field} differs from the paste-ready block in docs/{source}"


def test_only_the_two_agreed_placeholders_remain():
    assert set(re.findall(r"\[[A-Z][A-Z ]{3,}[^\]]*\]", SUB)) == {"[TEAM NAME]", "[EXACT CHALLENGE TITLE FROM THE NASA SPACE APPS LIST]"}


def test_summary_is_within_the_suggested_length():
    assert 50 <= len(_section(SUB, "High-Level Project Summary").split()) <= 200


def test_baseline_poisoning_numbers_match_ml_results():
    ml = (ROOT / "docs" / "ML_RESULTS.md").read_text(encoding="utf-8")
    keep = re.search(r"\| 20 % \| keep all \(today\) \| ([\d.]+) \|.*\| \*\*([\d.]+)\*\* \|", ml)
    excl = re.search(r"\| 20 % \| exclude flagged.*\| \*\*([\d.]+)\*\* \|", ml)
    assert f"from {keep.group(1)} to {keep.group(2)} by the fifteenth" in SUB and f"held it at {excl.group(1)}" in SUB


@pytest.mark.skipif(not SHIPPED.exists(), reason="no NASA results file (removed until the terms are confirmed)")
def test_nasa_numbers_in_the_submission_match_the_results_file():
    d = json.loads(SHIPPED.read_text(encoding="utf-8"))
    iccs = [m["icc"] for m in d["icc"]]
    text = re.sub(r"\s+", " ", SUB)
    assert f"NASA bed-rest data ({d['people']} people" in text
    assert f"an intraclass correlation of {min(iccs) * 100:.0f} % to {max(iccs) * 100:.0f} %)" in text
    assert f"kept its budget before bed rest ({d['rules']['pre_bed_rest']['own_baseline']['false_alert_rate'] * 100:.1f} %)" in text
