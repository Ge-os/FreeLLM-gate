from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse, Response, StreamingResponse

from config import Settings
from app.services.load_balancer import LoadBalancer, NoHealthyCandidateError
from app.services.provider_registry import ProviderRegistry
from app.services.quota_store import QuotaStore
from app.services.rate_limiter import RateLimiter
from app.services.runtime_types import RouteCandidate, ScoredCandidate


class GatewayService:
    _HOP_BY_HOP_RESPONSE_HEADERS = {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "content-length",
    }

    _FORWARDED_REQUEST_HEADERS = {
        "accept",
        "content-type",
        "openai-organization",
        "openai-project",
        "http-referer",
        "x-title",
    }

    def __init__(
        self,
        settings: Settings,
        provider_registry: ProviderRegistry,
        quota_store: QuotaStore,
    ) -> None:
        self._settings = settings
        self._provider_registry = provider_registry
        self._quota_store = quota_store
        self._rate_limiter = RateLimiter(quota_store)
        self._load_balancer = LoadBalancer(
            rate_limiter=self._rate_limiter,
            recent_request_penalty=settings.routing_recent_request_penalty,
        )
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.request_timeout_seconds),
        )

    async def startup(self) -> None:
        await self._quota_store.connect()

    async def shutdown(self) -> None:
        await self._quota_store.close()
        await self._http.aclose()

    def health_payload(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "providers": self._provider_registry.summary(),
            "quota_backend": self._quota_store.backend,
        }

    def list_models(self) -> dict[str, Any]:
        return self._provider_registry.as_openai_models_payload()

    async def transform_request(self, endpoint: str, payload: dict[str, Any] | None) -> dict[str, Any]:
        candidates = self._provider_registry.resolve_candidates(endpoint, payload)
        if not candidates:
            return {
                "endpoint": endpoint,
                "selected": None,
                "reason": "No candidates available",
                "candidates": [],
            }

        estimated_tokens = self._rate_limiter.estimate_request_tokens(payload)
        scored_candidates = await self._score_candidates(candidates)
        selected = scored_candidates[0] if scored_candidates else None

        return {
            "endpoint": endpoint,
            "estimated_tokens": estimated_tokens,
            "selected": self._candidate_payload(selected) if selected else None,
            "candidates": [self._candidate_payload(candidate) for candidate in scored_candidates],
        }

    async def proxy(self, request: Request, endpoint: str) -> Response:
        payload, body_bytes = await self._extract_payload(request)
        return await self._proxy_core(
            request=request,
            endpoint=endpoint,
            payload=payload,
            body_bytes=body_bytes,
        )

    async def proxy_with_payload(
        self,
        request: Request,
        endpoint: str,
        payload: dict[str, Any],
    ) -> Response:
        body_bytes = json.dumps(payload).encode("utf-8")
        return await self._proxy_core(
            request=request,
            endpoint=endpoint,
            payload=payload,
            body_bytes=body_bytes,
        )

    async def _proxy_core(
        self,
        request: Request,
        endpoint: str,
        payload: dict[str, Any] | None,
        body_bytes: bytes | None,
    ) -> Response:
        method = request.method.upper()
        query_params = list(request.query_params.multi_items())
        candidates = self._provider_registry.resolve_candidates(endpoint, payload)

        try:
            scored = await self._load_balancer.pick(candidates, payload)
        except NoHealthyCandidateError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

        selected = scored.candidate
        upstream_url = self._build_upstream_url(selected.provider.base_url, endpoint)

        outbound_headers = self._build_upstream_headers(request, selected)
        outbound_payload = dict(payload) if isinstance(payload, dict) else payload
        if isinstance(outbound_payload, dict) and selected.model and "model" not in outbound_payload:
            outbound_payload["model"] = selected.model

        if method == "POST" and isinstance(outbound_payload, dict) and outbound_payload.get("stream") is True:
            return await self._proxy_stream(
                method=method,
                url=upstream_url,
                selected=selected,
                query_params=query_params,
                headers=outbound_headers,
                json_payload=outbound_payload,
            )

        response = await self._send_request(
            method=method,
            url=upstream_url,
            query_params=query_params,
            headers=outbound_headers,
            json_payload=outbound_payload if isinstance(outbound_payload, dict) else None,
            raw_body=body_bytes if not isinstance(outbound_payload, dict) else None,
        )

        return await self._to_fastapi_response(response=response, selected=selected)

    async def invoke_sagemaker_messages(self, payload: dict[str, Any], request: Request) -> Response:
        transformed: dict[str, Any] = {
            "messages": [{"role": "user", "content": payload.get("inputs", "")}],
        }

        if isinstance(payload.get("parameters"), dict):
            transformed.update(payload["parameters"])

        # Keep explicit model if user provided one in parameters.
        if isinstance(payload.get("model"), str) and payload["model"].strip():
            transformed["model"] = payload["model"].strip()

        return await self.proxy_with_payload(request, "/v1/chat/completions", transformed)

    async def _extract_payload(self, request: Request) -> tuple[dict[str, Any] | None, bytes | None]:
        body = await request.body()
        if not body:
            return None, None

        content_type = request.headers.get("content-type", "").lower()
        if "application/json" not in content_type:
            return None, body

        try:
            parsed = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            return None, body

        if isinstance(parsed, dict):
            return parsed, body
        return None, body

    def _build_upstream_headers(self, request: Request, selected: RouteCandidate) -> dict[str, str]:
        outbound_headers: dict[str, str] = {}
        for key, value in request.headers.items():
            normalized = key.lower()
            if normalized in self._FORWARDED_REQUEST_HEADERS and value:
                outbound_headers[key] = value

        # Caller auth is not forwarded to provider; provider auth is managed by gateway.
        if selected.api_key:
            outbound_headers.update(self._build_auth_header(selected.provider.token_type, selected.api_key))

        outbound_headers.setdefault("User-Agent", "freellm-gate/1.0")
        return outbound_headers

    @staticmethod
    def _build_auth_header(token_type: str, token: str) -> dict[str, str]:
        normalized = token_type.strip().lower().replace("-", "_").replace(" ", "_")

        if normalized in {"bearer", "oauth2"}:
            return {"Authorization": f"Bearer {token}"}
        if normalized == "basic":
            return {"Authorization": f"Basic {token}"}
        if normalized in {"api_key", "api_token", "x_api_key"}:
            return {"x-api-key": token}
        if normalized == "authorization":
            return {"Authorization": token}

        # Safe default for most OpenAI-compatible providers.
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def _build_upstream_url(base_url: str, endpoint: str) -> str:
        trimmed_base = base_url.rstrip("/")
        normalized_endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        endpoint_path = normalized_endpoint.lstrip("/")

        base_path = urlparse(trimmed_base).path.rstrip("/")
        if endpoint_path.startswith("v1/") and (
            base_path.endswith("/v1")
            or base_path.endswith("/api/v1")
            or base_path.endswith("/openai/v1")
            or base_path.endswith("/v1beta/openai")
        ):
            endpoint_path = endpoint_path[len("v1/") :]

        return f"{trimmed_base}/{endpoint_path}"

    async def _send_request(
        self,
        method: str,
        url: str,
        query_params: list[tuple[str, str]],
        headers: dict[str, str],
        json_payload: dict[str, Any] | None,
        raw_body: bytes | None,
    ) -> httpx.Response:
        try:
            return await self._http.request(
                method,
                url,
                params=query_params,
                headers=headers,
                json=json_payload,
                content=raw_body,
            )
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Upstream timeout: {exc}",
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Upstream request failed: {exc}",
            ) from exc

    async def _to_fastapi_response(
        self,
        response: httpx.Response,
        selected: RouteCandidate,
    ) -> Response:
        content_type = response.headers.get("content-type", "")
        filtered_headers = {
            key: value
            for key, value in response.headers.items()
            if key.lower() not in self._HOP_BY_HOP_RESPONSE_HEADERS
        }

        if "application/json" in content_type.lower():
            try:
                payload = response.json()
            except json.JSONDecodeError:
                payload = {"error": {"message": response.text}}

            if isinstance(payload, dict):
                await self._rate_limiter.record_usage(selected, payload)

            json_headers = {
                key: value for key, value in filtered_headers.items() if key.lower() != "content-type"
            }
            return JSONResponse(
                content=payload,
                status_code=response.status_code,
                headers=json_headers,
            )

        return Response(
            content=response.content,
            status_code=response.status_code,
            media_type=content_type or None,
            headers=filtered_headers,
        )

    async def _proxy_stream(
        self,
        method: str,
        url: str,
        selected: RouteCandidate,
        query_params: list[tuple[str, str]],
        headers: dict[str, str],
        json_payload: dict[str, Any],
    ) -> StreamingResponse:
        try:
            upstream = await self._http.send(
                self._http.build_request(
                    method=method,
                    url=url,
                    params=query_params,
                    headers=headers,
                    json=json_payload,
                ),
                stream=True,
            )
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Upstream timeout: {exc}",
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Upstream stream request failed: {exc}",
            ) from exc

        if upstream.status_code >= 400:
            error_body = await upstream.aread()
            await upstream.aclose()
            return Response(
                content=error_body,
                status_code=upstream.status_code,
                media_type=upstream.headers.get("content-type"),
            )

        async def _iter() -> AsyncIterator[bytes]:
            try:
                async for chunk in upstream.aiter_raw():
                    yield chunk
            finally:
                await upstream.aclose()

        await self._rate_limiter.record_usage(selected, None)

        forward_headers = {
            key: value
            for key, value in upstream.headers.items()
            if key.lower() not in self._HOP_BY_HOP_RESPONSE_HEADERS
        }

        return StreamingResponse(
            _iter(),
            status_code=upstream.status_code,
            media_type=upstream.headers.get("content-type", "text/event-stream"),
            headers=forward_headers,
        )

    async def _score_candidates(self, candidates: list[RouteCandidate]) -> list[ScoredCandidate]:
        scored: list[ScoredCandidate] = []
        for candidate in candidates:
            tokens_left = await self._rate_limiter.tokens_left_score(candidate)
            recent_requests = await self._rate_limiter.recent_requests(candidate)
            score = float(tokens_left) - float(recent_requests) * float(
                self._settings.routing_recent_request_penalty
            )
            scored.append(
                ScoredCandidate(
                    candidate=candidate,
                    score=score,
                    tokens_left=tokens_left,
                    recent_requests=recent_requests,
                )
            )

        scored.sort(key=lambda item: item.score, reverse=True)
        return scored

    @staticmethod
    def _candidate_payload(candidate: ScoredCandidate) -> dict[str, Any]:
        return {
            "provider": candidate.candidate.provider.name,
            "base_url": candidate.candidate.provider.base_url,
            "model": candidate.candidate.model,
            "key_slot": candidate.candidate.key_slot,
            "score": candidate.score,
            "tokens_left": candidate.tokens_left,
            "recent_requests": candidate.recent_requests,
        }
