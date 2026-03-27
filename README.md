# Free LLM Gate

FreeLLM Gate is a FastAPI API gateway for OpenAI-compatible free LLM providers.

It loads providers from `config.yaml`, chooses the best upstream using quota-aware scoring, and proxies requests through one unified API surface.

## Implemented Architecture

- OpenAI-compatible proxy endpoints (`/v1/...`)
- Provider registry loaded from your YAML config
- L7 routing/load balancing across providers and key slots
- Quota/rate-limit tracking (in-memory)
- Optional gateway auth middleware (`GATEWAY_API_KEY`)
- `/utils/transform_request` endpoint for route/debug preview

Routing score:

```text
score = tokens_left - recent_requests * penalty
```

`penalty` is configurable via `ROUTING_RECENT_REQUEST_PENALTY`.

## Supported Endpoints

- `POST /v1/chat/completions`
- `POST /v1/completions`
- `GET /v1/models`
- `POST /v1/embeddings`
- `POST /v1/responses`
- `POST /v1/images/generations`
- `POST /v1/images/edits`
- `POST /v1/audio/transcriptions`
- `POST /v1/audio/speech`
- `POST /v1/batches`
- `POST /v1/messages`
- `GET|POST /v1/realtime/openai`
- `POST /v1/model/load`
- `POST /v1/model/unload`
- `POST /v1/model/download`
- `GET /v1/model/download-status`
- `POST /utils/transform_request`
- `POST /invocations` (SageMaker-style shim)
- `GET /healthz`

## Configuration

### 1. Environment (`.env`)

Required for real provider calls:

- `GEMINI_API_KEY`
- `GROQ_API_KEY`
- `OPENROUTER_API_KEY`
- ...other provider keys as needed

Optional gateway settings:

- `GATEWAY_API_KEY` (if set, requests must include bearer/x-api-key)
- `PROVIDERS_CONFIG_PATH` (default: `config.yaml`)
- `REQUEST_TIMEOUT_SECONDS` (default: `90`)
- `ROUTING_RECENT_REQUEST_PENALTY` (default: `200`)

### 2. Provider YAML (`config.yaml`)

The gateway reads your current list-of-dicts provider format (same shape as your existing file).

If `config.yaml` is missing, it falls back to `config-example.yaml`.

## Run

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Server defaults: `0.0.0.0:8000`.

### Docker Run

```bash
docker run --rm \
  -p 8000:8000 \
  --env-file .env \
  -v "$(pwd)/config.yaml:/app/config.yaml:ro" \
  <your-dockerhub-image>:latest
```

This is enough to run the gateway: provide `config.yaml` plus your API keys in `.env`.

## Notes

- For providers with OpenAI-compatible base URLs, requests are forwarded mostly as-is.
- If a request does not specify `model`, the gateway injects a provider default model for that endpoint family.
- Quota counters are in-memory and reset on process restart.
