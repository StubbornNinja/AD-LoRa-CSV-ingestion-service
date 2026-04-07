def test_health_returns_envelope(app_client):
    resp = app_client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["data"]["status"] == "healthy"
    assert "version" in body["data"]


def test_401_returns_error_envelope(app_client):
    resp = app_client.post(
        "/api/v1/intake/upload",
        files={"file": ("devices.csv", "content", "text/csv")},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["message"] == "Unauthorized"
    assert body["error"]["code"] == 401


def test_404_returns_error_envelope(app_client, auth_header):
    resp = app_client.get("/api/v1/intake/jobs/nonexistent", headers=auth_header)
    assert resp.status_code == 404
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == 404


def test_501_returns_error_envelope(app_client, auth_header):
    resp = app_client.get("/api/v1/chirpstack/devices", headers=auth_header)
    assert resp.status_code == 501
    body = resp.json()
    assert body["ok"] is False
    assert "Phase 2" in body["error"]["message"]
