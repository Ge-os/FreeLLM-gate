from __future__ import annotations

from typing import Any

from config import Settings
from app.services.config_loader import load_provider_runtimes
from app.services.runtime_types import ProviderRuntime, RouteCandidate


class ProviderRegistry:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._providers: dict[str, ProviderRuntime] = {}
        self.reload()

    @property
    def providers(self) -> dict[str, ProviderRuntime]:
        return self._providers

    def reload(self) -> None:
        self._providers = load_provider_runtimes(self._settings)

    def summary(self) -> dict[str, Any]:
        return {
            name: {
                "base_url": provider.base_url,
                "api_keys": len(provider.api_keys),
                "models": len(provider.all_models),
            }
            for name, provider in self._providers.items()
        }

    def as_openai_models_payload(self) -> dict[str, Any]:
        model_to_providers: dict[str, list[str]] = {}
        for provider in self._providers.values():
            for model in provider.all_models:
                model_to_providers.setdefault(model, []).append(provider.name)

        data = [
            {
                "id": model,
                "object": "model",
                "created": 0,
                "owned_by": providers[0],
                "metadata": {"providers": providers},
            }
            for model, providers in sorted(model_to_providers.items())
        ]

        return {"object": "list", "data": data}

    def resolve_candidates(self, endpoint: str, payload: dict[str, Any] | None) -> list[RouteCandidate]:
        requested_model = None
        if payload and isinstance(payload.get("model"), str):
            requested_model = payload["model"].strip() or None

        candidates: list[RouteCandidate] = []

        for provider in self._providers.values():
            if not provider.supports_endpoint(endpoint, requested_model):
                continue

            selected_model = requested_model or provider.default_model_for_endpoint(endpoint)
            limits = provider.limits_for_model(selected_model)

            key_pool: list[str | None] = provider.api_keys or [None]
            for key_slot, key in enumerate(key_pool):
                candidates.append(
                    RouteCandidate(
                        provider=provider,
                        api_key=key,
                        key_slot=key_slot,
                        model=selected_model,
                        model_limits=limits,
                    )
                )

        return candidates
