from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import SecretStr

from config import Settings
from app.services.runtime_types import ModelLimits, ProviderRuntime


_PROVIDER_NAMES = (
    "gemini",
    "groq",
    "cerebras",
    "openrouter",
    "mistral",
    "huggingface",
    "nvidia_nim",
    "cohere",
    "ollama",
)


def _secret_to_str(value: SecretStr | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, SecretStr):
        extracted = value.get_secret_value().strip()
        return extracted or None
    extracted = str(value).strip()
    return extracted or None


def _merge_provider_entries(raw_provider: Any) -> dict[str, Any]:
    if isinstance(raw_provider, dict):
        return dict(raw_provider)

    merged: dict[str, Any] = {}
    if not isinstance(raw_provider, list):
        return merged

    for entry in raw_provider:
        if not isinstance(entry, dict):
            continue
        for key, value in entry.items():
            existing = merged.get(key)
            if isinstance(existing, list) and isinstance(value, list):
                merged[key] = [*existing, *value]
            elif isinstance(existing, dict) and isinstance(value, dict):
                copied = dict(existing)
                copied.update(value)
                merged[key] = copied
            else:
                merged[key] = value
    return merged


def _merge_mapping_list(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    merged: dict[str, Any] = {}
    if not isinstance(raw, list):
        return merged
    for item in raw:
        if not isinstance(item, dict):
            continue
        merged.update(item)
    return merged


def _parse_string_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        stripped = raw.strip()
        return [stripped] if stripped else []
    if isinstance(raw, list):
        result: list[str] = []
        for item in raw:
            if isinstance(item, str):
                stripped = item.strip()
                if stripped:
                    result.append(stripped)
        return result
    return []


def _parse_model_collection(raw: Any) -> tuple[list[str], dict[str, ModelLimits]]:
    model_names: list[str] = []
    limits: dict[str, ModelLimits] = {}

    if raw is None:
        return model_names, limits

    if isinstance(raw, str):
        stripped = raw.strip()
        if stripped:
            model_names.append(stripped)
        return model_names, limits

    iterable: list[Any]
    if isinstance(raw, dict):
        iterable = [{k: v} for k, v in raw.items()]
    elif isinstance(raw, list):
        iterable = raw
    else:
        return model_names, limits

    for item in iterable:
        if isinstance(item, str):
            stripped = item.strip()
            if stripped:
                model_names.append(stripped)
            continue

        if not isinstance(item, dict):
            continue

        for model_name, raw_cfg in item.items():
            if not isinstance(model_name, str):
                continue
            name = model_name.strip()
            if not name:
                continue
            model_names.append(name)

            cfg = _merge_mapping_list(raw_cfg)
            if cfg:
                limits[name] = ModelLimits.from_mapping(cfg)

    return model_names, limits


def _extract_provider_api_keys(provider_cfg: dict[str, Any], settings: Settings, name: str) -> list[str]:
    api_keys = _parse_string_list(
        provider_cfg.get("apiKeys")
        or provider_cfg.get("api_keys")
        or provider_cfg.get("tokens")
        or provider_cfg.get("token")
    )

    settings_field = f"{name}_api_key"
    if hasattr(settings, settings_field):
        env_key = _secret_to_str(getattr(settings, settings_field))
        if env_key:
            api_keys.insert(0, env_key)

    deduped: list[str] = []
    seen: set[str] = set()
    for key in api_keys:
        if key in seen:
            continue
        seen.add(key)
        deduped.append(key)
    return deduped


def _provider_base_url(provider_cfg: dict[str, Any], settings: Settings, name: str) -> str:
    from_cfg = provider_cfg.get("base_url") or provider_cfg.get("base-url")
    if isinstance(from_cfg, str) and from_cfg.strip():
        return from_cfg.strip()

    field_name = f"{name}_base_url"
    if hasattr(settings, field_name):
        value = getattr(settings, field_name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _provider_token_type(provider_cfg: dict[str, Any]) -> str:
    raw = provider_cfg.get("token_type") or provider_cfg.get("token-type") or "Bearer"
    return str(raw).strip() or "Bearer"


def load_provider_runtimes(settings: Settings) -> dict[str, ProviderRuntime]:
    config_path = Path(settings.providers_config_path)
    if not config_path.exists():
        fallback = Path("config-example.yaml")
        if fallback.exists():
            config_path = fallback
        else:
            return {}

    try:
        raw_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return {}
    if not isinstance(raw_config, dict):
        return {}

    providers: dict[str, ProviderRuntime] = {}

    for provider_name in _PROVIDER_NAMES:
        provider_raw = raw_config.get(provider_name)
        merged = _merge_provider_entries(provider_raw)

        base_url = _provider_base_url(merged, settings, provider_name)
        if not base_url:
            continue

        generic_models, generic_limits = _parse_model_collection(merged.get("models"))
        text_models, text_limits = _parse_model_collection(merged.get("text-models"))
        tool_models, tool_limits = _parse_model_collection(merged.get("tool-models"))
        vision_models, vision_limits = _parse_model_collection(merged.get("vision-models"))
        embedding_models, embedding_limits = _parse_model_collection(merged.get("embedding-models"))
        stt_models, stt_limits = _parse_model_collection(merged.get("stt-models"))
        tts_models, tts_limits = _parse_model_collection(merged.get("tts-models"))

        model_limits: dict[str, ModelLimits] = {}
        for source in (
            generic_limits,
            text_limits,
            tool_limits,
            vision_limits,
            embedding_limits,
            stt_limits,
            tts_limits,
        ):
            model_limits.update(source)

        providers[provider_name] = ProviderRuntime(
            name=provider_name,
            base_url=base_url,
            token_type=_provider_token_type(merged),
            api_keys=_extract_provider_api_keys(merged, settings, provider_name),
            generic_models=generic_models,
            text_models=text_models,
            tool_models=tool_models,
            vision_models=vision_models,
            embedding_models=embedding_models,
            stt_models=stt_models,
            tts_models=tts_models,
            model_limits=model_limits,
        )

    return providers
