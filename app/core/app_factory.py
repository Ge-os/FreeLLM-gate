from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.client import router as gateway_router
from app.middleware.auth import GatewayAuthMiddleware
from app.services.gateway import GatewayService
from app.services.provider_registry import ProviderRegistry
from app.services.quota_store import QuotaStore
from config import settings


def create_app() -> FastAPI:
    provider_registry = ProviderRegistry(settings)
    quota_store = QuotaStore()
    gateway_service = GatewayService(
        settings=settings,
        provider_registry=provider_registry,
        quota_store=quota_store,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await gateway_service.startup()
        yield
        await gateway_service.shutdown()

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(
        GatewayAuthMiddleware,
        api_key=(
            settings.gateway_api_key.get_secret_value()
            if settings.gateway_api_key
            else None
        ),
    )

    app.state.gateway = gateway_service

    @app.get("/healthz", tags=["internal"])
    async def healthz(request: Request) -> dict:
        return request.app.state.gateway.health_payload()

    app.include_router(gateway_router)
    return app
