import importlib
from unittest.mock import patch

from fastapi.testclient import TestClient
from ingest.csv_to_chirpstack import IngestResult


def _load_app(monkeypatch, tmp_path):
    upload_dir = tmp_path / "uploads"
    db_path = tmp_path / "jobs.db"
    monkeypatch.setenv("INGEST_API_TOKEN", "test-token")
    monkeypatch.setenv("APPLICATION_ID", "app-uuid")
    monkeypatch.setenv("DEVICE_PROFILE_ID", "profile-uuid")
    monkeypatch.setenv("CHIRPSTACK_API_URL", "http://localhost:8080/api")
    monkeypatch.setenv("CHIRPSTACK_API_TOKEN", "fake-chirpstack-token")
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "512")

    module = importlib.import_module("ingest.ingestion_api")
    module = importlib.reload(module)
    return module


def test_upload_requires_auth(monkeypatch, tmp_path):
    module = _load_app(monkeypatch, tmp_path)
    client = TestClient(module.app)
    response = client.post(
        "/upload",
        files={"file": ("devices.csv", "DEVEUI,APPEUI,APPKEY,DEVADDR,NWKSKEY,APPSKEY\n", "text/csv")},
    )
    assert response.status_code == 401


def test_upload_rejects_non_csv(monkeypatch, tmp_path):
    module = _load_app(monkeypatch, tmp_path)
    client = TestClient(module.app)
    response = client.post(
        "/upload",
        headers={"Authorization": "Bearer test-token"},
        files={"file": ("devices.txt", "not csv", "text/plain")},
    )
    assert response.status_code == 400


def test_upload_rejects_missing_headers(monkeypatch, tmp_path):
    module = _load_app(monkeypatch, tmp_path)
    client = TestClient(module.app)
    response = client.post(
        "/upload",
        headers={"Authorization": "Bearer test-token"},
        files={"file": ("devices.csv", "DEVEUI,APPEUI\nabcd,efgh\n", "text/csv")},
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"]["message"] == "Missing required CSV columns"


def test_upload_rejects_oversized_payload(monkeypatch, tmp_path):
    module = _load_app(monkeypatch, tmp_path)
    client = TestClient(module.app)
    content = "A" * 513
    response = client.post(
        "/upload",
        headers={"Authorization": "Bearer test-token"},
        files={"file": ("devices.csv", content, "text/csv")},
    )
    assert response.status_code == 413


def test_upload_happy_path(monkeypatch, tmp_path):
    module = _load_app(monkeypatch, tmp_path)
    client = TestClient(module.app)
    csv_content = (
        "DEVEUI,APPEUI,APPKEY,DEVADDR,NWKSKEY,APPSKEY\n"
        "0011223344556677,0000000000000000,00112233445566778899aabbccddeeff,00000000,00,00\n"
    )
    with patch(
        "ingest.ingestion_api.ingest_csv",
        return_value=IngestResult(ok=1, skipped=0, failed=0, errors=[]),
    ):
        upload = client.post(
            "/upload",
            headers={"Authorization": "Bearer test-token"},
            files={"file": ("devices.csv", csv_content, "text/csv")},
        )
    assert upload.status_code == 200
    payload = upload.json()
    assert payload["status"] == "queued"
    assert payload["job_id"]

    status = client.get(
        f"/jobs/{payload['job_id']}",
        headers={"Authorization": "Bearer test-token"},
    )
    assert status.status_code == 200
    job = status.json()
    assert job["status"] == "completed"
    assert job["ok"] == 1
