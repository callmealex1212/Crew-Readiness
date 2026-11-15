"""
Backup and restore (task R3): the database as JSON with a SHA-256 checksum.

    flask --app run export-backup backup.json
    flask --app run reset-empty            # restore goes into an EMPTY database only
    flask --app run import-backup backup.json

What is written: profiles, sessions (the nine aggregate features, their time, source, data quality and the accepted-as-new-normal
marker) and attention-check results. Nothing else exists in the database, and nothing else is written. The importer is strict:
it refuses a file whose checksum does not match, any field or table it does not know, any value of the wrong type or outside the
feature contract (so text cannot be smuggled into a number), and any database that already holds data.

What it does NOT show or do: it is not encrypted (a backup holds the same pseudonyms and timings as the database; keep it where the
database is kept); it does not merge two databases; a checksum detects accidental damage, not a deliberate forgery (anyone can
recompute it); and it has not been tested on flight storage media.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3

import click

from .features import FEATURE_NAMES, FEATURES_BY_NAME, TASK_TYPES

FORMAT = "crew-readiness-backup"
FORMAT_VERSION = 1

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
SLUG = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
NAME = re.compile(r"^[^\x00-\x1f\x7f]{1,80}$")          # pseudonyms and roles: short, one line
# the only free text the app itself writes (app/features.py assess_quality); anything else is refused
QUALITY_NOTES = frozenset({
    "Fewer keystrokes than the task requires; task may be incomplete.",
    "Many rejected confirmations; task may not have been followed normally.",
})


class BackupError(ValueError):
    """A backup file was refused; the message says why, in plain words."""


def _iso(v, nullable=False):
    return (nullable and v is None) or (isinstance(v, str) and bool(ISO.match(v)))


def _int(v, lo=0, hi=10**9, nullable=False):
    return (nullable and v is None) or (isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi)


def _num(v, lo, hi, nullable=False):
    if nullable and v is None:
        return True
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and lo <= v <= hi


def _feature(name):
    spec = FEATURES_BY_NAME[name]
    if spec.kind is int:
        return lambda v: _int(v, int(spec.min), int(spec.max))
    return lambda v: _num(v, spec.min, spec.max)


def _notes(v):
    return v is None or (isinstance(v, str) and all(part in QUALITY_NOTES for part in _split_notes(v)))


def _split_notes(v: str) -> list[str]:
    # notes are joined with "; " but each note ends with "." so split after the full stop
    return [p if p.endswith(".") else p + "." for p in re.split(r"(?<=\.); ", v)]


# table -> column -> validator. The columns are exactly the schema's; this is also the export's column list.
SCHEMA = {
    "profiles": {
        "id": lambda v: isinstance(v, str) and bool(SLUG.match(v)),
        "display_name": lambda v: isinstance(v, str) and bool(NAME.match(v)),
        "mission_role": lambda v: isinstance(v, str) and bool(NAME.match(v)),
        "kind": lambda v: v in ("demo", "team_test"),
        "created_at": _iso,
    },
    "sessions": {
        "id": lambda v: _int(v, 1),
        "profile_id": lambda v: isinstance(v, str) and bool(SLUG.match(v)),
        "task_type": lambda v: v in TASK_TYPES,
        "created_at": _iso,
        "source": lambda v: v in ("live", "synthetic"),
        "data_quality": lambda v: v in ("ok", "low"),
        "quality_notes": _notes,
        **{name: _feature(name) for name in FEATURE_NAMES},
        "accepted_at": lambda v: _iso(v, nullable=True),
    },
    "attention_results": {
        "id": lambda v: _int(v, 1),
        "profile_id": lambda v: isinstance(v, str) and bool(SLUG.match(v)),
        "session_id": lambda v: _int(v, 1, nullable=True),
        "created_at": _iso,
        "trials": lambda v: _int(v, 1, 100),
        "median_rt_ms": lambda v: _num(v, 50, 5000, nullable=True),
        "premature_count": lambda v: _int(v, 0, 1000),
        "miss_count": lambda v: _int(v, 0, 100),
    },
}
TABLE_ORDER = ("profiles", "sessions", "attention_results")   # parents before children


def checksum(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()


def export_backup(db: sqlite3.Connection) -> dict:
    tables = {}
    for table in TABLE_ORDER:
        cols = list(SCHEMA[table])
        rows = db.execute(f"SELECT {', '.join(cols)} FROM {table} ORDER BY rowid").fetchall()
        tables[table] = [dict(zip(cols, tuple(r))) for r in rows]
    payload = {"format": FORMAT, "format_version": FORMAT_VERSION, "tables": tables}
    return {"sha256": checksum(payload), "payload": payload}


def write_backup(db: sqlite3.Connection, path) -> dict:
    doc = export_backup(db)
    with open(path, "w", encoding="ascii") as f:
        json.dump(doc, f, ensure_ascii=True, allow_nan=False, indent=1)
        f.write("\n")
    return {t: len(rows) for t, rows in doc["payload"]["tables"].items()}


def _reject_constants(name):
    raise BackupError(f"the file contains {name}, which a backup never holds")


def read_backup(path) -> dict:
    """Parse and verify a backup file; return its payload. Raises BackupError with a plain reason."""
    try:
        with open(path, "rb") as f:
            raw = f.read()
        doc = json.loads(raw.decode("utf-8"), parse_constant=_reject_constants)
    except BackupError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise BackupError(f"not a readable backup file ({type(e).__name__}); it may be damaged") from None
    if not isinstance(doc, dict) or set(doc) != {"sha256", "payload"}:
        raise BackupError("not a backup file: expected exactly 'sha256' and 'payload'")
    payload = doc["payload"]
    if not isinstance(payload, dict) or not isinstance(doc["sha256"], str) or checksum(payload) != doc["sha256"]:
        raise BackupError("checksum does not match: the file was changed or damaged, so it was NOT restored")
    validate(payload)
    return payload


def validate(payload: dict) -> None:
    if set(payload) != {"format", "format_version", "tables"}:
        raise BackupError(f"unknown or missing top-level fields: {sorted(set(payload) ^ {'format', 'format_version', 'tables'})}")
    if payload["format"] != FORMAT or payload["format_version"] != FORMAT_VERSION:
        raise BackupError(f"not a {FORMAT} version {FORMAT_VERSION} file")
    tables = payload["tables"]
    if not isinstance(tables, dict) or set(tables) != set(SCHEMA):
        raise BackupError(f"unknown or missing tables: expected exactly {sorted(SCHEMA)}")
    for table, rows in tables.items():
        if not isinstance(rows, list):
            raise BackupError(f"{table} is not a list of rows")
        cols = SCHEMA[table]
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                raise BackupError(f"{table} row {i + 1} is not an object")
            extra, missing = set(row) - set(cols), set(cols) - set(row)
            if extra:
                raise BackupError(f"{table} row {i + 1} has unknown fields {sorted(extra)}; only the stored columns are allowed")
            if missing:
                raise BackupError(f"{table} row {i + 1} is missing {sorted(missing)}")
            for col, ok in cols.items():
                if not ok(row[col]):
                    raise BackupError(f"{table} row {i + 1}: {col} has a value that is not allowed")


def is_empty(db: sqlite3.Connection) -> bool:
    return all(db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0 for t in TABLE_ORDER)


def restore(db: sqlite3.Connection, payload: dict) -> dict:
    """Insert a validated payload into an EMPTY database, all or nothing."""
    if not is_empty(db):
        raise BackupError("the database is not empty. Restore only goes into an empty database, so nothing is overwritten "
                          "or mixed. Run `flask --app run reset-empty` first if you mean to replace everything.")
    try:
        for table in TABLE_ORDER:
            cols = list(SCHEMA[table])
            for row in payload["tables"][table]:
                db.execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                           tuple(row[c] for c in cols))
        db.commit()
    except sqlite3.Error as e:
        db.rollback()
        raise BackupError(f"the database refused the backup ({e}); nothing was restored") from None
    return {t: len(payload["tables"][t]) for t in TABLE_ORDER}


def register_cli(app) -> None:
    """`flask export-backup <file>` and `flask import-backup <file>` (wired in app/cli.py)."""
    from .db import get_db

    @app.cli.command("export-backup")
    @click.argument("path", type=click.Path(dir_okay=False, writable=True))
    def export_backup_cmd(path):
        """Write the database (profiles, sessions, attention results) as JSON with a SHA-256 checksum."""
        counts = write_backup(get_db(), path)
        click.echo(f"Wrote {path}: " + ", ".join(f"{n} {t}" for t, n in counts.items()))
        click.echo("Not encrypted: it holds the same pseudonyms and timings as the database. Keep it where the database is kept.")

    @app.cli.command("import-backup")
    @click.argument("path", type=click.Path(exists=True, dir_okay=False))
    def import_backup_cmd(path):
        """Restore a backup into an EMPTY database. Refuses a damaged file, unknown fields or a database that holds data."""
        try:
            counts = restore(get_db(), read_backup(path))
        except BackupError as e:
            click.echo(f"Refused: {e}", err=True)
            raise SystemExit(1)
        click.echo("Restored: " + ", ".join(f"{n} {t}" for t, n in counts.items()))
