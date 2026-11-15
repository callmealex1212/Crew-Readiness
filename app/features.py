"""
Feature contract — the ONLY per-session data the server accepts.

PRIVACY BY DESIGN
-----------------
These are aggregate timings and counts computed *in the browser*
(see app/static/js/capture.js). There is no field for typed text, key
identity, or raw keystroke timelines. `validate_session_payload` rejects
any field that is not listed here, and the database has no column to put
text in. Privacy is enforced by code and tested (tests/test_features.py),
not just promised in the README.

If you change this file, you MUST also update docs/DATA_CONTRACT.md and
app/schema.sql, and tell the team lead. This is the integration contract
that the frontend (Member 3) and the scoring code (Member 2) both depend on.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# A task type is versioned. If the checklist text changes, the typing
# behaviour changes, so old baselines are no longer comparable. Bump the
# version (docking_checklist_v2) instead of editing v1 in place.
TASK_TYPES = frozenset({"docking_checklist_v1"})


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    kind: type          # int (a count) or float (a duration in ms)
    min: float          # sanity range: values outside it are rejected (HTTP 400)
    max: float
    label: str          # plain-language name, used in UI and in "reasons"
    unit: str


FEATURES: tuple[FeatureSpec, ...] = (
    FeatureSpec("keystroke_count", int, 1, 5000,
                "Keystrokes in task", "count"),
    FeatureSpec("iki_median_ms", float, 20, 3000,
                "Typing rhythm (median time between keys)", "ms"),
    FeatureSpec("iki_iqr_ms", float, 0, 3000,
                "Typing variability (spread of time between keys)", "ms"),
    FeatureSpec("pause_count", int, 0, 500,
                "Pauses while typing (gaps of 2 s or more)", "count"),
    FeatureSpec("pause_total_ms", float, 0, 3_600_000,
                "Total pause time", "ms"),
    FeatureSpec("checklist_response_median_ms", float, 0, 120_000,
                "Checklist response time (item shown to first key)", "ms"),
    FeatureSpec("task_duration_ms", float, 1_000, 3_600_000,
                "Task duration", "ms"),
    FeatureSpec("correction_count", int, 0, 2000,
                "Corrections (Backspace/Delete presses)", "count"),
    FeatureSpec("retry_count", int, 0, 500,
                "Rejected confirmations (had to re-enter)", "count"),
)

FEATURE_NAMES: tuple[str, ...] = tuple(f.name for f in FEATURES)
FEATURES_BY_NAME: dict[str, FeatureSpec] = {f.name: f for f in FEATURES}

ALLOWED_TOP_LEVEL = frozenset({"profile_id", "task_type", "features"})

# Data-quality rules (illustrative). A "low" quality session is stored and
# shown, but it is NOT used to build the baseline and it lowers confidence.
MIN_KEYSTROKES_FOR_OK = 80      # the v1 checklist needs ~125 keys
MAX_RETRIES_FOR_OK = 5


class ValidationError(ValueError):
    """Raised when a payload breaks the data contract. Maps to HTTP 400."""


def validate_session_payload(payload: object) -> dict:
    """Return a clean {profile_id, task_type, features} dict or raise ValidationError.

    Deliberately strict: unknown fields are an error, not silently dropped.
    If a future frontend bug starts sending typed text, we want a loud 400
    in development, not a quiet privacy leak.
    """
    if not isinstance(payload, dict):
        raise ValidationError("Body must be a JSON object.")

    unknown_top = set(payload) - ALLOWED_TOP_LEVEL
    if unknown_top:
        raise ValidationError(
            f"Unexpected top-level field(s): {sorted(unknown_top)}. "
            "Only aggregate timing features are accepted."
        )

    profile_id = payload.get("profile_id")
    if not isinstance(profile_id, str) or not profile_id.strip():
        raise ValidationError("profile_id must be a non-empty string.")
    # found by fault injection (task R2): a lone surrogate reached SQLite and crashed it; ids are short, printable slugs
    if len(profile_id) > 200 or not profile_id.isprintable():
        raise ValidationError("profile_id must be at most 200 printable characters.")

    task_type = payload.get("task_type")
    if not isinstance(task_type, str) or task_type not in TASK_TYPES:   # a list or object here raised TypeError (R2)
        raise ValidationError(f"task_type must be one of {sorted(TASK_TYPES)}.")

    features = payload.get("features")
    if not isinstance(features, dict):
        raise ValidationError("features must be a JSON object.")

    unknown = set(features) - set(FEATURE_NAMES)
    if unknown:
        raise ValidationError(
            f"Unexpected feature(s): {sorted(unknown)}. "
            "The server never accepts text, key identities or raw keystroke logs."
        )
    missing = set(FEATURE_NAMES) - set(features)
    if missing:
        raise ValidationError(f"Missing feature(s): {sorted(missing)}.")

    clean: dict[str, float | int] = {}
    for spec in FEATURES:
        value = features[spec.name]
        # bool is a subclass of int in Python — reject it explicitly.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValidationError(f"{spec.name} must be a number.")
        # found by fault injection (task R2): int(NaN) and int(inf) raised before the range check; check range first
        if isinstance(value, float) and not math.isfinite(value):
            raise ValidationError(f"{spec.name} must be a finite number.")
        if not (spec.min <= value <= spec.max):
            raise ValidationError(
                f"{spec.name}={value} is outside the plausible range "
                f"[{spec.min}, {spec.max}] {spec.unit}."
            )
        if spec.kind is int:
            if value != int(value):
                raise ValidationError(f"{spec.name} must be a whole number.")
            value = int(value)
        else:
            value = float(value)
        clean[spec.name] = value

    return {"profile_id": profile_id.strip(), "task_type": task_type, "features": clean}


def assess_quality(features: dict) -> tuple[str, list[str]]:
    """Flag sessions that are probably not comparable to the person's usual ones."""
    notes: list[str] = []
    if features["keystroke_count"] < MIN_KEYSTROKES_FOR_OK:
        notes.append("Fewer keystrokes than the task requires; task may be incomplete.")
    if features["retry_count"] > MAX_RETRIES_FOR_OK:
        notes.append("Many rejected confirmations; task may not have been followed normally.")
    return ("low" if notes else "ok"), notes
