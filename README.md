# AD-LoRa-CSV-ingestion-service

FastAPI service for uploading LoRaWAN CSV credentials and provisioning devices in ChirpStack with tracked import jobs.

## What Changed

- Profile-aware key upload:
  - LoRaWAN 1.0.x device profiles use `appKey`
  - LoRaWAN 1.1 profiles use `nwkKey`
- Ingest logic is callable as Python (`ingest_csv`) and still executable as a CLI script.
- Uploads create persistent jobs in SQLite with status and metrics.
- API now includes:
  - `POST /upload`
  - `GET /jobs/{job_id}`
  - `GET /jobs?limit=&offset=`
  - `GET /healthz`
- Upload validation hardening:
  - CSV-only uploads
  - required headers validation (BOM/whitespace-safe)
  - configurable payload limit (`MAX_UPLOAD_BYTES`, default 10 MiB)

## CSV Requirements

Required columns:

- `DEVEUI`
- `APPEUI`
- `APPKEY`
- `DEVADDR`
- `NWKSKEY`
- `APPSKEY`

## Environment Variables

See `.env.example` for a complete template.

- `CHIRPSTACK_API_URL` (`http://chirpstack:8080/api` in Docker)
- `CHIRPSTACK_API_TOKEN`
- `INGEST_API_TOKEN` (required for API auth)
- `APPLICATION_ID` (ChirpStack **application UUID**)
- `DEVICE_PROFILE_ID` (ChirpStack **device profile UUID**)
- `LW010_PROFILE_ID` (legacy fallback)
- `UPLOAD_DIR` (default `/opt/chirpstack-ingest/uploads`)
- `DB_PATH` (default `/opt/chirpstack-ingest/jobs.db`)
- `MAX_UPLOAD_BYTES` (default `10485760`)

## Local Run

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn ingest.ingestion_api:app --host 127.0.0.1 --port 8000
```

## Docker / Compose

Use `docker-compose.ingest.yml` as a drop-in service snippet for a ChirpStack stack.

```bash
docker compose -f docker-compose.ingest.yml up -d ingest-api
```

The service binds to `127.0.0.1:8000` so it is only reachable via local reverse proxy (for example NGINX).

## API Examples

Upload a CSV:

```bash
curl -X POST http://127.0.0.1:8000/upload \
  -H "Authorization: Bearer ${INGEST_API_TOKEN}" \
  -F "file=@devices.csv"
```

Response:

```json
{"job_id":"<uuid>","status":"queued"}
```

Check job status:

```bash
curl -H "Authorization: Bearer ${INGEST_API_TOKEN}" \
  http://127.0.0.1:8000/jobs/<job_id>
```

List jobs:

```bash
curl -H "Authorization: Bearer ${INGEST_API_TOKEN}" \
  "http://127.0.0.1:8000/jobs?limit=20&offset=0"
```

## NGINX HTTPS Hardening Example

```nginx
limit_req_zone $binary_remote_addr zone=ingest_limit:10m rate=10r/m;

server {
    listen 443 ssl http2;
    server_name ingest.example.com;

    ssl_certificate /etc/letsencrypt/live/ingest.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ingest.example.com/privkey.pem;

    client_max_body_size 10m;

    location / {
        limit_req zone=ingest_limit burst=20 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
    }
}

server {
    listen 80;
    server_name ingest.example.com;
    return 301 https://$host$request_uri;
}
```

## Tests

```bash
pytest
```

Coverage includes key selection, hex normalization, and API bad-payload/auth behavior.
