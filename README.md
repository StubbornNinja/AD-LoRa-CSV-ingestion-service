# AD ChirpStack API Gateway

Unified FastAPI backend for the ActiveDefender ops portal. Provides CSV device provisioning into ChirpStack with tracked import jobs, and will expand to proxy broader ChirpStack data (devices, gateways) in Phase 2.

## Architecture

```
ops.ad-sos.com (frontend VM)
  Browser -> NGINX -> oauth2-proxy -> NGINX proxy
                                        |
                                        | /api/chirpstack/* -> rewrite /api/v1/*
                                        v
                                  This service (:8000)
                                        |
                                        v
                                    ChirpStack API
```

- The frontend never sends Authorization headers. NGINX validates the Google OAuth session and injects a Bearer token + `X-Forwarded-Email` header.
- All responses follow the envelope format: `{"ok": true, "data": {...}}` or `{"ok": false, "error": {"message": "..."}}`

## API Routes

### Phase 1 (current)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Service health check |
| POST | `/api/v1/intake/upload` | Upload CSV file (returns 202 + job_id) |
| GET | `/api/v1/intake/jobs` | List jobs (paginated) |
| GET | `/api/v1/intake/jobs/{job_id}` | Job status + progress + errors |

### Phase 2 (stubs, returns 501)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/chirpstack/devices` | List provisioned devices |
| GET | `/api/v1/chirpstack/devices/{dev_eui}` | Single device detail |
| GET | `/api/v1/chirpstack/gateways` | List gateways |

### OpenAPI Docs

Interactive docs at `/api/docs` when running locally.

## Response Envelope

All JSON responses are wrapped:

```json
// Success (2xx)
{"ok": true, "data": {"job_id": "uuid", "status": "queued"}}

// Error (4xx/5xx)
{"ok": false, "error": {"message": "Human-readable error", "code": 401}}
```

## CSV Requirements

Required columns: `DEVEUI`, `APPEUI`, `APPKEY`, `DEVADDR`, `NWKSKEY`, `APPSKEY`

## Environment Variables

See `.env.example` for a complete template.

| Variable | Required | Description |
|----------|----------|-------------|
| `CHIRPSTACK_API_URL` | Yes | ChirpStack REST API endpoint |
| `CHIRPSTACK_API_TOKEN` | Yes | ChirpStack API Bearer token |
| `INGEST_API_TOKEN` | Yes | Token for authenticating API requests |
| `APPLICATION_ID` | Yes | ChirpStack application UUID |
| `DEVICE_PROFILE_ID` | Yes | ChirpStack device profile UUID |
| `LW010_PROFILE_ID` | No | Legacy fallback profile UUID |
| `INGEST_DATA_DIR` | No | Base data directory (default: `/opt/chirpstack-ingest`) |
| `UPLOAD_DIR` | No | CSV upload directory (default: `{data_dir}/uploads`) |
| `DB_PATH` | No | SQLite database path (default: `{data_dir}/data/jobs.db`) |
| `MAX_UPLOAD_BYTES` | No | Upload size limit (default: `10485760` / 10 MiB) |

## Local Development

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn ingest.app:create_app --factory --host 127.0.0.1 --port 8000
```

## Docker

```bash
docker compose -f docker-compose.ingest.yml up -d ingest-api
```

The service binds to `127.0.0.1:8000` — reachable only via local reverse proxy (NGINX).

## API Examples

Upload a CSV:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/intake/upload \
  -H "Authorization: Bearer ${INGEST_API_TOKEN}" \
  -F "file=@devices.csv"
```

Check job status:

```bash
curl -H "Authorization: Bearer ${INGEST_API_TOKEN}" \
  http://127.0.0.1:8000/api/v1/intake/jobs/<job_id>
```

List jobs:

```bash
curl -H "Authorization: Bearer ${INGEST_API_TOKEN}" \
  "http://127.0.0.1:8000/api/v1/intake/jobs?limit=20&offset=0"
```

## NGINX Config (for frontend VM at ops.ad-sos.com)

```nginx
upstream chirpstack_gateway {
    server <backend-vm-ip>:8000;
}

location /api/chirpstack/ {
    auth_request /oauth2/auth;
    auth_request_set $email $upstream_http_x_auth_request_email;
    error_page 401 = /oauth2/sign_in;

    proxy_set_header Authorization "Bearer <INGEST_API_TOKEN>";
    proxy_set_header X-Forwarded-Email $email;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Host $host;

    rewrite ^/api/chirpstack/(.*)$ /api/v1/$1 break;
    proxy_pass http://chirpstack_gateway;
    client_max_body_size 10m;
}
```

## Tests

```bash
pytest
```

22 tests covering: envelope middleware, auth, CSV validation, intake router, ChirpStack key selection.
