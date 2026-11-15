"""
All SQL lives here. Nothing else in the app writes SQL.

Why: when the schema changes we fix one file, and the math modules
(baseline.py, scoring.py) stay pure functions you can test without a DB.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from .features import FEATURE_NAMES


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------- profiles ----------

def list_profiles(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute(
        "SELECT id, display_name, mission_role, kind FROM profiles ORDER BY kind, id"
    ).fetchall()
    return [dict(r) for r in rows]


def get_profile(db: sqlite3.Connection, profile_id: str) -> dict | None:
    row = db.execute(
        "SELECT id, display_name, mission_role, kind FROM profiles WHERE id = ?",
        (profile_id,),
    ).fetchone()
    return dict(row) if row else None


def insert_profile(db, profile_id: str, display_name: str, mission_role: str,
                   kind: str = "demo") -> None:
    db.execute(
        "INSERT INTO profiles (id, display_name, mission_role, kind, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (profile_id, display_name, mission_role, kind, utc_now_iso()),
    )


# ---------- sessions ----------

_SESSION_COLUMNS = ("id", "profile_id", "task_type", "created_at", "source",
                    "data_quality", "quality_notes", "accepted_at") + FEATURE_NAMES


def insert_session(db, *, profile_id: str, task_type: str, features: dict,
                   source: str, data_quality: str, quality_notes: str | None,
                   created_at: str | None = None) -> int:
    cols = ("profile_id", "task_type", "created_at", "source",
            "data_quality", "quality_notes") + FEATURE_NAMES
    values = (profile_id, task_type, created_at or utc_now_iso(), source,
              data_quality, quality_notes) + tuple(features[n] for n in FEATURE_NAMES)
    placeholders = ", ".join("?" for _ in cols)
    cur = db.execute(
        f"INSERT INTO sessions ({', '.join(cols)}) VALUES ({placeholders})", values
    )
    return cur.lastrowid


def list_sessions(db, profile_id: str, task_type: str, limit: int | None = None) -> list[dict]:
    """Sessions for one person + task, oldest first."""
    sql = (f"SELECT {', '.join(_SESSION_COLUMNS)} FROM sessions "
           "WHERE profile_id = ? AND task_type = ? ORDER BY id DESC")
    params: tuple = (profile_id, task_type)
    if limit is not None:
        sql += " LIMIT ?"
        params += (limit,)
    rows = db.execute(sql, params).fetchall()
    return [dict(r) for r in reversed(rows)]


def accept_sessions(db, session_ids: list[int]) -> None:
    """A human accepted these flagged sessions as the new normal: they may now shape the baseline."""
    if not session_ids:
        return
    marks = ", ".join("?" for _ in session_ids)
    db.execute(f"UPDATE sessions SET accepted_at = ? WHERE id IN ({marks})", (utc_now_iso(), *session_ids))


# ---------- attention check ----------

def insert_attention_result(db, *, profile_id: str, session_id: int | None, trials: int,
                            median_rt_ms: float | None, premature_count: int,
                            miss_count: int, created_at: str | None = None) -> int:
    cur = db.execute(
        "INSERT INTO attention_results (profile_id, session_id, created_at, trials, "
        "median_rt_ms, premature_count, miss_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (profile_id, session_id, created_at or utc_now_iso(), trials, median_rt_ms,
         premature_count, miss_count),
    )
    return cur.lastrowid


def latest_attention_result(db, profile_id: str) -> dict | None:
    row = db.execute(
        "SELECT id, session_id, created_at, trials, median_rt_ms, premature_count, miss_count "
        "FROM attention_results WHERE profile_id = ? ORDER BY id DESC LIMIT 1",
        (profile_id,),
    ).fetchone()
    return dict(row) if row else None


def list_attention_results(db, profile_id: str, limit: int = 60) -> list[dict]:
    """A person's reaction checks, oldest first (the latest `limit`)."""
    rows = db.execute(
        "SELECT id, session_id, created_at, trials, median_rt_ms, premature_count, miss_count "
        "FROM attention_results WHERE profile_id = ? ORDER BY id DESC LIMIT ?", (profile_id, limit)).fetchall()
    return [dict(r) for r in reversed(rows)]
