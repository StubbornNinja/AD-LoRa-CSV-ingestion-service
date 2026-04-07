import pytest
from fastapi.testclient import TestClient

from ingest.config import Settings


@pytest.fixture
def test_settings(tmp_path):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    db_path = tmp_path / "jobs.db"
    return Settings(
        ingest_api_token="test-token",
        application_id="app-uuid",
        device_profile_id="profile-uuid",
        chirpstack_api_url="http://localhost:8080/api",
        chirpstack_api_token="fake-chirpstack-token",
        upload_dir=str(upload_dir),
        db_path=str(db_path),
        max_upload_bytes=10 * 1024 * 1024,
    )


@pytest.fixture
def app_client(test_settings):
    from ingest.app import create_app

    app = create_app(settings=test_settings)
    return TestClient(app)


@pytest.fixture
def auth_header():
    return {"Authorization": "Bearer test-token"}
