# AD-LoRa-CSV-ingestion-service

A FastAPI microservice that accepts CSV uploads containing LoRaWAN device
credentials and automatically registers them in ChirpStack via its REST API.

## Features

- **POST /upload** -- upload a CSV file of device credentials; the service
  validates the file, saves it, and spawns an asynchronous job that registers
  each device in ChirpStack.
- **GET /healthz** -- lightweight health-check endpoint.
- Bearer-token authentication on the upload endpoint.

## CSV Format

The uploaded CSV must contain these columns:

| Column   | Description                         | Example                            |
|----------|-------------------------------------|------------------------------------|
| DEVEUI   | Device EUI (16 hex chars / 8 bytes) | `c93b87ffffee0ddf`                 |
| APPEUI   | Application EUI                     | `70b3d57ed0026b87`                 |
| APPKEY   | Application Key (32 hex chars)      | `2b7e151628aed2a6abf7c93b87ee0ddf` |
| DEVADDR  | Device Address                      | `42496b13`                         |
| NWKSKEY  | Network Session Key                 | (hex string)                       |
| APPSKEY  | App Session Key                     | (hex string)                       |

## Quick Start

```bash
# Clone and enter
git clone <your-repo-url>
cd AD-LoRa-CSV-ingestion-service

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment (copy and edit)
cp .env.example .env
# Edit .env with your real values

# Run the service
uvicorn ingest.ingestion_api:app --host 0.0.0.0 --port 8000
```

## Environment Variables

| Variable              | Required | Default                     | Description                      |
|-----------------------|----------|-----------------------------|----------------------------------|
| CHIRPSTACK_API_URL    | No       | `http://localhost:8090/api` | ChirpStack REST API base URL     |
| CHIRPSTACK_API_TOKEN  | Yes      |                             | ChirpStack API bearer token      |
| INGEST_API_TOKEN      | Yes      |                             | Token for authenticating uploads |
| APPLICATION_ID        | Yes      |                             | ChirpStack application UUID      |
| LW010_PROFILE_ID      | Yes      |                             | Device profile UUID for LW010    |
| UPLOAD_DIR            | No       | `./uploads` (relative)      | Directory for uploaded CSV files |

## Usage

```bash
curl -X POST http://localhost:8000/upload \
  -H "Authorization: Bearer <INGEST_API_TOKEN>" \
  -F "file=@devices.csv"
```

Response:

```json
{"job_id": "5374eb81-c80d-498d-baf6-996089c45f41", "status": "accepted"}
```

Processing logs are written to `uploads/<job_id>.csv.log`.
