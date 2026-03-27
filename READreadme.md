Краткое описание изменений

- Сделал единый асинхронный API‑клиент `BaseAPIClient` в `app/utils/api_interface.py`, будет использоваться как основа для наследования GeminiClient, MistalClient...
- В `app/utils/constants.py` просьба сохранять константы, например ENUM TokenType
- В конфиг добавил к каждому провайдеру base_url, token_type, token
