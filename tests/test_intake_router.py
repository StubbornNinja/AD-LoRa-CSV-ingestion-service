from unittest.mock import patch

from ingest.csv_to_chirpstack import IngestResult


VALID_CSV = (
    "DEVEUI,APPEUI,APPKEY,DEVADDR,NWKSKEY,APPSKEY\n"
    "0011223344556677,0000000000000000,00112233445566778899aabbccddeeff,00000000,00,00\n"
)


def test_upload_requires_auth(app_client):
    resp = app_client.post(
        "/api/v1/intake/upload",
        files={"file": ("devices.csv", VALID_CSV, "text/csv")},
    )
    assert resp.status_code == 401


def test_upload_rejects_non_csv(app_client, auth_header):
    resp = app_client.post(
        "/api/v1/intake/upload",
        headers=auth_header,
        files={"file": ("devices.txt", "not csv", "text/plain")},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["ok"] is False
    assert "CSV" in body["error"]["message"]


def test_upload_rejects_missing_headers(app_client, auth_header):
    resp = app_client.post(
        "/api/v1/intake/upload",
        headers=auth_header,
        files={"file": ("devices.csv", "DEVEUI,APPEUI\nabcd,efgh\n", "text/csv")},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["ok"] is False
    assert "Missing required CSV columns" in body["error"]["message"]


def test_upload_rejects_oversized_payload(app_client, auth_header, test_settings):
    test_settings.max_upload_bytes = 512
    # Need to recreate app with small limit
    from ingest.app import create_app
    from fastapi.testclient import TestClient

    small_app = create_app(settings=test_settings)
    client = TestClient(small_app)

    content = "A" * 513
    resp = client.post(
        "/api/v1/intake/upload",
        headers=auth_header,
        files={"file": ("devices.csv", content, "text/csv")},
    )
    assert resp.status_code == 413
    body = resp.json()
    assert body["ok"] is False


def test_upload_happy_path(app_client, auth_header):
    with patch(
        "ingest.routers.intake.ingest_csv",
        return_value=IngestResult(ok=1, skipped=0, failed=0, errors=[]),
    ):
        resp = app_client.post(
            "/api/v1/intake/upload",
            headers=auth_header,
            files={"file": ("devices.csv", VALID_CSV, "text/csv")},
        )
    assert resp.status_code == 202
    body = resp.json()
    assert body["ok"] is True
    assert body["data"]["status"] == "queued"
    assert body["data"]["job_id"]

    job_id = body["data"]["job_id"]
    status_resp = app_client.get(f"/api/v1/intake/jobs/{job_id}", headers=auth_header)
    assert status_resp.status_code == 200
    job = status_resp.json()["data"]
    assert job["status"] == "completed"
    assert job["ok"] == 1
    assert job["total_rows"] == 1


def test_jobs_list_returns_paginated(app_client, auth_header):
    # Upload a job first
    with patch(
        "ingest.routers.intake.ingest_csv",
        return_value=IngestResult(ok=1, skipped=0, failed=0, errors=[]),
    ):
        app_client.post(
            "/api/v1/intake/upload",
            headers=auth_header,
            files={"file": ("devices.csv", VALID_CSV, "text/csv")},
        )

    resp = app_client.get("/api/v1/intake/jobs", headers=auth_header)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "items" in body["data"]
    assert "total" in body["data"]
    assert body["data"]["total"] >= 1
    assert body["data"]["limit"] == 20
    assert body["data"]["offset"] == 0


def test_job_not_found(app_client, auth_header):
    resp = app_client.get("/api/v1/intake/jobs/nonexistent-id", headers=auth_header)
    assert resp.status_code == 404
    body = resp.json()
    assert body["ok"] is False
