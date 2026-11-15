"""Task R3: backup and restore. Round trip is exact; damaged files, unknown fields, text and non-empty databases are refused."""
import json

import pytest

from app import backup, create_app
from app.db import get_db, init_db
from app.features import assess_quality
from tests.conftest import valid_features

SLOW = valid_features(iki_median_ms=330.0, iki_iqr_ms=140.0, pause_count=4, pause_total_ms=9000.0,
                      checklist_response_median_ms=2600.0)


@pytest.fixture
def rich_app(seeded_app):
    """The demo crew plus everything a backup must carry: a flagged run accepted as the new normal, an attention result,
    and a low-quality session with a quality note."""
    c = seeded_app.test_client()
    for _ in range(3):
        assert c.post("/api/sessions", json={"profile_id": "plt-okafor", "task_type": "docking_checklist_v1",
                                             "features": SLOW}).status_code == 201
    assert c.post("/api/readiness/plt-okafor/accept-new-normal").status_code == 200
    assert c.post("/api/attention", json={"profile_id": "fe-sato", "trials": 10, "median_rt_ms": 301.5,
                                          "premature_count": 1, "miss_count": 0}).status_code == 201
    assert c.post("/api/sessions", json={"profile_id": "fe-sato", "task_type": "docking_checklist_v1",
                                         "features": valid_features(keystroke_count=40)}).status_code == 201
    return seeded_app


def empty_app(tmp_path, name="restored.sqlite3"):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / name), "AUTO_SEED": False})
    with app.app_context():
        init_db()
    return app


def views(app):
    c = app.test_client()
    ids = [p["id"] for p in c.get("/api/profiles").json["profiles"]]
    return {"all": c.get("/api/readiness").json, "mission": c.get("/api/mission").json,
            **{i: c.get(f"/api/readiness/{i}").json for i in ids}}


def write(rich_app, tmp_path):
    path = tmp_path / "backup.json"
    with rich_app.app_context():
        backup.write_backup(get_db(), path)
    return path


def test_round_trip_gives_identical_readiness(rich_app, tmp_path):
    path = write(rich_app, tmp_path)
    doc = json.loads(path.read_text())
    tables = doc["payload"]["tables"]
    assert any(s["accepted_at"] for s in tables["sessions"]), "the accepted-as-new-normal marker must be in the backup"
    assert any(s["quality_notes"] for s in tables["sessions"]) and tables["attention_results"]
    dst = empty_app(tmp_path)
    with dst.app_context():
        backup.restore(get_db(), backup.read_backup(path))
    assert views(dst) == views(rich_app)


def test_the_backup_holds_only_the_stored_columns(rich_app, tmp_path):
    tables = json.loads(write(rich_app, tmp_path).read_text())["payload"]["tables"]
    with rich_app.app_context():
        for table, rows in tables.items():
            stored = [r[1] for r in get_db().execute(f"PRAGMA table_info({table})")]
            assert sorted(backup.SCHEMA[table]) == sorted(stored), table
            assert all(set(r) == set(stored) for r in rows)


def test_every_flipped_byte_is_refused(rich_app, tmp_path):
    raw = write(rich_app, tmp_path).read_bytes()
    bad = tmp_path / "bad.json"
    for pos in range(0, len(raw), max(1, len(raw) // 400)):          # about 400 positions across the whole file
        flipped = bytearray(raw)
        flipped[pos] ^= 0x01
        bad.write_bytes(bytes(flipped))
        with pytest.raises(backup.BackupError):
            backup.read_backup(bad)


def resealed(rich_app, tmp_path, mutate):
    """A backup changed and then re-checksummed, as a careless editor or an attacker would: the checksum alone cannot catch it."""
    doc = json.loads(write(rich_app, tmp_path).read_text())
    mutate(doc["payload"])
    doc["sha256"] = backup.checksum(doc["payload"])
    path = tmp_path / "resealed.json"
    path.write_text(json.dumps(doc))
    return path


@pytest.mark.parametrize("mutate, reason", [
    (lambda p: p["tables"]["sessions"][0].update(typed_text="CORRIDOR CLEAR"), "unknown fields"),
    (lambda p: p["tables"]["sessions"][0].update(iki_median_ms="CORRIDOR CLEAR"), "iki_median_ms"),
    (lambda p: p["tables"]["sessions"][0].update(quality_notes="he typed: TARGET LOCK"), "quality_notes"),
    (lambda p: p["tables"]["profiles"][0].update(notes="free text"), "unknown fields"),
    (lambda p: p["tables"].update(keystrokes=[]), "unknown or missing tables"),
    (lambda p: p.update(extra=1), "top-level"),
    (lambda p: p["tables"]["sessions"][0].update(pause_count=10**12), "pause_count"),
    (lambda p: p["tables"]["sessions"][0].update(iki_median_ms=True), "iki_median_ms"),
    (lambda p: p["tables"]["profiles"][0].update(display_name="line one\nline two"), "display_name"),
])
def test_text_and_unknown_fields_are_refused_even_with_a_valid_checksum(rich_app, tmp_path, mutate, reason):
    with pytest.raises(backup.BackupError, match=reason):
        backup.read_backup(resealed(rich_app, tmp_path, mutate))


def test_nan_is_refused(rich_app, tmp_path):
    path = write(rich_app, tmp_path)
    path.write_text(path.read_text().replace('"iki_iqr_ms": 75.0', '"iki_iqr_ms": NaN', 1))
    with pytest.raises(backup.BackupError):
        backup.read_backup(path)


def test_restore_only_into_an_empty_database(rich_app, tmp_path):
    path = write(rich_app, tmp_path)
    with rich_app.app_context():
        before = backup.export_backup(get_db())
        with pytest.raises(backup.BackupError, match="not empty"):
            backup.restore(get_db(), backup.read_backup(path))
        assert backup.export_backup(get_db()) == before


def test_restore_is_all_or_nothing(rich_app, tmp_path):
    def orphan(p):  # a session whose person is not in the file: valid shape, refused by the database
        p["tables"]["profiles"] = [r for r in p["tables"]["profiles"] if r["id"] != "cdr-vega"]
    dst = empty_app(tmp_path)
    with dst.app_context():
        with pytest.raises(backup.BackupError, match="nothing was restored"):
            backup.restore(get_db(), backup.read_backup(resealed(rich_app, tmp_path, orphan)))
        assert backup.is_empty(get_db())


def test_the_allowed_quality_notes_are_exactly_the_ones_the_app_writes():
    _, few = assess_quality(valid_features(keystroke_count=10))
    _, retries = assess_quality(valid_features(retry_count=50))
    assert set(few) | set(retries) == backup.QUALITY_NOTES


def test_cli_round_trip_and_refusals(rich_app, tmp_path):
    path = tmp_path / "cli.json"
    out = rich_app.test_cli_runner().invoke(args=["export-backup", str(path)])
    assert out.exit_code == 0 and "Not encrypted" in out.output
    refused = rich_app.test_cli_runner().invoke(args=["import-backup", str(path)])
    assert refused.exit_code == 1 and "not empty" in refused.output
    dst = empty_app(tmp_path)
    ok = dst.test_cli_runner().invoke(args=["import-backup", str(path)])
    assert ok.exit_code == 0 and "Restored" in ok.output
    assert views(dst) == views(rich_app)
