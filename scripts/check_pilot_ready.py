"""
Is the real pilot complete and consistent? (task F2 support). Run it during the pilot evening and before committing.

    python scripts/check_pilot_ready.py
    python scripts/check_pilot_ready.py --sessions docs/pilot/pilot_sessions.csv --sheet docs/pilot/session_sheet.csv

Reads the export from scripts/export_pilot.py and the hand-filled session sheet, and prints, per pseudonym, which of the 12
sessions are missing from the export, which sheet rows still need a consent or issue code, and anything that disagrees with the
protocol in docs/PILOT.md. It reads only pseudonyms, session numbers and codes; it never prints a timing value and never edits a file.
At the end it runs the same loader as the analysis (ml/pilot_report.py), so "READY" means `python -m ml.pilot_report` will accept
the files. Exit code 0 when ready, 1 otherwise.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SESSIONS = 12
PERTURBED = range(9, 12)          # sessions 9, 10, 11 (docs/PILOT.md)
MIN_PEOPLE = 5
ISSUES = {"none", "redone", "interrupted", "other"}
PSEUDONYM = re.compile(r"^pilot-\d{2}$")


def planned(pid: str, n: int) -> tuple[str, str]:
    """The protocol's plan: odd pseudonyms use the non-dominant hand, even ones count backwards, in sessions 9-11."""
    if n not in PERTURBED:
        return "normal", "none"
    return "perturbed", ("non_dominant_hand" if int(pid[-2:]) % 2 else "counting_backwards")


def read(path: Path) -> list[dict] | None:
    if not path.exists():
        return None
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def check(sessions_path: Path, sheet_path: Path) -> tuple[list[str], bool]:
    """Returns (report lines, ready)."""
    sessions_rows, sheet_rows = read(sessions_path), read(sheet_path)
    lines: list[str] = []
    problems = 0
    exported: dict[str, list[int]] = {}
    for r in sessions_rows or []:
        exported.setdefault(r["pseudonym"], []).append(int(r["session_number"]))
    sheet: dict[str, dict[int, dict]] = {}
    dup_sheet: list[str] = []
    for r in sheet_rows or []:
        pid, n = r["pseudonym"].strip(), int(r["session_number"])
        if n in sheet.setdefault(pid, {}):
            dup_sheet.append(f"{pid} #{n}")
        sheet[pid][n] = r

    if sessions_rows is None:
        lines.append("export: NOT FOUND (run scripts/export_pilot.py after the sessions)")
        problems += 1
    if sheet_rows is None:
        lines.append("sheet: NOT FOUND (docs/pilot/session_sheet.csv)")
        problems += 1
    for d in dup_sheet:
        lines.append(f"sheet lists {d} twice: keep one row")
        problems += 1

    complete = []
    for pid in sorted(set(exported) | set(sheet)):
        if not PSEUDONYM.match(pid):
            lines.append(f"{pid}: not a pilot pseudonym (pilot-NN); remove it")
            problems += 1
            continue
        got = exported.get(pid, [])
        rows = sheet.get(pid, {})
        consented = {n for n, r in rows.items() if r["consent"].strip() == "yes"}
        if not got and not consented:
            lines.append(f"{pid}: not run yet (no exported sessions, no consent ticked). "
                         f"Run them, or delete this person's {len(rows)} sheet rows if they are not coming.")
            problems += 1
            continue
        notes = []
        missing = [n for n in range(1, SESSIONS + 1) if n not in got]
        if missing:
            notes.append(f"missing sessions in export: {_ranges(missing)}")
        dups = sorted({n for n in got if got.count(n) > 1})
        extra = sorted({n for n in got if n > SESSIONS})
        if dups or extra:
            notes.append(f"unexpected export sessions: {_ranges(sorted(set(dups + extra)))} (more than 12 submitted? note it in the sheet)")
        no_row = [n for n in got if n not in rows]
        if no_row:
            notes.append(f"exported but no sheet row: {_ranges(sorted(set(no_row)))}")
        not_run = [n for n in rows if n not in got]
        if got and not_run:
            notes.append(f"sheet rows with no exported session: {_ranges(sorted(not_run))} (run them, or delete the rows)")
        blank_consent = sorted(n for n, r in rows.items() if n in got and r["consent"].strip() != "yes")
        if blank_consent:
            notes.append(f"consent not 'yes' on: {_ranges(blank_consent)}")
        bad_issue = sorted(n for n, r in rows.items() if n in got and r["issue"].strip() not in ISSUES)
        if bad_issue:
            notes.append(f"issue code blank or unknown on: {_ranges(bad_issue)} (use none, redone, interrupted or other)")
        off_plan = sorted(n for n, r in rows.items()
                          if (r["condition"].strip(), r["perturbation"].strip()) != planned(pid, n))
        if off_plan:
            notes.append(f"condition/perturbation differs from the protocol on: {_ranges(off_plan)} (fine only if that is what happened)")
        hard = [x for x in notes if not x.startswith("condition/perturbation")]
        if hard:
            problems += 1
            lines.append(f"{pid}: " + "; ".join(notes))
        else:
            complete.append(pid)
            lines.append(f"{pid}: complete, 12 sessions" + (f" ({notes[0]})" if notes else ""))

    lines.append("")
    lines.append(f"complete: {len(complete)} people (the plan needs at least {MIN_PEOPLE})")
    ready = problems == 0 and len(complete) >= MIN_PEOPLE
    if problems == 0 and sessions_rows is not None and sheet_rows is not None:
        try:   # the analysis's own loader: the final word on whether the two files agree
            from ml.pilot_report import load_pilot
        except ImportError as e:
            lines.append(f"could not import ml.pilot_report ({e}); skipped the analysis's own check")
        else:
            try:
                load_pilot(sessions_path, sheet_path)
            except ValueError as e:
                lines.append(f"ml.pilot_report refuses the files: {e}")
                ready = False
    lines.append("READY: run `python -m ml.pilot_report`" if ready else "NOT READY: fix the lines above")
    return lines, ready


def _ranges(ns: list[int]) -> str:
    """[1, 2, 3, 7, 9, 10] -> '1-3, 7, 9-10'"""
    out, start = [], None
    for i, n in enumerate(ns):
        if start is None:
            start = n
        if i + 1 == len(ns) or ns[i + 1] != n + 1:
            out.append(str(start) if start == n else f"{start}-{n}")
            start = None
    return ", ".join(out)


DEFAULT_SESSIONS = ROOT / "docs" / "pilot" / "pilot_sessions.csv"
DEFAULT_SHEET = ROOT / "docs" / "pilot" / "session_sheet.csv"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sessions", type=Path, default=DEFAULT_SESSIONS, help="export from scripts/export_pilot.py")
    ap.add_argument("--sheet", type=Path, default=DEFAULT_SHEET, help="the filled session sheet")
    a = ap.parse_args(argv)
    lines, ready = check(a.sessions, a.sheet)
    print("\n".join(lines))
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
