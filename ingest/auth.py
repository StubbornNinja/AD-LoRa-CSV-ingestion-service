from dataclasses import dataclass
from typing import Optional

from fastapi import Header, HTTPException


@dataclass
class AuthContext:
    operator_email: Optional[str] = None


_api_token: Optional[str] = None


def configure(api_token: str) -> None:
    global _api_token
    _api_token = api_token


def require_auth(
    authorization: Optional[str] = Header(None),
    x_forwarded_email: Optional[str] = Header(None, alias="X-Forwarded-Email"),
) -> AuthContext:
    if _api_token is None:
        raise RuntimeError("Auth not configured - call auth.configure() first")
    if authorization != f"Bearer {_api_token}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    return AuthContext(operator_email=x_forwarded_email)
