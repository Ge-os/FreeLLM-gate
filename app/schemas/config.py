from pydantic import BaseModel, Field, Any

from app.utils.constants import TokenType


class ModelCapabilities(BaseModel):
    """Model limits/capabilities (from detailed model config in YAML)."""

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
    request_per_month: int | None = None

    model_config = {"extra": "allow"}

    @classmethod
    def model_validate(cls, obj: Any, **kwargs: Any) -> "ModelCapabilities":
        if isinstance(obj, dict):
            obj = {k: None if v in ("None", "null") else v for k, v in obj.items()}
        return super().model_validate(obj, **kwargs)


class ProviderConfig(BaseModel):
    """Merged provider config (apiKeys + models from the list-of-dicts structure)."""

    base_url: str = Field(default="https://api.gemini.com/v1")
    token_type: TokenType = Field(default=TokenType.BEARER)
    token: str = Field(default="")
    api_keys: list[str] = Field(default_factory=list, alias="apiKeys")
    models: dict[str, ModelCapabilities | None] = Field(default_factory=dict)
    text_models: list[str] = Field(default_factory=list, alias="text-models")
    tool_models: list[str] = Field(default_factory=list, alias="tool-models")
    vision_models: list[str] = Field(default_factory=list, alias="vision-models")
    embedding_models: dict[str, ModelCapabilities | None] | list[str] = Field(
        default_factory=dict, alias="embedding-models"
    )
    stt_models: list[str] = Field(default_factory=list, alias="stt-models")
    tts_models: list[str] = Field(default_factory=list, alias="tts-models")

    model_config = {"extra": "allow", "populate_by_name": True}


class Config(BaseModel):
    """Root config from config.yaml."""

    name: str = "LLM Config"
    version: str = "1.0.0"
    schema_: str = Field(default="v1", alias="schema")
    gemini: ProviderConfig | None = None
    groq: ProviderConfig | None = None
    cerebras: ProviderConfig | None = None
    openrouter: ProviderConfig | None = None
    ollama: dict[str, Any] | None = None

    model_config = {"extra": "allow", "populate_by_name": True}