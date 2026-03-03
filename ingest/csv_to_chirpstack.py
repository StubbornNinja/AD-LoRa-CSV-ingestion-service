#!/usr/bin/env python3

import csv
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from typing import Callable

import requests

DEFAULT_API_URL = "http://localhost:8090/api"
REQUIRED_COLUMNS = ["DEVEUI", "APPEUI", "APPKEY", "DEVADDR", "NWKSKEY", "APPSKEY"]
HEX_PATTERN = re.compile(r"^[0-9a-f]+$")


@dataclass
class IngestError:
    line: int
    dev_eui: str
    message: str


@dataclass
class IngestResult:
    ok: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[IngestError] = field(default_factory=list)

    def to_dict(self) -> dict:
        result = asdict(self)
        result["errors"] = [asdict(err) for err in self.errors]
        return result


class ChirpStackClient:
    def __init__(self, api_url: str, api_token: str, timeout: int = 20):
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            }
        )

    def device_exists(self, dev_eui: str) -> bool:
        response = self.session.get(f"{self.api_url}/devices/{dev_eui}", timeout=self.timeout)
        if response.status_code == 404:
            return False
        if response.status_code == 200:
            return True
        raise RuntimeError(f"Device lookup failed ({response.status_code})")

    def create_device(self, application_id: str, profile_id: str, dev_eui: str) -> None:
        payload = {
            "device": {
                "applicationId": application_id,
                "deviceProfileId": profile_id,
                "devEui": dev_eui,
                "name": dev_eui,
                "description": "Imported via CSV",
                "isDisabled": False,
                "skipFcntCheck": False,
            }
        }
        response = self.session.post(f"{self.api_url}/devices", json=payload, timeout=self.timeout)
        if response.status_code not in (200, 201):
            raise RuntimeError(f"Create device failed ({response.status_code})")

    def set_device_key(self, dev_eui: str, key_field: str, key_value: str) -> None:
        payload = {"deviceKeys": {"devEui": dev_eui, key_field: key_value}}
        response = self.session.post(
            f"{self.api_url}/devices/{dev_eui}/keys",
            json=payload,
            timeout=self.timeout,
        )
        if response.status_code not in (200, 201):
            raise RuntimeError(f"Set device keys failed ({response.status_code})")

    def get_device_profile_mac_version(self, profile_id: str) -> str:
        response = self.session.get(f"{self.api_url}/device-profiles/{profile_id}", timeout=self.timeout)
        if response.status_code != 200:
            raise RuntimeError(f"Device profile lookup failed ({response.status_code})")
        body = response.json()
        profile = body.get("deviceProfile") or {}
        mac_version = profile.get("macVersion", "")
        if not mac_version:
            raise RuntimeError("Device profile missing macVersion")
        return mac_version


def normalize_header(name: str) -> str:
    return (name or "").replace("\ufeff", "").strip().upper()


def normalize_hex(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized.startswith("0x"):
        normalized = normalized[2:]
    return normalized


def validate_csv_headers(headers: list[str] | None) -> tuple[bool, list[str]]:
    normalized = [normalize_header(h) for h in (headers or [])]
    missing = [col for col in REQUIRED_COLUMNS if col not in normalized]
    return (len(missing) == 0, missing)


def key_field_for_mac_version(mac_version: str) -> str:
    normalized = (mac_version or "").upper()
    if "1_1" in normalized:
        return "nwkKey"
    if "1_0" in normalized:
        return "appKey"
    raise ValueError(f"Unsupported LoRaWAN MAC version: {mac_version}")


def parse_csv_rows(csv_path: str):
    with open(csv_path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        ok_headers, missing = validate_csv_headers(reader.fieldnames)
        if not ok_headers:
            raise ValueError(f"Missing required CSV columns: {missing}")
        for row_num, raw_row in enumerate(reader, start=2):
            normalized_row = {normalize_header(k): (v or "").strip() for k, v in raw_row.items() if k}
            yield row_num, normalized_row


def validate_row(row: dict, row_num: int) -> tuple[str, str]:
    dev_eui = normalize_hex(row.get("DEVEUI", ""))
    app_key = normalize_hex(row.get("APPKEY", ""))

    if len(dev_eui) != 16 or not HEX_PATTERN.fullmatch(dev_eui):
        raise ValueError(f"DEVEUI must be 16 hex chars at line {row_num}")
    if len(app_key) != 32 or not HEX_PATTERN.fullmatch(app_key):
        raise ValueError(f"APPKEY must be 32 hex chars at line {row_num}")
    return dev_eui, app_key


def ingest_csv(
    application_id: str,
    csv_path: str,
    profile_id: str,
    client: ChirpStackClient | None = None,
    log: Callable[[str], None] | None = None,
) -> IngestResult:
    if client is None:
        api_url = os.getenv("CHIRPSTACK_API_URL", DEFAULT_API_URL)
        api_token = os.getenv("CHIRPSTACK_API_TOKEN")
        if not api_token:
            raise RuntimeError("CHIRPSTACK_API_TOKEN not set")
        client = ChirpStackClient(api_url=api_url, api_token=api_token)

    logger = log or (lambda message: None)
    result = IngestResult()
    key_field = key_field_for_mac_version(client.get_device_profile_mac_version(profile_id))
    logger(f"Using key field '{key_field}' for profile {profile_id}")

    for row_num, row in parse_csv_rows(csv_path):
        dev_eui = ""
        try:
            dev_eui, app_key = validate_row(row, row_num)
            if client.device_exists(dev_eui):
                result.skipped += 1
                logger(f"[SKIP] {dev_eui} already exists")
                continue
            client.create_device(application_id=application_id, profile_id=profile_id, dev_eui=dev_eui)
            client.set_device_key(dev_eui=dev_eui, key_field=key_field, key_value=app_key)
            result.ok += 1
            logger(f"[OK] {dev_eui}")
        except Exception as exc:  # noqa: BLE001
            result.failed += 1
            result.errors.append(IngestError(line=row_num, dev_eui=dev_eui, message=str(exc)))
            logger(f"[ERROR] line={row_num} dev_eui={dev_eui or '<unknown>'} error={exc}")

    return result


def main(argv: list[str]) -> int:
    if len(argv) not in (3, 4):
        print("Usage: csv_to_chirpstack.py <APPLICATION_ID> <CSV_FILE> [PROFILE_ID]")
        return 1

    application_id = argv[1]
    csv_path = argv[2]
    profile_id = argv[3] if len(argv) == 4 else os.getenv("LW010_PROFILE_ID") or os.getenv("DEVICE_PROFILE_ID")
    if not profile_id:
        print("ERROR: LW010_PROFILE_ID or DEVICE_PROFILE_ID not set")
        return 1

    result = ingest_csv(application_id=application_id, csv_path=csv_path, profile_id=profile_id, log=print)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
