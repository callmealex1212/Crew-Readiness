"""H2: the missed check-in watchdog. It suggests someone look in; it never changes the readiness advisory and never alarms on a wrong clock."""
from datetime import datetime, timedelta, timezone

from app.mission import check_in_watchdog

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


def a(role, name, hours_ago):
    last = None if hours_ago is None else (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"role": role, "display_name": name, "last_check_in": last}


def test_everyone_recent_is_ok():
    w = check_in_watchdog([a("Pilot", "A", 2), a("Monitor", "B", 35)], 36, NOW)
    assert w["level"] == "OK" and w["overdue"] == [] and w["messages"] == []


def test_overdue_names_the_person_the_hours_and_says_nothing_is_necessarily_wrong():
    w = check_in_watchdog([a("Pilot", "A", 2), a("Comms", "B", 61)], 36, NOW)
    assert w["level"] == "OVERDUE" and [o["display_name"] for o in w["overdue"]] == ["B"] and w["overdue"][0]["hours_since"] == 61
    text = " ".join(w["messages"] + w["suggested_actions"])
    assert "61 hours" in text and "looking in" in text and "does not mean anything is wrong" in text
    for banned in ("unconscious", "fatigue", "impaired", "unfit", "diagnos"):
        assert banned not in text.lower()


def test_no_check_in_at_all_is_overdue_not_a_crash():
    w = check_in_watchdog([a("Pilot", "A", None)], 36, NOW)
    assert w["level"] == "OVERDUE" and w["overdue"][0]["hours_since"] is None and "No check-in recorded yet" in w["messages"][0]


def test_a_future_or_unreadable_time_is_a_clock_problem_never_negative_hours_or_overdue():
    w = check_in_watchdog([a("Pilot", "A", -5), {"role": "Comms", "display_name": "B", "last_check_in": "not a time"}], 36, NOW)
    assert w["level"] == "OK" and w["overdue"] == [] and {c["reason"] for c in w["clock_check"]} == {"future", "unreadable"}
    assert "Check the device clock" in " ".join(w["messages"])


def test_exactly_at_the_interval_is_not_overdue():
    assert check_in_watchdog([a("Pilot", "A", 36)], 36, NOW)["level"] == "OK"


def test_mission_api_has_the_watchdog_and_does_not_change_the_advisory(client):
    d = client.get("/api/mission").get_json()
    w = d["watchdog"]
    assert w["interval_hours"] == 36 and w["level"] == "OVERDUE"
    assert [o["display_name"] for o in w["overdue"]] == ["Tomas Ibarra"]          # the seeded crew member with no recent check-in
    assert d["advisory"]["level"] == "CHECK_IN"                                     # unchanged: Okafor YELLOW; non-critical roles never move it
    assert not any("Ibarra" in m for m in d["advisory"]["messages"])
