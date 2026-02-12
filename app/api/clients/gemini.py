from app.utils.api_interface import BaseAPIClient


class GeminiClient(BaseAPIClient):
    def __init__(self, api_key: str):
        super().__init__("https://api.gemini.com/v1")