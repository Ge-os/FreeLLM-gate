from __future__ import annotations

from app.core.app_factory import create_app
from config import settings

app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=(settings.environment == "dev"),
    )
