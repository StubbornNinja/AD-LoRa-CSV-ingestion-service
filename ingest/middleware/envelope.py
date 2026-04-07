import json

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

SKIP_PATHS = {"/api/docs", "/api/openapi.json", "/api/redoc"}

# Header used to signal that a response is already enveloped (set by exception handlers)
ENVELOPE_HEADER = "X-Envelope-Applied"


class EnvelopeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        response = await call_next(request)

        # Skip if already enveloped by exception handler
        if response.headers.get(ENVELOPE_HEADER):
            return response

        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response

        body_bytes = b""
        async for chunk in response.body_iterator:
            body_bytes += chunk if isinstance(chunk, bytes) else chunk.encode()

        try:
            original = json.loads(body_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return Response(
                content=body_bytes,
                status_code=response.status_code,
                headers=dict(response.headers),
            )

        if 200 <= response.status_code < 300:
            wrapped = {"ok": True, "data": original}
        else:
            if isinstance(original, dict):
                message = original.get("detail") or original.get("message") or "Unknown error"
            else:
                message = str(original)
            if isinstance(message, dict):
                message = message.get("message", str(message))
            wrapped = {"ok": False, "error": {"message": str(message), "code": response.status_code}}

        return Response(
            content=json.dumps(wrapped),
            status_code=response.status_code,
            media_type="application/json",
        )
