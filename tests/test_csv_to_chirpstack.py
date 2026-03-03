import tempfile

from ingest.csv_to_chirpstack import ingest_csv, key_field_for_mac_version, normalize_hex


class FakeChirpStackClient:
    def __init__(self, mac_version: str):
        self.mac_version = mac_version
        self.keys_payloads = []
        self.created = []

    def get_device_profile_mac_version(self, profile_id: str) -> str:
        return self.mac_version

    def device_exists(self, dev_eui: str) -> bool:
        return False

    def create_device(self, application_id: str, profile_id: str, dev_eui: str) -> None:
        self.created.append((application_id, profile_id, dev_eui))

    def set_device_key(self, dev_eui: str, key_field: str, key_value: str) -> None:
        self.keys_payloads.append({"dev_eui": dev_eui, key_field: key_value})


def _write_csv() -> str:
    payload = (
        "DEVEUI,APPEUI,APPKEY,DEVADDR,NWKSKEY,APPSKEY\n"
        "c93b87ffffee0ddf,70b3d57ed0026b87,2b7e151628aed2a6abf7c93b87ee0ddf,42496b13,1122,3344\n"
    )
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv") as handle:
        handle.write(payload)
        return handle.name


def test_normalize_hex():
    assert normalize_hex(" 0xAABBCC ") == "aabbcc"


def test_key_selection_lorawan_10x_uses_appkey():
    assert key_field_for_mac_version("LORAWAN_1_0_4") == "appKey"


def test_key_selection_lorawan_11_uses_nwkkey():
    assert key_field_for_mac_version("LORAWAN_1_1_0") == "nwkKey"


def test_ingest_posts_appkey_for_lw010_profile():
    csv_path = _write_csv()
    client = FakeChirpStackClient(mac_version="LORAWAN_1_0_3")

    result = ingest_csv(
        application_id="app-id",
        csv_path=csv_path,
        profile_id="lw010-profile",
        client=client,
    )

    assert result.ok == 1
    assert result.failed == 0
    assert "appKey" in client.keys_payloads[0]


def test_ingest_posts_nwkkey_for_lorawan_11_profile():
    csv_path = _write_csv()
    client = FakeChirpStackClient(mac_version="LORAWAN_1_1_0")

    result = ingest_csv(
        application_id="app-id",
        csv_path=csv_path,
        profile_id="lorawan11-profile",
        client=client,
    )

    assert result.ok == 1
    assert result.failed == 0
    assert "nwkKey" in client.keys_payloads[0]
