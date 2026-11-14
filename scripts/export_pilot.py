"""
Export the real pilot (task F1) as AGGREGATE TIMING NUMBERS ONLY.

Reads the pilot profiles (kind = 'team_test') from the app's SQLite database and writes one CSV row per submitted
session: the pseudonym, the session number for that person (1, 2, 3, ... in the order the sessions were submitted)
and the nine aggregate features from app/features.py. Nothing else leaves the database: no display names, no
mission roles, no timestamps, no free-text notes. (Typed text and keystroke timelines are never stored at all.)

    python scripts/export_pilot.py                                   # $CREW_DB_PATH (else instance/crew_readiness.sqlite3) -> docs/pilot/pilot_sessions.csv
    python scripts/export_pilot.py --db path/to.sqlite3 --out out.csv
    python scripts/export_pilot.py --exclude pilot-03                # a volunteer withdrew: leave them out

Only profiles whose id looks like a pilot pseudonym ("pilot-01" ... "pilot-99", see docs/PILOT.md) are exported.
Any other team_test profile is skipped with a warning, so a real name typed as an id can never reach the CSV.
Standard library only. The database is opened read-only.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.features import FEATURE_NAMES, FEATURES_BY_NAME, TASK_TYPES  # noqa: E402

PSEUDONYM = re.compile(r"^pilot-\d{2}$")
TASK_TYPE = "docking_checklist_v1"
COLUMNS = ("pseudonym", "session_number") + FEATURE_NAMES
DEFAULT_DB = Path(os.environ.get("CREW_DB_PATH") or ROOT / "instance" / "crew_readiness.sqlite3")  # same rule as the app
DEFAULT_OUT = ROOT / "docs" / "pilot" / "pilot_sessions.csv"

assert TASK_TYPE in TASK_TYPES


def pilot_rows(db_path: Path, exclude: frozenset[str] = frozenset(), warn=print) -> list[dict]:
    """The export rows, oldest session first per person. Pure read; raises if the database is missing."""
    if not Path(db_path).exists():
        raise FileNotFoundError(f"No database at {db_path}")
    con = sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        profiles = [r["id"] for r in con.execute(
            "SELECT id FROM profiles WHERE kind = 'team_test' ORDER BY id")]
        rows: list[dict] = []
        for pid in profiles:
            if not PSEUDONYM.match(pid):
                warn(f"skipped team_test profile that is not a pilot pseudonym (pilot-NN): {pid!r}")
                continue
            if pid in exclude:
                warn(f"excluded on request: {pid}")
                continue
            sessions = con.execute(
                f"SELECT {', '.join(FEATURE_NAMES)} FROM sessions "
                "WHERE profile_id = ? AND task_type = ? AND source = 'live' ORDER BY id",
                (pid, TASK_TYPE)).fetchall()
            for n, s in enumerate(sessions, start=1):
                row = {"pseudonym": pid, "session_number": n}
                for name in FEATURE_NAMES:
                    value = s[name]
                    # belt and braces: only numbers of the declared kind may be written
                    kind = FEATURES_BY_NAME[name].kind
                    if isinstance(value, bool) or not isinstance(value, (int, float)):
                        raise ValueError(f"{pid} session {n}: {name} is not a number")
                    row[name] = int(value) if kind is int else float(value)
                rows.append(row)
        return rows
    finally:
        con.close()


def write_csv(rows: list[dict], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"SQLite database (default: {DEFAULT_DB})")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"CSV to write (default: {DEFAULT_OUT})")
    ap.add_argument("--exclude", action="append", default=[], metavar="PSEUDONYM",
                    help="leave this pseudonym out (repeatable), e.g. a volunteer who withdrew")
    a = ap.parse_args(argv)

    warn = lambda msg: print(f"warning: {msg}", file=sys.stderr)  # noqa: E731
    try:
        rows = pilot_rows(a.db, frozenset(a.exclude), warn=warn)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if not rows:
        print("error: no pilot sessions found (profiles named pilot-NN with kind team_test).", file=sys.stderr)
        return 1
    write_csv(rows, a.out)
    people = sorted({r["pseudonym"] for r in rows})
    print(f"Wrote {len(rows)} sessions from {len(people)} people to {a.out}")
    for p in people:
        print(f"  {p}: {sum(r['pseudonym'] == p for r in rows)} sessions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
