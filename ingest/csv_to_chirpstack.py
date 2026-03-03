#!/usr/bin/env python3

import csv
import os
import sys
import requests

CHIRPSTACK_API_URL = os.getenv("CHIRPSTACK_API_URL", "http://localhost:8090/api")
API_TOKEN = os.getenv("CHIRPSTACK_API_TOKEN")

if not API_TOKEN:
    print("ERROR: CHIRPSTACK_API_TOKEN not set")
    sys.exit(1)

LW010_PROFILE_ID = os.getenv("LW010_PROFILE_ID")

if not LW010_PROFILE_ID:
    print("ERROR: LW010_PROFILE_ID not set")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
}

REQUIRED_COLUMNS = ["DEVEUI", "APPEUI", "APPKEY", "DEVADDR", "NWKSKEY", "APPSKEY"]

def normalize_hex(value: str) -> str:
    v = (value or "").strip().lower()
    if v.startswith("0x"):
        v = v[2:]
    return v

def validate_row(row: dict, rownum: int) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in row]
    if missing:
        raise ValueError(f"Row {rownum}: missing columns {missing}")

    dev_eui = normalize_hex(row["DEVEUI"])
    appkey = normalize_hex(row["APPKEY"])

    if len(dev_eui) != 16:
        raise ValueError(f"Row {rownum}: DEVEUI must be 16 hex chars (8 bytes), got '{row['DEVEUI']}'")
    if len(appkey) != 32:
        raise ValueError(f"Row {rownum}: APPKEY must be 32 hex chars (16 bytes), got '{row['APPKEY']}'")

def device_exists(dev_eui: str) -> bool:
    r = requests.get(f"{CHIRPSTACK_API_URL}/devices/{dev_eui}", headers=HEADERS)
    return r.status_code == 200

def create_device(application_id: str, dev_eui: str) -> None:
    payload = {
      "device": {
        "applicationId": application_id,
        "deviceProfileId": LW010_PROFILE_ID,
        "devEui": dev_eui,
        "name": dev_eui,
        "description": "Imported via CSV",
        "isDisabled": False,
        "skipFcntCheck": False,
      }
    }
    r = requests.post(f"{CHIRPSTACK_API_URL}/devices", headers=HEADERS, json=payload)
    if r.status_code not in (200, 201):
        raise RuntimeError(r.text)

def set_device_keys(dev_eui: str, appkey: str) -> None:
    payload = {
        "deviceKeys": {
            "devEui": dev_eui,
            "nwkKey": appkey,
        }
    }
    r = requests.post(f"{CHIRPSTACK_API_URL}/devices/{dev_eui}/keys", headers=HEADERS, json=payload)
    if r.status_code not in (200, 201):
        raise RuntimeError(r.text)

def ingest_csv(application_id: str, csv_path: str) -> int:
    ok = 0
    fail = 0

    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)

        for i, row in enumerate(reader, start=2):  # header is line 1
            try:
                validate_row(row, i)
                dev_eui = normalize_hex(row["DEVEUI"])
                appkey = normalize_hex(row["APPKEY"])

                if device_exists(dev_eui):
                    print(f"[SKIP] {dev_eui} already exists")
                    continue

                create_device(application_id, dev_eui)
                set_device_keys(dev_eui, appkey)

                print(f"[OK] {dev_eui}")
                ok += 1
            except Exception as e:
                print(f"[ERROR] line {i}: {e}")
                fail += 1

    print(f"Done. ok={ok} fail={fail}")
    return 0 if fail == 0 else 2

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: csv_to_chirpstack.py <APPLICATION_ID> <CSV_FILE>")
        sys.exit(1)

    sys.exit(ingest_csv(sys.argv[1], sys.argv[2]))
