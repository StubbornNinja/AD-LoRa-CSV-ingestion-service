# DEPRECATED: Use ingest.app:create_app instead.
# This module exists for backward compatibility.
# Run with: uvicorn ingest.app:create_app --factory
from ingest.app import create_app  # noqa: F401
