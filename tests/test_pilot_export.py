"""Task F1: the pilot export carries aggregate timing numbers only: no names, no typed text, no free text."""
import csv
import hashlib
import importlib.util
import re
from pathlib import Path

import pytest

from app.features import FEATURE_NAMES
from tests.conftest import valid_features

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("export_pilot", ROOT / "scripts" / "export_pilot.py")
export_pilot = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(export_pilot)

REAL_NAME = "Jane Realname"   # a display name someone typed by mistake; must never reach the CSV
TYPED = "CORRIDOR CLEAR"      # a checklist phrase; must never reach the CSV (or the database)


def add_profile(app, pid, name, role="Volunteer"):
    result = app.test_cli_runner().invoke(args=["add-profile", pid, name, role])
    assert result.exit_code == 0, result.output


def post(client, pid, **overrides):
    body = {"profile_id": pid, "task_type": "docking_checklist_v1", "features": valid_features(**overrides)}
    assert client.post("/api/sessions", json=body).status_code == 201


@pytest.fixture
def pilot_db(seeded_app):
    """The demo crew plus three team_test profiles: two proper pseudonyms and one named by mistake."""
    add_profile(seeded_app, "pilot-01", REAL_NAME, "Pilot")
    add_profile(seeded_app, "pilot-02", "Volunteer two")
    add_profile(seeded_app, "jane-realname", "Jane R")
    c = seeded_app.test_client()
    for i in range(3):
        post(c, "pilot-01", iki_median_ms=200.0 + i, pause_count=i)
    post(c, "pilot-02", iki_median_ms=250.5)
    post(c, "jane-realname")
    # the server refuses typed text, so it cannot be stored in the first place
    bad = {"profile_id": "pilot-01", "task_type": "docking_checklist_v1",
           "features": valid_features(), "typed_text": TYPED}
    assert c.post("/api/sessions", json=bad).status_code == 400
    return Path(seeded_app.config["DATABASE"])


def run_export(db, tmp_path, *extra):
    out = tmp_path / "pilot.csv"
    code = export_pilot.main(["--db", str(db), "--out", str(out), *extra])
    return code, out


def test_export_has_only_pseudonym_session_number_and_the_nine_features(pilot_db, tmp_path):
    code, out = run_export(pilot_db, tmp_path)
    assert code == 0
    with open(out, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert tuple(rows[0]) == ("pseudonym", "session_number") + FEATURE_NAMES
    for row in rows[1:]:
        assert re.fullmatch(r"pilot-\d{2}", row[0]), row[0]
        for cell in row[1:]:          # every other cell is a plain number: there is no room for text
            float(cell)


def test_export_contains_no_names_roles_typed_text_or_other_profiles(pilot_db, tmp_path):
    _, out = run_export(pilot_db, tmp_path)
    text = out.read_text(encoding="utf-8")
    for forbidden in (REAL_NAME, "Jane", "Volunteer", "Pilot,", TYPED, "jane-realname",
                      "plt-okafor", "cdr-vega", "synthetic", "live", "Z,"):
        assert forbidden not in text, forbidden
    # no timestamps either (time of day is not part of the export)
    assert not re.search(r"\d{4}-\d{2}-\d{2}", text)


def test_sessions_are_numbered_per_person_in_submission_order(pilot_db, tmp_path):
    _, out = run_export(pilot_db, tmp_path)
    with open(out, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    p1 = [r for r in rows if r["pseudonym"] == "pilot-01"]
    assert [r["session_number"] for r in p1] == ["1", "2", "3"]
    assert [float(r["iki_median_ms"]) for r in p1] == [200.0, 201.0, 202.0]
    assert [r["pause_count"] for r in p1] == ["0", "1", "2"]
    assert [(r["pseudonym"], r["session_number"]) for r in rows if r["pseudonym"] == "pilot-02"] == [("pilot-02", "1")]


def test_a_withdrawn_volunteer_can_be_excluded(pilot_db, tmp_path):
    _, out = run_export(pilot_db, tmp_path, "--exclude", "pilot-01")
    assert "pilot-01" not in out.read_text(encoding="utf-8")


def test_the_database_is_only_read(pilot_db, tmp_path):
    before = hashlib.sha256(pilot_db.read_bytes()).hexdigest()
    run_export(pilot_db, tmp_path)
    assert hashlib.sha256(pilot_db.read_bytes()).hexdigest() == before


def test_no_pilot_data_is_an_error_not_an_empty_file(seeded_app, tmp_path):
    code, out = run_export(Path(seeded_app.config["DATABASE"]), tmp_path)
    assert code == 1 and not out.exists()
    code, _ = run_export(tmp_path / "missing.sqlite3", tmp_path)
    assert code == 1
