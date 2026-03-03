import importlib

from fastapi.testclient import TestClient


def _load_app(monkeypatch, tmp_path):
    upload_dir = tmp_path / "uploads"
    db_path = tmp_path / "jobs.db"
    monkeypatch.setenv("INGEST_API_TOKEN", "test-token")
    monkeypatch.setenv("APPLICATION_ID", "app-uuid")
    monkeypatch.setenv("DEVICE_PROFILE_ID", "profile-uuid")
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "64")

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
    content = "A" * 65
    response = client.post(
        "/upload",
        headers={"Authorization": "Bearer test-token"},
        files={"file": ("devices.csv", content, "text/csv")},
    )
    assert response.status_code == 413
