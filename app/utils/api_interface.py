from socket import timeout
from app.schemas.config import Config
from app.utils.constants import TokenType
import aiohttp
from typing import Any, Dict, List, Optional

from requests import Response


class BaseAPIClient:
    def __init__(self, config: Config) -> None:
        self.base_url = config.gemini.base_url
        self.timeout = aiohttp.ClientTimeout(total=10)
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        self.token_type = config.gemini.token_type
        self.token = config.gemini.token
        self.set_default_headers()
    
    def set_default_headers(self):
        self.headers = {
            "Authorization": f"{self.token_type.value} {self.token}" if self.token else None,
            "Content-Type": "application/json",
            "User-Agent": "FreeLLM-gate/1.0",
            "Accept": "application/json",
        }

    async def _request(
        self, method: str, endpoint: str,
        params: dict = None,
        data: dict = None,
        headers: dict = None,
        files: dict = None,
        verify: bool = True,
        stream: bool = False,
    ) -> Any:
        try:
            async with self.session.request(
                method, self.base_url + endpoint,
                timeout=self.timeout,
                params=params,
                data=data,
                headers=headers or self.headers,
                files=files,
                verify=verify,
                stream=stream,
            ) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            raise aiohttp.ClientError(f"HTTP error: {e}") from e
        except aiohttp.ClientTimeout as e:
            raise aiohttp.ClientTimeout(f"Timeout error: {e}") from e
        except aiohttp.ClientConnectionError as e:
            raise aiohttp.ClientConnectionError(f"Connection error: {e}") from e
        except aiohttp.ClientRequestException as e:
            raise aiohttp.ClientRequestException(f"Request error: {e}") from e
        except aiohttp.ClientPayloadError as e:
            raise aiohttp.ClientPayloadError(f"Payload error: {e}") from e
        except aiohttp.ClientResponseError as e:
            raise aiohttp.ClientResponseError(f"Response error: {e}") from e

    async def get(self, endpoint: str,
    headers: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None) -> Response:
        self.session.headers.update(self.headers) if headers else self.set_default_headers()
        return await self._request("GET", endpoint, params=params)

    async def post(self, endpoint: str,
    data: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    files: Optional[Dict[str, Any]] = None) -> Response:
        return await self._request("POST", endpoint, data=data)
