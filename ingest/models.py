from typing import List, Optional

from pydantic import BaseModel


class JobCreated(BaseModel):
    job_id: str
    status: str = "queued"


class JobSummary(BaseModel):
    job_id: str
    status: str
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    ok: int = 0
    skipped: int = 0
    failed: int = 0
    total_rows: Optional[int] = None
    operator_email: Optional[str] = None
    log_path: Optional[str] = None


class JobDetail(JobSummary):
    errors: List[dict] = []
    log_excerpt: List[str] = []


class JobListResponse(BaseModel):
    items: List[JobSummary]
    total: int
    limit: int
    offset: int


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "1.0.0"
