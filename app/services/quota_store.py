from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

try:
    import redis.asyncio as redis
except ImportError:  # pragma: no cover - optional dependency
    redis = None


@dataclass(slots=True)
class _CounterRecord:
    value: int
    expires_at: float | None


class _InMemoryCounterStore:
    def __init__(self) -> None:
        self._records: dict[str, _CounterRecord] = {}
        self._lock = asyncio.Lock()

    def _purge_expired(self) -> None:
        now = time.time()
        expired_keys = [
            key for key, record in self._records.items() if record.expires_at and record.expires_at <= now
        ]
        for key in expired_keys:
            self._records.pop(key, None)

    async def get(self, key: str) -> int:
        async with self._lock:
            self._purge_expired()
            record = self._records.get(key)
            return record.value if record else 0

    async def incr(self, key: str, amount: int = 1, ttl: int | None = None) -> int:
        async with self._lock:
            self._purge_expired()
            now = time.time()
            existing = self._records.get(key)
            if existing is None:
                expires_at = (now + ttl) if ttl else None
                existing = _CounterRecord(value=0, expires_at=expires_at)
            elif ttl and existing.expires_at is None:
                existing.expires_at = now + ttl

            existing.value += amount
            self._records[key] = existing
            return existing.value


class QuotaStore:
    def __init__(self, redis_url: str, prefix: str = "freellm") -> None:
        self._redis_url = redis_url
        self._prefix = prefix
        self._memory = _InMemoryCounterStore()
        self._redis_client: redis.Redis | None = None

    @property
    def backend(self) -> str:
        return "redis" if self._redis_client else "memory"

    async def connect(self) -> None:
        if redis is None:
            return
        try:
            client = redis.from_url(self._redis_url, decode_responses=True)
            await client.ping()
            self._redis_client = client
        except Exception:
            self._redis_client = None

    async def close(self) -> None:
        if not self._redis_client:
            return
        await self._redis_client.aclose()
        self._redis_client = None

    def _full_key(self, key: str) -> str:
        return f"{self._prefix}:{key}"

    async def get(self, key: str) -> int:
        if not self._redis_client:
            return await self._memory.get(key)

        raw = await self._redis_client.get(self._full_key(key))
        return int(raw) if raw is not None else 0

    async def incr(self, key: str, amount: int = 1, ttl: int | None = None) -> int:
        if not self._redis_client:
            return await self._memory.incr(key, amount=amount, ttl=ttl)

        full_key = self._full_key(key)
        value = await self._redis_client.incrby(full_key, amount)

        if ttl:
            key_ttl = await self._redis_client.ttl(full_key)
            if key_ttl in (-1, -2):
                await self._redis_client.expire(full_key, ttl)

        return int(value)
