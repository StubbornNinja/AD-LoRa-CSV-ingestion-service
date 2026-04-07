import csv
import io
import json
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile

from ingest import db
from ingest.auth import AuthContext, require_auth
from ingest.config import Settings
from ingest.csv_to_chirpstack import REQUIRED_COLUMNS, ingest_csv, validate_csv_headers
from ingest.models import JobCreated, JobDetail, JobListResponse, JobSummary

router = APIRouter(prefix="/intake", tags=["intake"])

_settings: Optional[Settings] = None


def configure(settings: Settings) -> None:
    global _settings
    _settings = settings


def _is_csv_upload(file: UploadFile) -> bool:
    allowed_types = {"text/csv", "application/csv", "application/vnd.ms-excel"}
    file_name = (file.filename or "").lower()
    return file_name.endswith(".csv") or file.content_type in allowed_types


def _validate_csv_bytes(raw_bytes: bytes) -> int:
    """Validate CSV content. Returns the number of data rows."""
    try:
        decoded = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid UTF-8 CSV payload: {}".format(exc)) from exc
    reader = csv.reader(io.StringIO(decoded))
    headers = next(reader, None)
    if not headers:
        raise HTTPException(status_code=400, detail="CSV is missing header row")
    ok_headers, missing = validate_csv_headers(headers)
    if not ok_headers:
        raise HTTPException(
            status_code=400,
            detail="Missing required CSV columns: {}".format(", ".join(missing)),
        )
    row_count = sum(1 for _ in reader)
    return row_count


def _run_job(job_id: str, csv_path: Path, log_path: Path, settings: Settings) -> None:
    db.update_job_running(job_id)

    def write_log(message: str) -> None:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write("{}\n".format(message))

    try:
        result = ingest_csv(
            application_id=settings.application_id,
            csv_path=str(csv_path),
            profile_id=settings.resolved_device_profile_id,
            log=write_log,
        )
        errors_path = csv_path.with_suffix(".errors.json")
        with errors_path.open("w", encoding="utf-8") as handle:
            json.dump(result.to_dict()["errors"], handle, indent=2)
        final_status = "completed" if result.failed == 0 else "completed_with_errors"
        db.update_job_finished(job_id, final_status, result.ok, result.skipped, result.failed)
    except Exception as exc:  # noqa: BLE001
        write_log("[FATAL] {}".format(exc))
        db.update_job_finished(job_id, "failed", 0, 0, 1)


@router.post("/upload", response_model=JobCreated, status_code=202)
async def upload_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    auth: AuthContext = Depends(require_auth),
):
    if not _is_csv_upload(file):
        raise HTTPException(status_code=400, detail="Only CSV uploads are accepted")

    raw_bytes = file.file.read(_settings.max_upload_bytes + 1)
    if len(raw_bytes) > _settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail="Upload exceeds limit of {} bytes".format(_settings.max_upload_bytes),
        )
    total_rows = _validate_csv_bytes(raw_bytes)

    upload_dir = _settings.resolved_upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)

    job_id = str(uuid.uuid4())
    csv_path = upload_dir / "{}.csv".format(job_id)
    log_path = upload_dir / "{}.log".format(job_id)
    csv_path.write_bytes(raw_bytes)

    db.insert_job(
        job_id=job_id,
        log_path=str(log_path),
        total_rows=total_rows,
        operator_email=auth.operator_email,
    )
    background_tasks.add_task(_run_job, job_id, csv_path, log_path, _settings)
    return JobCreated(job_id=job_id)


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(
    auth: AuthContext = Depends(require_auth),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    items = db.list_jobs(limit=limit, offset=offset)
    total = db.total_jobs()
    return JobListResponse(
        items=[JobSummary(**j) for j in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/jobs/{job_id}", response_model=JobDetail)
def get_job_status(
    job_id: str,
    auth: AuthContext = Depends(require_auth),
):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    upload_dir = _settings.resolved_upload_dir
    csv_path = upload_dir / "{}.csv".format(job_id)
    errors = db.read_errors_file(csv_path.with_suffix(".errors.json"))
    log_tail = db.read_log_tail(Path(job["log_path"]))

    return JobDetail(
        **{k: v for k, v in job.items() if k not in ("errors", "log_excerpt")},
        errors=errors,
        log_excerpt=log_tail,
    )
