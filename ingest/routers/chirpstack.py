from fastapi import APIRouter, Depends, HTTPException

from ingest.auth import AuthContext, require_auth

router = APIRouter(prefix="/chirpstack", tags=["chirpstack"])


@router.get("/devices")
def list_devices(auth: AuthContext = Depends(require_auth)):
    raise HTTPException(status_code=501, detail="Not implemented - Phase 2")


@router.get("/devices/{dev_eui}")
def get_device(dev_eui: str, auth: AuthContext = Depends(require_auth)):
    raise HTTPException(status_code=501, detail="Not implemented - Phase 2")


@router.get("/gateways")
def list_gateways(auth: AuthContext = Depends(require_auth)):
    raise HTTPException(status_code=501, detail="Not implemented - Phase 2")
