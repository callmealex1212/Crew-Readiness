"""F2 support: scripts/check_pilot_ready.py says exactly what is missing. Uses a MADE-UP stand-in export; never pilot data."""
import csv
import importlib.util
from pathlib import Path

from app.features import FEATURE_NAMES
from tests.conftest import valid_features

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("check_pilot_ready", ROOT / "scripts" / "check_pilot_ready.py")
cpr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cpr)

SHEET_COLS = ["pseudonym", "consent", "session_number", "condition", "perturbation", "issue"]
MARKER = 187.25   # a timing value that must never be printed


def write(tmp_path, people=range(1, 6), skip=(), blank_consent=(), sheet_only=(), off_plan=()):
    export, sheet = [], []
    for p in people:
        pid = f"pilot-{p:02d}"
        for n in range(1, 13):
            cond, pert = cpr.planned(pid, n)
            if (pid, n) in off_plan:
                pert = "counting_backwards" if pert == "non_dominant_hand" else "non_dominant_hand"
            sheet.append({"pseudonym": pid, "consent": "" if (pid, n) in blank_consent else "yes", "session_number": n,
                          "condition": cond, "perturbation": pert, "issue": "none"})
            if (pid, n) not in skip:
                export.append(dict(valid_features(iki_median_ms=MARKER), pseudonym=pid, session_number=n))
    for pid in sheet_only:
        for n in range(1, 13):
            cond, pert = cpr.planned(pid, n)
            sheet.append({"pseudonym": pid, "consent": "", "session_number": n, "condition": cond, "perturbation": pert, "issue": ""})
    s, h = tmp_path / "sessions.csv", tmp_path / "sheet.csv"
    with open(s, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["pseudonym", "session_number", *FEATURE_NAMES])
        w.writeheader()
        w.writerows(export)
    with open(h, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SHEET_COLS)
        w.writeheader()
        w.writerows(sheet)
    return s, h


def run(s, h, capsys):
    code = cpr.main(["--sessions", str(s), "--sheet", str(h)])
    return code, capsys.readouterr().out


def test_five_complete_people_are_ready_and_the_analysis_accepts_them(tmp_path, capsys):
    code, out = run(*write(tmp_path), capsys)
    assert code == 0 and "READY: run" in out and "complete: 5 people" in out
    assert str(MARKER) not in out   # never prints timing values


def test_names_the_missing_sessions_per_person(tmp_path, capsys):
    code, out = run(*write(tmp_path, skip={("pilot-03", 4), ("pilot-03", 11), ("pilot-03", 12)}), capsys)
    assert code == 1
    assert "pilot-03: missing sessions in export: 4, 11-12" in out
    assert "sheet rows with no exported session: 4, 11-12" in out


def test_blank_consent_and_people_not_run(tmp_path, capsys):
    code, out = run(*write(tmp_path, blank_consent={("pilot-02", 1)}, sheet_only=["pilot-08"]), capsys)
    assert code == 1
    assert "pilot-02: consent not 'yes' on: 1" in out
    assert "pilot-08: not run yet" in out


def test_off_protocol_perturbation_is_reported_but_not_blocking(tmp_path, capsys):
    code, out = run(*write(tmp_path, off_plan={("pilot-01", 9)}), capsys)
    assert code == 0
    assert "pilot-01: complete, 12 sessions (condition/perturbation differs from the protocol on: 9" in out


def test_too_few_people_is_not_ready(tmp_path, capsys):
    code, out = run(*write(tmp_path, people=range(1, 4)), capsys)
    assert code == 1 and "complete: 3 people" in out


def test_the_committed_sheet_only_holds_allowed_codes():
    """Holds for the empty skeleton and for the filled sheet alike: codes only, no free text, no names."""
    rows = list(csv.DictReader(open(ROOT / "docs" / "pilot" / "session_sheet.csv", encoding="utf-8")))
    assert 0 < len(rows) <= 8 * 12
    for r in rows:
        assert list(r) == SHEET_COLS
        assert cpr.PSEUDONYM.match(r["pseudonym"])
        assert r["consent"] in ("", "yes")
        assert r["issue"] in {""} | cpr.ISSUES
        assert r["condition"] in ("normal", "perturbed")
        assert r["perturbation"] in ("none", "non_dominant_hand", "counting_backwards")
        assert 1 <= int(r["session_number"]) <= 12
