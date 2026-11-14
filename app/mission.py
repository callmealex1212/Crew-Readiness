"""
Mission scenario: gives a readiness change *operational meaning*.

A YELLOW band on a quiet day is trivia; a YELLOW band on the primary
pilot six hours before manual docking is a decision. This module holds
the (fictional) scenario and the advisory rules.

Owner: Team Lead (task L-1 in docs/TEAM_GUIDE.md).
"""
from __future__ import annotations

MISSION = {
    "name": "Gateway docking — simulated scenario",
    "critical_operation": "Manual approach and docking",
    "t_minus_hours": 6,
    "assignments": [
        {"role": "Primary pilot",   "profile_id": "plt-okafor", "critical": True},
        {"role": "Backup pilot",    "profile_id": "cdr-vega",   "critical": True},
        {"role": "Systems monitor", "profile_id": "fe-sato",    "critical": False},
        {"role": "Comms and log",   "profile_id": "ms-ibarra",  "critical": False},
    ],
}


def _who(a: dict) -> str:
    return f"{a['display_name']} ({a['role']})"


def _unknown(a: dict) -> bool:
    """CALIBRATING, no data, or no band: we do not know. Unknown is never presented as fine."""
    return a.get("status") != "SCORED" or a.get("band") not in ("GREEN", "YELLOW", "RED")


def _caveat(a: dict) -> str:
    """LOW confidence never changes the level (safety first); it only says so in the words."""
    return " Few sessions so far, so lower confidence." if a.get("confidence") in ("NONE", "LOW") else ""


def mission_advisory(assignments: list[dict]) -> dict:
    """Turn crew readiness into a human-facing recommendation for the critical operation.

    Input, one dict per assignment, already joined with readiness:
        {"role": str, "profile_id": str, "display_name": str, "critical": bool,
         "status": "SCORED"|"CALIBRATING"|"INSUFFICIENT_DATA",
         "band": "GREEN"|"YELLOW"|"RED"|None, "confidence": str}

    Output:
        {"level": "NOMINAL" | "CHECK_IN" | "REVIEW",
         "messages": [str, ...],           # plain language, one per concern
         "suggested_actions": [str, ...]}  # e.g. "Suggest a brief check-in with Kai Okafor (Primary pilot)..."

    Guardrails: the system SUGGESTS and never assigns, clears or grounds anyone; it never uses the words fatigue,
    impaired, unfit or diagnosis; a CALIBRATING person is "unknown", not "fine".

    Rules (docs/PLAN.md, D-5). Only CRITICAL roles count; non-critical roles never change the level or the text.
    Level = the highest row that applies:
        any critical RED            -> REVIEW (name a GREEN critical member as an option for the reviewer, if there is one;
                                       if there is none, flag everyone who is not GREEN and name nobody as a replacement)
        else any critical YELLOW    -> CHECK_IN
        else any critical unknown   -> CHECK_IN ("no baseline yet")
        else                        -> NOMINAL
    Open edges, settled when implementing (recorded in docs/PLAN.md, pending the Lead's confirmation):
        a RED backup alone forces REVIEW even with a GREEN primary; RED together with an unknown member is REVIEW, and
        the unknown member is reported as unknown and never named as an option; LOW confidence adds a caveat to the
        wording and never changes the level.
    """
    critical = [a for a in assignments if a.get("critical")]
    red = [a for a in critical if not _unknown(a) and a["band"] == "RED"]
    yellow = [a for a in critical if not _unknown(a) and a["band"] == "YELLOW"]
    green = [a for a in critical if not _unknown(a) and a["band"] == "GREEN"]
    unknown = [a for a in critical if _unknown(a)]

    messages: list[str] = []
    actions: list[str] = []

    for a in red:
        messages.append(f"{_who(a)}: timing differs strongly from their own usual pattern.{_caveat(a)}")
    for a in yellow:
        messages.append(f"{_who(a)}: timing differs from their own usual pattern.{_caveat(a)}")
    for a in unknown:
        messages.append(f"No baseline yet for {_who(a)}: their status is unknown, not fine.")

    if red:
        level = "REVIEW"
        for a in red:
            actions.append(f"Recommend human review of {_who(a)} and a second verification before the critical operation.")
        if green:
            names = ", ".join(_who(a) for a in green)
            actions.append(f"A reviewer may consider {names}, within their own usual range, as an option. The decision stays with people.")
        else:
            messages.append("No critical team member is currently within their own usual range.")
            actions.append("This is a decision for people: review everyone flagged above.")
        for a in yellow:
            actions.append(f"Suggest a brief check-in with {_who(a)}.")
        for a in unknown:
            actions.append(f"Collect more sessions for {_who(a)}; treat their status as unknown for now.")
    elif yellow:
        level = "CHECK_IN"
        for a in yellow:
            actions.append(f"Suggest a brief check-in with {_who(a)}, or run the optional attention check.")
        for a in unknown:
            actions.append(f"Collect more sessions for {_who(a)}; treat their status as unknown for now.")
    elif unknown:
        level = "CHECK_IN"
        for a in unknown:
            actions.append(f"Collect more sessions for {_who(a)} before relying on this check; treat their status as unknown for now.")
    else:
        level = "NOMINAL"
        messages.append("Every critical role is within its own usual range." if critical else "No critical roles are assigned.")

    return {"level": level, "messages": messages, "suggested_actions": actions}
