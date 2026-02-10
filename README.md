# Free LLM Gate

FreeLLM-gate is a universal gateway for free Large Language Model (LLM) API providers. It helps you overcome the limitations of individual free LLM APIs (such as rate limits per minute/day and lack of multithreading support) by aggregating multiple providers and tokens behind a single FastAPI-powered interface.

## Features

- **Multi-provider support:** Easily add multiple LLM API providers using a simple YAML configuration.
- **Multi-token support:** Use multiple tokens for a single provider to maximize throughput and avoid rate limits.
- **Automatic load balancing:** Requests are distributed across available providers and tokens.
- **Multithreading:** Enables concurrent generation, even if the underlying providers do not support it.
- **Easy integration:** Exposes a universal API endpoint for your applications.

## Quick Start

1. **Clone the repository:**
	```bash
	git clone https://github.com/yourusername/FreeLLM-gate.git
	cd FreeLLM-gate
	```

2. **Configure providers and tokens:**
	- Edit the `config.yaml` file to add your API keys/tokens for each provider. You can add multiple tokens per provider. Follow providers links *down below* or in [`config-example.yaml`](config-example.yaml) for more details.

3. **Install dependencies:**
	```bash
	pip install -r requirements.txt
	```

4. **Run the FastAPI server:**
	```bash
	uvicorn main:app --reload
	```

5. **Send requests to the gateway:**
	- Use the provided API endpoint to interact with LLMs via your configured providers.

TODO: add POST examples for /generate, /embed and /ping endpoints

## Configuration Example

```yaml
gemini:
  - apiKeys: [..., ..., ...]# <-- Paste your API keys here
  - models:
  # Change model order if needed: fallback is from first to last
  # Delete models you don't need or afraid of quality differ
    - gemini-2.0-flash:
      - input_token_limit: 1048576
      - output_token_limit: 8192

      - default_temperature: 1.0
      - max_temperature: 2.0
      - default_top_p: 0.95
      - default_top_k: 40

      - thinking: False
      - vision: True
      - tools: True

      - requests_per_minute: 5
      - token_per_minute: 250000
      - requests_per_day: 20
      - requests_per_month: None
```

## Get API Keys
- Gemini: https://ai.google.dev/gemini-api/docs/get-started
- Groq: https://www.groq.com/signup
- Cerebras: https://www.cerebras.net/signup
- OpenRouter: https://openrouter.ai/signup
- Cohere:https://cohere.com/ (?)
- NVIDIA NIM: https://build.nvidia.com/explore/discover (?)
- Mistral (La Plateforme | Codestral): https://console.mistral.ai/ (NON-RU NUMBER REQUIRED)
- HF Inference Prov. https://huggingface.co/docs/inference-providers/en/index (?)
- Cloudflare Workers AI https://developers.cloudflare.com/workers-ai/ (?)

### Setup local models for fallback (optional)
- Ollama: https://ollama.com/

## Checking yaml config by your own

1. Gemini 
    - All supported models list:
    ```python
    from google import genai

    client = genai.Client(api_key="API_KEY")

    print("List of models that support generateContent:\n")
    for m in client.models.list():
        for action in m.supported_actions:
            if action == "generateContent":
                print(m.name)

    print("List of models that support embedContent:\n")
    for m in client.models.list():
        for action in m.supported_actions:
            if action == "embedContent":
                print(m.name)
    ```
    - Model info:
    ```python
    print(str(client.models.get(model="models/gemini-embedding-001")))
    ```
    - Rate limits: [aistudio.google.com/usage](https://aistudio.google.com/usage)
    - Models availability for free tier: [ai.google.dev/gemini-api/docs/pricing](https://ai.google.dev/gemini-api/docs/pricing)

