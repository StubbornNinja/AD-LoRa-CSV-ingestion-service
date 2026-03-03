import csv
import io
import json
import os
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

from ingest.csv_to_chirpstack import REQUIRED_COLUMNS, ingest_csv, validate_csv_headers

DATA_DIR = Path(os.getenv("INGEST_DATA_DIR", "/opt/chirpstack-ingest"))
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(DATA_DIR / "uploads")))
DB_PATH = Path(os.getenv("DB_PATH", str(DATA_DIR / "data" / "jobs.db")))
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
INGEST_API_TOKEN = os.getenv("INGEST_API_TOKEN")
APPLICATION_ID = os.getenv("APPLICATION_ID")
DEVICE_PROFILE_ID = os.getenv("DEVICE_PROFILE_ID") or os.getenv("LW010_PROFILE_ID")
CHIRPSTACK_API_URL = os.getenv("CHIRPSTACK_API_URL")
CHIRPSTACK_API_TOKEN = os.getenv("CHIRPSTACK_API_TOKEN")

if not INGEST_API_TOKEN:
    raise RuntimeError("INGEST_API_TOKEN not set")
if not APPLICATION_ID:
    raise RuntimeError("APPLICATION_ID not set")
if not DEVICE_PROFILE_ID:
    raise RuntimeError("DEVICE_PROFILE_ID (or LW010_PROFILE_ID) not set")
if not CHIRPSTACK_API_URL:
    raise RuntimeError("CHIRPSTACK_API_URL not set")
if not CHIRPSTACK_API_TOKEN:
    raise RuntimeError("CHIRPSTACK_API_TOKEN not set")

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def now_utc_iso() -> str:
    return datetime.now(UTC).isoformat()


def connect_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with connect_db() as db:
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
                log_path TEXT NOT NULL
            )
            """
        )
        db.commit()


def insert_job(job_id: str, log_path: str) -> None:
    with connect_db() as db:
        db.execute(
            """
            INSERT INTO jobs (job_id, status, created_at, log_path)
            VALUES (?, 'queued', ?, ?)
            """,
            (job_id, now_utc_iso(), log_path),
        )
        db.commit()


def update_job_running(job_id: str) -> None:
    with connect_db() as db:
        db.execute(
            """
            UPDATE jobs SET status = 'running', started_at = ?
            WHERE job_id = ?
            """,
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
            """
            SELECT * FROM jobs
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
    return [dict(row) for row in rows]


def _read_errors_file(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _read_log_tail(path: Path, max_lines: int = 100) -> list[str]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        lines = handle.readlines()
    return [line.rstrip("\n") for line in lines[-max_lines:]]


def _run_job(job_id: str, csv_path: Path, log_path: Path) -> None:
    update_job_running(job_id)

    def write_log(message: str) -> None:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{message}\n")

    try:
        result = ingest_csv(
            application_id=APPLICATION_ID,
            csv_path=str(csv_path),
            profile_id=DEVICE_PROFILE_ID,
            log=write_log,
        )
        errors_path = csv_path.with_suffix(".errors.json")
        with errors_path.open("w", encoding="utf-8") as handle:
            json.dump(result.to_dict()["errors"], handle, indent=2)
        final_status = "completed" if result.failed == 0 else "completed_with_errors"
        update_job_finished(job_id, final_status, result.ok, result.skipped, result.failed)
    except Exception as exc:  # noqa: BLE001
        write_log(f"[FATAL] {exc}")
        update_job_finished(job_id, "failed", 0, 0, 1)


def _read_upload_with_limit(upload: UploadFile, max_bytes: int):
    return upload.file.read(max_bytes + 1)


def _validate_csv_bytes(raw_bytes: bytes) -> None:
    try:
        decoded = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid UTF-8 CSV payload: {exc}") from exc
    reader = csv.reader(io.StringIO(decoded))
    headers = next(reader, None)
    if not headers:
        raise HTTPException(status_code=400, detail="CSV is missing header row")
    ok_headers, missing = validate_csv_headers(headers)
    if not ok_headers:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Missing required CSV columns",
                "required": REQUIRED_COLUMNS,
                "missing": missing,
            },
        )


def _is_csv_upload(file: UploadFile) -> bool:
    allowed_types = {"text/csv", "application/csv", "application/vnd.ms-excel"}
    file_name = (file.filename or "").lower()
    return file_name.endswith(".csv") or file.content_type in allowed_types


def _require_auth(authorization: str | None) -> None:
    if authorization != f"Bearer {INGEST_API_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")


app = FastAPI(title="ChirpStack CSV Ingest")
init_db()


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/upload")
async def upload_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    authorization: str | None = Header(None),
):
    _require_auth(authorization)
    if not _is_csv_upload(file):
        raise HTTPException(status_code=400, detail="Only CSV uploads are accepted")

    raw_bytes = _read_upload_with_limit(file, MAX_UPLOAD_BYTES)
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"Upload exceeds limit of {MAX_UPLOAD_BYTES} bytes")
    _validate_csv_bytes(raw_bytes)

    job_id = str(uuid.uuid4())
    csv_path = UPLOAD_DIR / f"{job_id}.csv"
    log_path = UPLOAD_DIR / f"{job_id}.log"
    csv_path.write_bytes(raw_bytes)

    insert_job(job_id=job_id, log_path=str(log_path))
    background_tasks.add_task(_run_job, job_id, csv_path, log_path)
    return JSONResponse({"job_id": job_id, "status": "queued"})


@app.get("/jobs/{job_id}")
def get_job_status(job_id: str, authorization: str | None = Header(None)):
    _require_auth(authorization)
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    csv_path = UPLOAD_DIR / f"{job_id}.csv"
    errors = _read_errors_file(csv_path.with_suffix(".errors.json"))
    log_tail = _read_log_tail(Path(job["log_path"]))
    job["errors"] = errors
    job["log_excerpt"] = log_tail
    return job


@app.get("/jobs")
def get_jobs(
    authorization: str | None = Header(None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    _require_auth(authorization)
    return {"items": list_jobs(limit=limit, offset=offset), "limit": limit, "offset": offset}
