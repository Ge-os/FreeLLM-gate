from __future__ import annotations

from typing import Any

from app.services.rate_limiter import RateLimiter
from app.services.runtime_types import RouteCandidate, ScoredCandidate


class NoHealthyCandidateError(RuntimeError):
    pass


class LoadBalancer:
    def __init__(self, rate_limiter: RateLimiter, recent_request_penalty: float) -> None:
        self._rate_limiter = rate_limiter
        self._penalty = recent_request_penalty

    async def pick(
        self,
        candidates: list[RouteCandidate],
        payload: dict[str, Any] | None,
    ) -> ScoredCandidate:
        if not candidates:
            raise NoHealthyCandidateError("No providers configured for this endpoint/model")

        estimated_tokens = self._rate_limiter.estimate_request_tokens(payload)
        scored: list[ScoredCandidate] = []

        for candidate in candidates:
            if not await self._rate_limiter.can_accept(candidate, estimated_tokens):
                continue

            tokens_left = await self._rate_limiter.tokens_left_score(candidate)
            recent_requests = await self._rate_limiter.recent_requests(candidate)
            score = float(tokens_left) - float(recent_requests) * float(self._penalty)
            scored.append(
                ScoredCandidate(
                    candidate=candidate,
                    score=score,
                    tokens_left=tokens_left,
                    recent_requests=recent_requests,
                )
            )

        if not scored:
            raise NoHealthyCandidateError("All candidate providers are rate-limited")

        scored.sort(key=lambda item: item.score, reverse=True)
        for scored_candidate in scored:
            reserved = await self._rate_limiter.reserve(scored_candidate.candidate, estimated_tokens)
            if reserved:
                return scored_candidate

        raise NoHealthyCandidateError("Unable to reserve capacity for any candidate provider")
