"""Task R1: "Health of the monitor". Every check passes on a healthy app and fails, with its reason, when broken."""
import sqlite3
from datetime import datetime, timezone

import pytest

from app import scoring, selftest
from app.db import get_db

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)


def by_id(result):
    return {c["id"]: c for c in result["checks"]}


def test_all_checks_pass_on_a_healthy_app(seeded_app):
    with seeded_app.app_context():
        before = get_db().execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
        r = selftest.run_selftest()
        after = get_db().execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
    assert r["ok"], r
    assert set(by_id(r)) == {"database", "scoring", "clock", "network", "version"}
    assert before == after, "the database check must not keep its test row"
    assert "says nothing about any crew member" in r["does_not_show"]


# ---- database ----
def test_database_check_fails_when_it_cannot_write(seeded_app, monkeypatch):
    path = seeded_app.config["DATABASE"]
    ro = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    monkeypatch.setattr(selftest, "get_db", lambda: ro)
    with seeded_app.app_context():
        c = by_id(selftest.run_selftest(NOW))["database"]
    assert not c["ok"] and "the check itself failed" in c["detail"]


# ---- scoring ----
def test_the_fixture_is_the_hand_worked_example():
    typing, pauses, checklist = (2.0 + 1.0) / 2, 0.0, 2.0
    assert selftest.FIXTURE_EXPECTED_SCORE == pytest.approx(0.4 * typing + 0.3 * pauses + 0.3 * checklist)
    assert selftest.FIXTURE_EXPECTED_BAND == "YELLOW"


def test_scoring_check_fails_if_the_scoring_changes(seeded_app, monkeypatch):
    monkeypatch.setitem(scoring.GROUP_WEIGHTS, "typing", 0.5)   # someone edits a weight
    with seeded_app.app_context():
        c = by_id(selftest.run_selftest(NOW))["scoring"]
    assert not c["ok"] and "expected 1.2 YELLOW" in c["detail"]


# ---- clock ----
def test_clock_before_2024_fails(seeded_app):
    with seeded_app.app_context():
        c = by_id(selftest.run_selftest(datetime(2023, 6, 1, tzinfo=timezone.utc)))["clock"]
    assert not c["ok"] and "before 2024" in c["detail"]


def test_clock_behind_the_latest_stored_session_fails(seeded_app):
    with seeded_app.app_context():
        db = get_db()
        db.execute("UPDATE sessions SET created_at = '2026-11-20T00:00:00Z' WHERE id = (SELECT MAX(id) FROM sessions)")
        db.commit()
        c = by_id(selftest.run_selftest(NOW))["clock"]
    assert not c["ok"] and "jumped backwards" in c["detail"]


def test_clock_within_a_day_of_the_latest_session_passes(seeded_app):
    with seeded_app.app_context():
        db = get_db()
        db.execute("UPDATE sessions SET created_at = '2026-11-15T06:00:00Z' WHERE id = (SELECT MAX(id) FROM sessions)")
        db.commit()
        assert by_id(selftest.run_selftest(NOW))["clock"]["ok"]


def test_clock_with_no_sessions_passes(app):
    with app.app_context():
        c = by_id(selftest.run_selftest(NOW))["clock"]
    assert c["ok"] and "no sessions stored" in c["detail"]


# ---- network ----
def test_network_check_fails_on_a_page_that_loads_from_another_host(seeded_app, tmp_path):
    (tmp_path / "templates").mkdir()
    (tmp_path / "static" / "js").mkdir(parents=True)
    (tmp_path / "templates" / "bad.html").write_text('<script src="https://cdn.example.com/x.js"></script>')
    (tmp_path / "static" / "js" / "bad.js").write_text('fetch("https://api.example.com/data")')
    with seeded_app.app_context():
        ok, detail = selftest.check_no_outside_network(tmp_path)
    assert not ok and "cdn.example.com" in detail and "api.example.com" in detail


def test_external_loads_matches_only_loads_not_plain_links():
    assert selftest.external_loads('<link rel="stylesheet" href="https://fonts.example/x.css">') == ["https://fonts.example/x.css"]
    assert selftest.external_loads('<a href="https://ntrs.nasa.gov/">a source</a>') == []


# ---- version ----
def test_version_check_fails_without_a_version(seeded_app):
    seeded_app.config["APP_VERSION"] = None
    with seeded_app.app_context():
        c = by_id(selftest.run_selftest(NOW))["version"]
    assert not c["ok"]


# ---- the three ways to see it ----
def test_api_endpoint(client):
    r = client.get("/api/selftest")
    assert r.status_code == 200
    assert r.json["ok"] is True and len(r.json["checks"]) == 5
    assert all({"id", "name", "ok", "detail"} <= set(c) for c in r.json["checks"])


def test_cli_exit_codes(seeded_app, monkeypatch):
    runner = seeded_app.test_cli_runner()
    ok = runner.invoke(args=["selftest"])
    assert ok.exit_code == 0 and "All checks passed." in ok.output and "What this does not show" in ok.output
    monkeypatch.setattr(selftest, "EARLIEST_SANE", datetime(2999, 1, 1, tzinfo=timezone.utc))   # pretend the clock is wrong
    bad = runner.invoke(args=["selftest"])
    assert bad.exit_code == 1 and "FAIL  System clock is sane" in bad.output


def test_status_page_is_linked_from_about_but_not_the_top_nav(client):
    page = client.get("/status")
    assert page.status_code == 200 and b"What it does not show" in page.data and b"/static/js/status.js" in page.data
    assert b'href="/status"' in client.get("/about").data
    assert b'href="/status"' not in client.get("/dashboard").data   # the shared nav does not list it
