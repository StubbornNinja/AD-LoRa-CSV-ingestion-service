# CODEX_PLAN.md — AD-LoRa-CSV-Ingestion-Service

## Current State (as of 2026-03-03)

Fixes 1-6 from the previous review cycle have been applied. The fatal Docker bugs (networking + volume mount) are resolved, ChirpStack credential validation was added, `to_dict()` was simplified, `.gitignore` was cleaned up, and a happy-path test was added.

**However, the happy-path test has a bug that will cause it to fail at runtime.** This was not caught because Codex could only run `py_compile` (syntax check) — `pytest` was not available in its environment.

---

## REMAINING FIX — Happy-path test `AttributeError` (BUG)

**Problem:**
In `tests/test_ingestion_api.py` line 76, the test references `module.IngestResult`:

```python
return_value=module.IngestResult(ok=1, skipped=0, failed=0, errors=[]),
```

`module` is `ingest.ingestion_api`, but `IngestResult` is **not imported** in that module. The import at `ingest/ingestion_api.py:13` is:

```python
from ingest.csv_to_chirpstack import REQUIRED_COLUMNS, ingest_csv, validate_csv_headers
```

`IngestResult` is not in the import list. This will raise `AttributeError: module 'ingest.ingestion_api' has no attribute 'IngestResult'` when the test runs.

**File:** `tests/test_ingestion_api.py`

**Fix:** Import `IngestResult` directly at the top of the test file:

```python
from ingest.csv_to_chirpstack import IngestResult
```

Then change line 76 from:
```python
return_value=module.IngestResult(ok=1, skipped=0, failed=0, errors=[]),
```

To:
```python
return_value=IngestResult(ok=1, skipped=0, failed=0, errors=[]),
```

---

## Verification Checklist

After the fix is applied:

1. `pytest` — all 9 tests pass (5 csv_to_chirpstack + 4 ingestion_api including happy-path)
2. `docker compose -f docker-compose.ingest.yml build` — image builds successfully
3. `docker compose -f docker-compose.ingest.yml up -d` — service starts
4. `curl http://127.0.0.1:8000/healthz` — returns `{"ok": true}`
5. Verify `./data/jobs.db` is created as a file (not a directory) on the host
6. Service refuses to start if `CHIRPSTACK_API_URL` or `CHIRPSTACK_API_TOKEN` are missing

---

## Previously Completed Items (for reference)

The following items are DONE and should not be re-implemented:

1. **Correct Key Handling** — `key_field_for_mac_version()` in `csv_to_chirpstack.py` selects `appKey` for 1.0.x, `nwkKey` for 1.1. Tests verify this.
2. **Structured Results** — `IngestResult` dataclass with `ok/skipped/failed/errors`. `ingest_csv()` is importable and callable.
3. **Job Tracking** — SQLite schema with `jobs` table. Endpoints: `POST /upload`, `GET /jobs/{job_id}`, `GET /jobs`.
4. **Upload Validation** — CSV-only check, header validation (BOM-safe), configurable `MAX_UPLOAD_BYTES` limit.
5. **Containerization** — Dockerfile (`0.0.0.0` bind) and `docker-compose.ingest.yml` (directory mount for data).
6. **Documentation** — README, `.env.example`, NGINX config example.
7. **Startup Validation** — `CHIRPSTACK_API_URL` and `CHIRPSTACK_API_TOKEN` validated at startup (fail fast).
8. **Security** — Bearer token auth, localhost-only Docker binding, NGINX hardening example in README.

## Future Enhancements (not blocking)

These remain optional and are not part of this fix cycle:

- ABP provisioning support
- Multi-profile CSV support (per-row profile selection)
- Dry-run API endpoint
- Job cleanup / pruning of old SQLite records
- Prometheus metrics / structured logging
