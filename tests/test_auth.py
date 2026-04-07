def test_missing_token_returns_401(app_client):
    resp = app_client.get("/api/v1/intake/jobs")
    assert resp.status_code == 401
    body = resp.json()
    assert body["ok"] is False


def test_wrong_token_returns_401(app_client):
    resp = app_client.get(
        "/api/v1/intake/jobs",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401


def test_valid_token_passes(app_client, auth_header):
    resp = app_client.get("/api/v1/intake/jobs", headers=auth_header)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True


def test_x_forwarded_email_extracted(app_client, auth_header):
    csv_content = (
        "DEVEUI,APPEUI,APPKEY,DEVADDR,NWKSKEY,APPSKEY\n"
        "0011223344556677,0000000000000000,00112233445566778899aabbccddeeff,00000000,00,00\n"
    )
    headers = {**auth_header, "X-Forwarded-Email": "ops@ad-sos.com"}
    from unittest.mock import patch
    from ingest.csv_to_chirpstack import IngestResult

    with patch(
        "ingest.routers.intake.ingest_csv",
        return_value=IngestResult(ok=1, skipped=0, failed=0, errors=[]),
    ):
        resp = app_client.post(
            "/api/v1/intake/upload",
            headers=headers,
            files={"file": ("devices.csv", csv_content, "text/csv")},
        )
    assert resp.status_code == 202
    job_id = resp.json()["data"]["job_id"]

    job_resp = app_client.get(f"/api/v1/intake/jobs/{job_id}", headers=auth_header)
    job = job_resp.json()["data"]
    assert job["operator_email"] == "ops@ad-sos.com"


def test_missing_email_still_succeeds(app_client, auth_header):
    resp = app_client.get("/api/v1/intake/jobs", headers=auth_header)
    assert resp.status_code == 200
