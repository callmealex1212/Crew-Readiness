"""
SPEC for task L-1 (Team Lead): mission_advisory().

SPEC for the mission advisory (decision D-5 in docs/PLAN.md). The tests ARE the spec.
"""
import pytest

from app.mission import mission_advisory

BANNED_WORDS = ("fatigue", "fatigued", "impaired", "unfit", "diagnos")


def a(role, name, band, critical=True, status="SCORED", confidence="MEDIUM"):
    return {"role": role, "profile_id": name.lower(), "display_name": name,
            "critical": critical, "status": status, "band": band, "confidence": confidence}


def test_all_green_is_nominal():
    out = mission_advisory([a("Primary pilot", "Kai", "GREEN"), a("Backup pilot", "Lena", "GREEN")])
    assert out["level"] == "NOMINAL"


def test_yellow_on_critical_role_suggests_check_in():
    out = mission_advisory([a("Primary pilot", "Kai", "YELLOW"), a("Backup pilot", "Lena", "GREEN")])
    assert out["level"] == "CHECK_IN"
    assert any("Kai" in s for s in out["suggested_actions"])


def test_red_on_critical_role_requires_review_and_mentions_green_backup():
    out = mission_advisory([a("Primary pilot", "Kai", "RED"), a("Backup pilot", "Lena", "GREEN")])
    assert out["level"] == "REVIEW"
    assert any("Lena" in s for s in out["suggested_actions"])


def test_yellow_on_non_critical_role_does_not_escalate():
    out = mission_advisory([a("Primary pilot", "Kai", "GREEN"),
                            a("Comms", "Tomas", "YELLOW", critical=False)])
    assert out["level"] == "NOMINAL"


def test_calibrating_critical_member_is_flagged_as_unknown():
    out = mission_advisory([a("Primary pilot", "Kai", None, status="CALIBRATING", confidence="NONE")])
    assert out["level"] != "NOMINAL"
    assert any("baseline" in m.lower() for m in out["messages"])


def test_language_guardrails():
    out = mission_advisory([a("Primary pilot", "Kai", "RED"), a("Backup pilot", "Lena", "YELLOW")])
    text = " ".join(out["messages"] + out["suggested_actions"]).lower()
    assert not any(w in text for w in BANNED_WORDS)


# ---- Added after decision D-5 (see docs/PLAN.md "D-5 rules") ----

def test_red_on_non_critical_role_does_not_escalate():
    """D-5: non-critical roles never change the level, even RED."""
    out = mission_advisory([a("Primary pilot", "Kai", "GREEN"),
                            a("Comms", "Tomas", "RED", critical=False)])
    assert out["level"] == "NOMINAL"


def test_no_clean_backup_requires_review_and_flags_both():
    """D-5: pilot RED and backup YELLOW -> REVIEW, flag both, name nobody as a replacement."""
    out = mission_advisory([a("Primary pilot", "Kai", "RED"), a("Backup pilot", "Lena", "YELLOW")])
    assert out["level"] == "REVIEW"
    text = " ".join(out["messages"])
    assert "Kai" in text and "Lena" in text
    # "names nobody as a replacement": no action offers anyone as cover, and both flagged people appear only as people to review
    actions = " ".join(out["suggested_actions"]).lower()
    assert not any(w in actions for w in ("replace", "instead", "cover", "option", "consider", "swap", "take over", "assign"))
    assert "kai" in actions and "lena" in actions                      # both are asked to be reviewed or checked in with


# ---- the three open edges, settled when L-1 was implemented (docs/PLAN.md) ----

def test_red_backup_with_green_primary_still_requires_review():
    out = mission_advisory([a("Primary pilot", "Kai", "GREEN"), a("Backup pilot", "Lena", "RED")])
    assert out["level"] == "REVIEW"
    assert "Lena" in " ".join(out["messages"])
    assert any("Kai" in s for s in out["suggested_actions"])           # the GREEN primary may be named as an option


def test_red_with_a_calibrating_member_is_review_and_the_unknown_is_never_an_option():
    out = mission_advisory([a("Primary pilot", "Kai", "RED"),
                            a("Backup pilot", "Lena", None, status="CALIBRATING", confidence="NONE")])
    assert out["level"] == "REVIEW"
    assert any("baseline" in m.lower() for m in out["messages"])       # reported as unknown
    assert not any("option" in s.lower() or "consider" in s.lower() for s in out["suggested_actions"])


def test_low_confidence_adds_a_caveat_but_never_softens_the_level():
    low = mission_advisory([a("Primary pilot", "Kai", "YELLOW", confidence="LOW")])
    med = mission_advisory([a("Primary pilot", "Kai", "YELLOW", confidence="MEDIUM")])
    assert low["level"] == med["level"] == "CHECK_IN"
    assert "lower confidence" in " ".join(low["messages"]).lower()
    assert "lower confidence" not in " ".join(med["messages"]).lower()


# ---- further guarantees ----

def test_non_critical_roles_never_appear_in_the_text():
    out = mission_advisory([a("Primary pilot", "Kai", "GREEN"), a("Comms", "Tomas", "RED", critical=False)])
    assert "Tomas" not in " ".join(out["messages"] + out["suggested_actions"])


def test_no_critical_roles_is_nominal_and_says_so():
    out = mission_advisory([a("Comms", "Tomas", "RED", critical=False)])
    assert out["level"] == "NOMINAL" and out["messages"]


def test_insufficient_data_is_unknown_not_fine():
    out = mission_advisory([a("Primary pilot", "Kai", None, status="INSUFFICIENT_DATA", confidence="NONE")])
    assert out["level"] == "CHECK_IN"
