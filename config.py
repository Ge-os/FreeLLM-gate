from functools import lru_cache
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # app
    app_name: str = "llm-gateway"
    environment: str = "dev"

    # server
    host: str = "0.0.0.0"
    port: int = 8000

    # redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: SecretStr | None = None
    redis_prefix: str = "freellm"

    # gateway
    gateway_api_key: SecretStr | None = None
    providers_config_path: str = "config.yaml"
    request_timeout_seconds: float = 90.0
    routing_recent_request_penalty: float = 200.0

    # CORS
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["*"])
    cors_allow_credentials: bool = True

    # API endpoints
    mistral_base_url: str = "https://api.mistral.ai/v1"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    huggingface_base_url: str = "https://api-inference.huggingface.co/v1"
    nvidia_nim_base_url: str = "https://integrate.api.nvidia.com/v1"
    cohere_base_url: str = "https://api.cohere.com/v2"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    cerebras_base_url: str = "https://api.cerebras.ai/v1"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    ollama_base_url: str = "http://localhost:11434/v1"

    # API keys
    mistral_api_key: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None
    huggingface_api_key: SecretStr | None = None
    nvidia_nim_api_key: SecretStr | None = None
    cohere_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    cerebras_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    ollama_api_key: SecretStr | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password.get_secret_value()}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
