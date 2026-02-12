from enum import Enum


class TokenType(Enum):
    BEARER = "Bearer"
    BASIC = "Basic"
    OAUTH2 = "OAuth2"
    API_KEY = "API Key"
    API_SECRET = "API Secret"
    API_TOKEN = "API Token"
    API_KEY_ID = "API Key ID"
    API_KEY_SECRET = "API Key Secret"
