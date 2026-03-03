Enhance the existing AD-LoRa-CSV-ingestion-service to production readiness. This includes making the CSV ingestion correct for ChirpStack LoRaWAN profiles, adding job tracking, improving API stability, containerizing the service, hardening for HTTPS exposure, and enabling future expansion (multi-profile / ABP support).

Scope of Work
1) Correct Key Handling Based on Device Profile

Problem:
The current script sends nwkKey unconditionally. ChirpStack v4 with LoRaWAN 1.0.x profiles requires appKey. Without this, device key uploads fail.

Tasks:

Replace hardcoded nwkKey with profile-aware logic:

Detect MAC version from the configured profile (via ChirpStack API).

Use appKey for LoRaWAN 1.0.x profiles.

Use nwkKey for LoRaWAN 1.1 profiles.

Acceptance Criteria:

Unit tests for key field selection.

When using a LW010_PROFILE_ID, script posts {"appKey": "..."}

When using a LoRaWAN 1.1 profile, script posts {"nwkKey": "..."}

Manual CSV import via API + NGINX results in devices with correct keys in ChirpStack.

2) Refactor Ingest Logic to Return Structured Results

Problem:
Right now, the API just spawns a subprocess and returns “accepted” without results.

Tasks:

Refactor csv_to_chirpstack.py into functions callable from Python:

ingest_csv(application_id, csv_path, profile_id)

Return structured result object:

{
  ok: int,
  skipped: int,
  failed: int,
  errors: [ ... ],
}

Acceptance Criteria:

Subprocess mode still works unchanged.

API can import and call ingest_csv() directly without spawning a new process.

3) Add Job Tracking Endpoints

Problem:
Clients can upload but cannot know import success or failure.

Tasks:

Create a SQLite (or JSON) job store under /opt/chirpstack-ingest/jobs.db with schema:

job_id (PK), status, created_at, started_at, finished_at, ok, skipped, failed, log_path

API additions:

POST /upload → creates job entry and returns job_id

GET /jobs/{job_id} → returns job status + metrics

GET /jobs → paginated summary

Acceptance Criteria:

API formal job status tracking implemented.

Upload returns { job_id, status }

Querying a completed job yields detailed results and links/log content.

4) Improve Upload Handling & Validation

Tasks:

Reject non-CSV content early with 400 errors.

Limit upload size (configurable but safe, e.g., 10 MB).

Strong CSV header validation (required columns must be present, fail fast).

Strip BOM / whitespace in headers.

Acceptance Criteria:

Invalid payloads return correct 4xx errors.

CSV issues return structured error messages.

Excessively large files are rejected (API and NGINX should both enforce).

5) Containerize the API Service

Goals:

Dockerfile for ingestion API

Integrate into ChirpStack Docker Compose stack

Ensure automatic restart and network connectivity

Deliverables:

/ingest/Dockerfile

Updated docker-compose.yml snippet

Updated .env.example

Volumes configured for:

/uploads

/jobs.db

Details:

Bind to 127.0.0.1:8000 so only NGINX is exposed publicly.

Use restart: unless-stopped so it auto-starts after VM reboot.

Docker networking allows “chirpstack” service DNS access to ChirpStack API.

Acceptance Criteria:

Service runs via docker compose up -d ingest-api

Exposed uploads API reachable only via localhost through NGINX

Logs persist between container restarts

6) Update Documentation and Env Examples

Tasks:

Update README.md and .env.example:

Clarify meaning of APPLICATION_ID (uuid vs numeric)

Add INGEST_API_TOKEN

Add UPLOAD_DIR, DB_PATH

Show Docker Compose example

Example curl usage with status endpoint

Acceptance Criteria:

Repository README accurately reflects production setup

.env.example provides a usable starting template

7) Security & Hardening

Tasks:

Ensure secrets are not logged (API tokens, keys)

Use proper file permissions on volumes and env files

NGINX must enforce:

Rate limiting

Request size limit

TLS only

Acceptance Criteria:

No sensitive values in stdout/stderr logs

API rejects unauthorized requests reliably

System is safe for public exposure via HTTPS

8) Optional Future Enhancements

These are not blocking, but should be scoped if resources permit:

A) Support ABP provisioning

Add a CSV column like MODE, ABP, or detect if ABP fields are present

Implement ABP activation logic via ChirpStack API

Provide per-row provisioning strategy

B) Multi-profile CSV support

Allow a column like PROFILE_CODE that maps to env vars

Maintain a profile mapping in config

C) Dry-run API

Return validation errors without writing or posting to ChirpStack

Testing & Verification
Manual Testing

Upload a valid CSV via curl POST /upload with auth header.

Poll GET /jobs/{job_id} until completion.

Verify devices appear in ChirpStack UI with correct profiles and keys.

Edge Cases

Missing columns → 400 error

Duplicate devices → skipped

Invalid hex values → recorded as errors, job does not crash

Mixed valid/invalid rows → partial success documented

CI Tests (Suggested)

Fixture CSVs (good, bad, mix)

Unit tests for:

normalize_hex()

profile key selection logic

API responses for bad payloads

End-to-end tests with local ChirpStack test instance (Docker)

Deliverable Artifacts

Updated Python scripts (csv_to_chirpstack.py, ingestion_api.py)

New SQLite job tracking code

Dockerfile and Compose config

Updated docs (README.md, CODEX_PLAN.md, .env.example)

Unit tests

API usage examples

Milestones

CSV ingest correctness & key handling

API structural improvements + job tracking

Containerization + Docker Compose integration

Documentation + production hardening
