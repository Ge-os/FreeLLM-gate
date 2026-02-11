from pathlib import Path
from typing import Any

import yaml
from app.schemas.config import ModelCapabilities, ProviderConfig, Config


def _flatten_provider(raw: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge list-of-dicts from YAML into a single dict."""
    out: dict[str, Any] = {}
    for d in raw:
        if isinstance(d, dict):
            out.update(d)
    return out


def _parse_model_item(item: Any) -> tuple[str, ModelCapabilities | None]:
    """Extract model name and capabilities from YAML model entry."""
    if isinstance(item, str):
        return item, None
    if isinstance(item, dict):
        for name, caps in item.items():
            if isinstance(caps, list):
                merged: dict[str, Any] = {}
                for c in caps:
                    if isinstance(c, dict):
                        merged.update(c)
                return name, ModelCapabilities.model_validate(merged) if merged else None
            return name, None
    return "", None


def _parse_models(raw: list[Any]) -> dict[str, ModelCapabilities | None]:
    """Parse models list into {model_name: capabilities}."""
    result: dict[str, ModelCapabilities | None] = {}
    for item in raw:
        name, caps = _parse_model_item(item)
        if name:
            if name not in result or caps is not None:
                result[name] = caps
    return result


def _parse_provider(raw: list[dict[str, Any]]) -> ProviderConfig:
    """Build ProviderConfig from provider's list-of-dicts structure."""
    flat = _flatten_provider(raw)
    api_keys = flat.get("apiKeys") or []

    models: dict[str, ModelCapabilities | None] = {}
    if "models" in flat and isinstance(flat["models"], list):
        models = _parse_models(flat["models"])

    embedding: dict[str, ModelCapabilities | None] | list[str] = []
    if "embedding-models" in flat and isinstance(flat["embedding-models"], list):
        parsed = _parse_models(flat["embedding-models"])
        embedding = parsed if parsed else []

    return ProviderConfig.model_validate(
        {
            "apiKeys": api_keys,
            "models": models,
            "text-models": flat.get("text-models") or [],
            "tool-models": flat.get("tool-models") or [],
            "vision-models": flat.get("vision-models") or [],
            "embedding-models": embedding,
            "stt-models": flat.get("stt-models") or [],
            "tts-models": flat.get("tts-models") or [],
        }
    )


_config: Config | None = None


def load_config(path: str | Path = "config.yaml") -> Config:
    """Load and parse config.yaml into Config."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {p}")

    with p.open() as f:
        data = yaml.safe_load(f) or {}

    for key in ("gemini", "groq", "cerebras", "openrouter"):
        if key in data and isinstance(data[key], list):
            data[key] = _parse_provider(data[key])

    return Config.model_validate(data)


def get_config(path: str | Path = "config.yaml") -> Config:
    """Return singleton config instance, loading on first call."""
    global _config
    if _config is None:
        _config = load_config(path)
    return _config
