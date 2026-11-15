"""Task R2: fault injection, long-mission soak, clock jump. The Evidence page renders app/reliability_data.json, and only that."""
import html
import json
import re
import sys
from pathlib import Path

import pytest

from app.features import ValidationError, validate_session_payload
from tests.conftest import valid_features, valid_payload

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import soak  # noqa: E402

DATA = json.loads((ROOT / "app" / "reliability_data.json").read_text(encoding="utf-8"))


# ---- the bugs fault injection found in app/features.py, now refused with a 400 ----
@pytest.mark.parametrize("name, value", [
    ("pause_count", float("nan")), ("pause_count", float("inf")), ("keystroke_count", float("-inf")),
    ("iki_median_ms", float("nan")), ("iki_median_ms", float("inf")), ("iki_median_ms", 10**400), ("retry_count", 10**30),
])
def test_non_finite_and_huge_numbers_are_refused(name, value):
    with pytest.raises(ValidationError):
        validate_session_payload(valid_payload(**{name: value}))


@pytest.mark.parametrize("field, value", [("task_type", ["docking_checklist_v1"]), ("task_type", {"a": 1}),
                                          ("profile_id", "\ud800"), ("profile_id", "x" * 1000), ("profile_id", "a\nb")])
def test_odd_ids_are_refused_not_crashed(field, value):
    with pytest.raises(ValidationError):
        validate_session_payload(dict(valid_payload(), **{field: value}))


def test_the_sessions_endpoint_answers_400_to_nan_in_raw_json(client):
    raw = json.dumps(valid_payload(pause_count=float("nan")), allow_nan=True)
    assert client.post("/api/sessions", data=raw, content_type="application/json").status_code == 400


def test_a_short_fuzz_run_does_not_crash_the_sessions_endpoint():
    r = soak.fuzz(400, seed=11)
    assert not [e for e in r["crash_examples"] if e["endpoint"] == "/api/sessions"], r["crash_examples"]


@pytest.mark.xfail(strict=True, reason="OPEN, reported by R2: /api/attention passes a lone surrogate profile_id to SQLite "
                                       "(app/api.py, not app/features.py). Fix there; this test then passes and must be un-marked.")
def test_attention_endpoint_refuses_a_lone_surrogate_profile_id(client):
    raw = json.dumps({"profile_id": "\ud800", "trials": 10, "median_rt_ms": 300, "premature_count": 0, "miss_count": 0})
    assert client.post("/api/attention", data=raw.encode("utf-8", "surrogatepass"),
                       content_type="application/json").status_code in (400, 404)


# ---- the runners work (tiny sizes) ----
def test_soak_runner_small():
    r = soak.soak(people=2, days=3, per_day=3)
    assert r["sessions_stored"] == 18 and r["scoring_ms"]["calls"] == 18 and r["database_bytes"] > 0


def test_clock_jump_gives_the_same_answers():
    r = soak.clock_jump()
    assert r["crashes"] == 0 and r["same_answers_as_forward_clock"]


# ---- the shipped file ----
def test_the_shipped_file_is_a_full_run_and_regenerable():
    assert DATA["generated_by"] == "python -m ml.export_reliability" and DATA["quick"] is False
    assert DATA["fault_injection"]["payloads"] == 1000
    assert (DATA["soak"]["people"], DATA["soak"]["days"], DATA["soak"]["sessions_per_day"]) == (6, 700, 3)
    assert DATA["soak"]["sessions_stored"] == 6 * 700 * 3
    for phrase in ("simulated data", "Not flight hardware", "not radiation-tested"):
        assert phrase in DATA["limits"]


def section(client):
    page = client.get("/evidence").data.decode()
    m = re.search(r'<section class="section" id="reliability">(.*?)</section>', page, re.S)
    assert m, "the Reliability section must render when the file exists"
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1))))


def test_the_page_shows_the_numbers_from_the_file(client):
    t = section(client)
    fz, fx, sk, cj = DATA["fault_injection"], DATA["fault_injection_extra_seeds"], DATA["soak"], DATA["clock_jump"]
    assert f"{fz['payloads']} malformed or hostile requests" in t and f"{fz['crashes']} crash" in t
    assert f"{fx['payloads']} more requests" in t and f"{fx['crashes']} crash" in t
    assert f"{sk['sessions_stored']} sessions stored" in t
    assert f"scoring {sk['scoring_ms']['median']} ms median, {sk['scoring_ms']['p95']} ms p95, {sk['scoring_ms']['max']} ms max" in t
    assert f"{sk['scoring_ms_first_100_median']} ms, then {sk['scoring_ms_last_100_median']} ms" in t
    assert f"{sk['database_bytes'] / 1048576:.1f} MB; {sk['peak_memory_mb']} MB" in t
    assert f"{cj['crashes']} crash" in t
    assert DATA["limits"] in t and "python -m ml.export_reliability" in t
    if fz["crashes"] or fx["crashes"]:
        assert "Open issue." in t and "Reported, not yet fixed." in t


def test_no_reliability_section_without_a_file(client, monkeypatch, tmp_path):
    from app import views
    monkeypatch.setattr(views, "RELIABILITY_FILE", tmp_path / "missing.json")
    assert 'id="reliability"' not in client.get("/evidence").data.decode()
