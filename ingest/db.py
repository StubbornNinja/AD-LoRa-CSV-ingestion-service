from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


_db_path: Path | None = None


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def configure(db_path: Path) -> None:
    global _db_path
    _db_path = db_path


def connect_db() -> sqlite3.Connection:
    if _db_path is None:
        raise RuntimeError("Database not configured — call db.configure() first")
    connection = sqlite3.connect(_db_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with connect_db() as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                ok INTEGER NOT NULL DEFAULT 0,
                skipped INTEGER NOT NULL DEFAULT 0,
                failed INTEGER NOT NULL DEFAULT 0,
                total_rows INTEGER,
                operator_email TEXT,
                log_path TEXT NOT NULL
            )
            """
        )
        db.commit()
        # Migrate existing databases: add columns if missing
        existing = {row[1] for row in db.execute("PRAGMA table_info(jobs)").fetchall()}
        if "total_rows" not in existing:
            db.execute("ALTER TABLE jobs ADD COLUMN total_rows INTEGER")
        if "operator_email" not in existing:
            db.execute("ALTER TABLE jobs ADD COLUMN operator_email TEXT")
        db.commit()


def insert_job(job_id: str, log_path: str, total_rows: int | None = None,
               operator_email: str | None = None) -> None:
    with connect_db() as db:
        db.execute(
            """
            INSERT INTO jobs (job_id, status, created_at, log_path, total_rows, operator_email)
            VALUES (?, 'queued', ?, ?, ?, ?)
            """,
            (job_id, now_utc_iso(), log_path, total_rows, operator_email),
        )
        db.commit()


def update_job_running(job_id: str) -> None:
    with connect_db() as db:
        db.execute(
            "UPDATE jobs SET status = 'running', started_at = ? WHERE job_id = ?",
            (now_utc_iso(), job_id),
        )
        db.commit()


def update_job_finished(job_id: str, status: str, ok: int, skipped: int, failed: int) -> None:
    with connect_db() as db:
        db.execute(
            """
            UPDATE jobs
            SET status = ?, finished_at = ?, ok = ?, skipped = ?, failed = ?
            WHERE job_id = ?
            """,
            (status, now_utc_iso(), ok, skipped, failed, job_id),
        )
        db.commit()


def get_job(job_id: str) -> dict | None:
    with connect_db() as db:
        row = db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    return dict(row) if row else None


def list_jobs(limit: int, offset: int) -> list[dict]:
    with connect_db() as db:
        rows = db.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [dict(row) for row in rows]


def total_jobs() -> int:
    with connect_db() as db:
        row = db.execute("SELECT COUNT(*) FROM jobs").fetchone()
    return row[0] if row else 0


def read_errors_file(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_log_tail(path: Path, max_lines: int = 100) -> list[str]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        lines = handle.readlines()
    return [line.rstrip("\n") for line in lines[-max_lines:]]
