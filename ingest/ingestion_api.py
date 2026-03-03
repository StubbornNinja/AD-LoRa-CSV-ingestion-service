import os
import uuid
import subprocess
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Header, HTTPException
from fastapi.responses import JSONResponse

# Resolve paths relative to this file's location
BASE_DIR = Path(__file__).resolve().parent
CSV_SCRIPT = BASE_DIR / "csv_to_chirpstack.py"

INGEST_API_TOKEN = os.getenv("INGEST_API_TOKEN")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", str(BASE_DIR.parent / "uploads"))
APPLICATION_ID = os.getenv("APPLICATION_ID")

if not INGEST_API_TOKEN:
    raise RuntimeError("INGEST_API_TOKEN not set")
if not APPLICATION_ID:
    raise RuntimeError("APPLICATION_ID not set")

os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="ChirpStack CSV Ingest")


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/upload")
async def upload_csv(
    file: UploadFile = File(...),
    authorization: str = Header(None),
):
    if authorization != f"Bearer {INGEST_API_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV only")

    job_id = str(uuid.uuid4())
    dest = os.path.join(UPLOAD_DIR, f"{job_id}.csv")

    with open(dest, "wb") as out:
        out.write(await file.read())

    # Run the CSV-to-ChirpStack script against the uploaded file.
    # Open the log file inside a with-statement so the handle is properly closed
    # in the parent process. The child process inherits a copy of the fd.
    log_path = f"{dest}.log"
    with open(log_path, "w") as log_fh:
        subprocess.Popen(
            ["python3", str(CSV_SCRIPT), APPLICATION_ID, dest],
            stdout=log_fh,
            stderr=subprocess.STDOUT,
        )

    return JSONResponse({"job_id": job_id, "status": "accepted"})
