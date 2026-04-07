# Legacy tests — validates backward-compat shim still imports.
# Full test coverage is in test_intake_router.py, test_auth.py, test_envelope.py.


def test_shim_exports_create_app():
    from ingest.ingestion_api import create_app

    assert callable(create_app)
