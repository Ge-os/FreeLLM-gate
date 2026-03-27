from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _normalize_number(value: Any) -> int | None:
    if value in (None, "", "None", "none", "null", "NULL"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


@dataclass(slots=True)
class ModelLimits:
    input_token_limit: int | None = None
    output_token_limit: int | None = None
    default_temperature: float | None = None
    max_temperature: float | None = None
    default_top_p: float | None = None
    default_top_k: int | None = None
    thinking: bool | None = None
    vision: bool | None = None
    tools: bool | None = None

    requests_per_minute: int | None = None
    token_per_minute: int | None = None
    requests_per_day: int | None = None
    requests_per_month: int | None = None

    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "ModelLimits":
        values = dict(raw)
        rpm = _normalize_number(values.pop("requests_per_minute", None))
        tpm = _normalize_number(values.pop("token_per_minute", None))
        rpd = _normalize_number(values.pop("requests_per_day", None))
        rpmth = _normalize_number(
            values.pop("requests_per_month", values.pop("request_per_month", None))
        )
        return cls(
            input_token_limit=_normalize_number(values.pop("input_token_limit", None)),
            output_token_limit=_normalize_number(values.pop("output_token_limit", None)),
            default_temperature=(
                float(values.pop("default_temperature"))
                if values.get("default_temperature") not in (None, "")
                else None
            ),
            max_temperature=(
                float(values.pop("max_temperature"))
                if values.get("max_temperature") not in (None, "")
                else None
            ),
            default_top_p=(
                float(values.pop("default_top_p"))
                if values.get("default_top_p") not in (None, "")
                else None
            ),
            default_top_k=_normalize_number(values.pop("default_top_k", None)),
            thinking=values.pop("thinking", None),
            vision=values.pop("vision", None),
            tools=values.pop("tools", None),
            requests_per_minute=rpm,
            token_per_minute=tpm,
            requests_per_day=rpd,
            requests_per_month=rpmth,
            extras=values,
        )


@dataclass(slots=True)
class ProviderRuntime:
    name: str
    base_url: str
    token_type: str = "Bearer"
    api_keys: list[str] = field(default_factory=list)

    generic_models: list[str] = field(default_factory=list)
    text_models: list[str] = field(default_factory=list)
    tool_models: list[str] = field(default_factory=list)
    vision_models: list[str] = field(default_factory=list)
    embedding_models: list[str] = field(default_factory=list)
    stt_models: list[str] = field(default_factory=list)
    tts_models: list[str] = field(default_factory=list)

    model_limits: dict[str, ModelLimits] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.api_keys = _dedupe_keep_order(self.api_keys)
        self.generic_models = _dedupe_keep_order(self.generic_models)
        self.text_models = _dedupe_keep_order(self.text_models)
        self.tool_models = _dedupe_keep_order(self.tool_models)
        self.vision_models = _dedupe_keep_order(self.vision_models)
        self.embedding_models = _dedupe_keep_order(self.embedding_models)
        self.stt_models = _dedupe_keep_order(self.stt_models)
        self.tts_models = _dedupe_keep_order(self.tts_models)

    @property
    def all_models(self) -> list[str]:
        return _dedupe_keep_order(
            self.generic_models
            + self.text_models
            + self.tool_models
            + self.vision_models
            + self.embedding_models
            + self.stt_models
            + self.tts_models
        )

    def models_for_endpoint(self, endpoint: str) -> list[str]:
        if endpoint == "/v1/embeddings":
            return self.embedding_models or self.all_models
        if endpoint in {
            "/v1/chat/completions",
            "/v1/completions",
            "/v1/responses",
            "/v1/messages",
        }:
            text_like = _dedupe_keep_order(
                self.text_models + self.tool_models + self.vision_models + self.generic_models
            )
            return text_like or self.all_models
        if endpoint.startswith("/v1/images/"):
            return self.vision_models or self.all_models
        if endpoint == "/v1/audio/transcriptions":
            return self.stt_models or self.all_models
        if endpoint == "/v1/audio/speech":
            return self.tts_models or self.all_models
        return self.all_models

    def default_model_for_endpoint(self, endpoint: str) -> str | None:
        models = self.models_for_endpoint(endpoint)
        return models[0] if models else None

    def supports_endpoint(self, endpoint: str, requested_model: str | None) -> bool:
        models = self.models_for_endpoint(endpoint)
        if not models:
            model_dependent_endpoints = {
                "/v1/chat/completions",
                "/v1/completions",
                "/v1/embeddings",
                "/v1/responses",
                "/v1/messages",
                "/v1/images/generations",
                "/v1/images/edits",
                "/v1/audio/transcriptions",
                "/v1/audio/speech",
                "/v1/batches",
            }
            if endpoint in model_dependent_endpoints:
                return False
            # Provider can still be valid for model management endpoints.
            return requested_model in (None, "")
        if not requested_model:
            return True
        return requested_model in models

    def limits_for_model(self, model: str | None) -> ModelLimits | None:
        if not model:
            return None
        return self.model_limits.get(model)


@dataclass(slots=True)
class RouteCandidate:
    provider: ProviderRuntime
    api_key: str | None
    key_slot: int
    model: str | None
    model_limits: ModelLimits | None

    @property
    def quota_key(self) -> str:
        return f"{self.provider.name}:{self.key_slot}:{self.model or 'none'}"


@dataclass(slots=True)
class ScoredCandidate:
    candidate: RouteCandidate
    score: float
    tokens_left: int
    recent_requests: int
