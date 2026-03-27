from __future__ import annotations

from typing import Any

from app.services.quota_store import QuotaStore
from app.services.runtime_types import ModelLimits, RouteCandidate

MINUTE = 60
DAY = 60 * 60 * 24
MONTH = DAY * 30


class RateLimiter:
    def __init__(self, store: QuotaStore) -> None:
        self._store = store

    @staticmethod
    def estimate_request_tokens(payload: dict[str, Any] | None) -> int:
        if not payload:
            return 0

        if isinstance(payload.get("max_tokens"), int):
            return max(payload["max_tokens"], 0)

        if isinstance(payload.get("max_completion_tokens"), int):
            return max(payload["max_completion_tokens"], 0)

        if isinstance(payload.get("input"), str):
            return max(len(payload["input"]) // 4, 1)

        messages = payload.get("messages")
        if isinstance(messages, list):
            total_chars = 0
            for message in messages:
                if not isinstance(message, dict):
                    continue
                content = message.get("content")
                if isinstance(content, str):
                    total_chars += len(content)
                elif isinstance(content, list):
                    for chunk in content:
                        if isinstance(chunk, dict) and isinstance(chunk.get("text"), str):
                            total_chars += len(chunk["text"])
            return max(total_chars // 4, 1)

        prompt = payload.get("prompt")
        if isinstance(prompt, str):
            return max(len(prompt) // 4, 1)

        return 0

    def _key(self, candidate: RouteCandidate, metric: str) -> str:
        return f"quota:{candidate.quota_key}:{metric}"

    async def _get(self, candidate: RouteCandidate, metric: str) -> int:
        return await self._store.get(self._key(candidate, metric))

    async def _incr(
        self,
        candidate: RouteCandidate,
        metric: str,
        amount: int = 1,
        ttl: int | None = None,
    ) -> int:
        return await self._store.incr(self._key(candidate, metric), amount=amount, ttl=ttl)

    async def recent_requests(self, candidate: RouteCandidate) -> int:
        return await self._get(candidate, "rpm")

    async def tokens_left_score(self, candidate: RouteCandidate) -> int:
        limits = candidate.model_limits
        if not limits:
            return 1_000_000

        if limits.token_per_minute:
            used = await self._get(candidate, "tpm")
            return max(limits.token_per_minute - used, 0)

        if limits.requests_per_day:
            used_requests = await self._get(candidate, "rpd")
            return max((limits.requests_per_day - used_requests) * 1000, 0)

        return 1_000_000

    async def can_accept(self, candidate: RouteCandidate, estimated_tokens: int) -> bool:
        limits = candidate.model_limits
        if not limits:
            return True

        if limits.input_token_limit and estimated_tokens > limits.input_token_limit:
            return False

        if limits.requests_per_minute is not None:
            current_rpm = await self._get(candidate, "rpm")
            if current_rpm >= limits.requests_per_minute:
                return False

        if limits.requests_per_day is not None:
            current_rpd = await self._get(candidate, "rpd")
            if current_rpd >= limits.requests_per_day:
                return False

        if limits.requests_per_month is not None:
            current_rpmth = await self._get(candidate, "rpmth")
            if current_rpmth >= limits.requests_per_month:
                return False

        if limits.token_per_minute is not None:
            current_tpm = await self._get(candidate, "tpm")
            if current_tpm + max(estimated_tokens, 0) > limits.token_per_minute:
                return False

        return True

    async def reserve(self, candidate: RouteCandidate, estimated_tokens: int) -> bool:
        if not await self.can_accept(candidate, estimated_tokens):
            return False

        await self._incr(candidate, "rpm", amount=1, ttl=MINUTE)
        await self._incr(candidate, "rpd", amount=1, ttl=DAY)
        await self._incr(candidate, "rpmth", amount=1, ttl=MONTH)

        if estimated_tokens > 0:
            await self._incr(candidate, "tpm", amount=estimated_tokens, ttl=MINUTE)

        return True

    async def record_usage(self, candidate: RouteCandidate, response_body: dict[str, Any] | None) -> int:
        usage_tokens = self._extract_usage_tokens(response_body)
        if usage_tokens > 0:
            await self._incr(candidate, "tokens_day", amount=usage_tokens, ttl=DAY)
        return usage_tokens

    @staticmethod
    def _extract_usage_tokens(response_body: dict[str, Any] | None) -> int:
        if not response_body:
            return 0

        usage = response_body.get("usage")
        if not isinstance(usage, dict):
            return 0

        for field in ("total_tokens", "input_tokens", "output_tokens"):
            value = usage.get(field)
            if isinstance(value, int) and value > 0:
                return value

        return 0

    @staticmethod
    def merge_limits(primary: ModelLimits | None, fallback: ModelLimits | None) -> ModelLimits | None:
        if primary and fallback:
            merged = ModelLimits(
                input_token_limit=primary.input_token_limit or fallback.input_token_limit,
                output_token_limit=primary.output_token_limit or fallback.output_token_limit,
                default_temperature=primary.default_temperature or fallback.default_temperature,
                max_temperature=primary.max_temperature or fallback.max_temperature,
                default_top_p=primary.default_top_p or fallback.default_top_p,
                default_top_k=primary.default_top_k or fallback.default_top_k,
                thinking=primary.thinking if primary.thinking is not None else fallback.thinking,
                vision=primary.vision if primary.vision is not None else fallback.vision,
                tools=primary.tools if primary.tools is not None else fallback.tools,
                requests_per_minute=primary.requests_per_minute or fallback.requests_per_minute,
                token_per_minute=primary.token_per_minute or fallback.token_per_minute,
                requests_per_day=primary.requests_per_day or fallback.requests_per_day,
                requests_per_month=primary.requests_per_month or fallback.requests_per_month,
                extras={**fallback.extras, **primary.extras},
            )
            return merged
        return primary or fallback
