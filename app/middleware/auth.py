from __future__ import annotations

import hmac

from fastapi import status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class GatewayAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, api_key: str | None) -> None:  # type: ignore[override]
        super().__init__(app)
        self._api_key = api_key.strip() if api_key else None

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self._api_key:
            return await call_next(request)

        if request.method.upper() == "OPTIONS":
            return await call_next(request)

        if request.url.path in {"/healthz", "/docs", "/openapi.json", "/redoc"}:
            return await call_next(request)

        provided = self._extract_api_key(request)
        if provided and hmac.compare_digest(provided, self._api_key):
            return await call_next(request)

        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": {"message": "Unauthorized", "type": "auth_error"}},
        )

    @staticmethod
    def _extract_api_key(request: Request) -> str | None:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            if token:
                return token

        x_api_key = request.headers.get("x-api-key", "").strip()
        return x_api_key or None
