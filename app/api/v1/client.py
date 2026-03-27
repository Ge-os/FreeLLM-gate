from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Query, Request
from fastapi.responses import Response

from app.services.gateway import GatewayService

router = APIRouter(tags=["gateway"])


def get_gateway(request: Request) -> GatewayService:
    return request.app.state.gateway  # type: ignore[attr-defined]


@router.get("/v1/models")
async def list_models(gateway: GatewayService = Depends(get_gateway)) -> dict[str, Any]:
    return gateway.list_models()


@router.post("/v1/chat/completions")
async def chat_completions(request: Request, gateway: GatewayService = Depends(get_gateway)) -> Response:
    return await gateway.proxy(request, "/v1/chat/completions")


@router.post("/v1/completions")
async def completions(request: Request, gateway: GatewayService = Depends(get_gateway)) -> Response:
    return await gateway.proxy(request, "/v1/completions")


@router.post("/v1/embeddings")
async def embeddings(request: Request, gateway: GatewayService = Depends(get_gateway)) -> Response:
    return await gateway.proxy(request, "/v1/embeddings")


@router.post("/v1/responses")
async def responses(request: Request, gateway: GatewayService = Depends(get_gateway)) -> Response:
    return await gateway.proxy(request, "/v1/responses")


@router.post("/v1/images/generations")
async def images_generations(request: Request, gateway: GatewayService = Depends(get_gateway)) -> Response:
    return await gateway.proxy(request, "/v1/images/generations")


@router.post("/v1/images/edits")
async def images_edits(request: Request, gateway: GatewayService = Depends(get_gateway)) -> Response:
    return await gateway.proxy(request, "/v1/images/edits")


@router.post("/v1/audio/transcriptions")
async def audio_transcriptions(request: Request, gateway: GatewayService = Depends(get_gateway)) -> Response:
    return await gateway.proxy(request, "/v1/audio/transcriptions")


@router.post("/v1/audio/speech")
async def audio_speech(request: Request, gateway: GatewayService = Depends(get_gateway)) -> Response:
    return await gateway.proxy(request, "/v1/audio/speech")


@router.post("/v1/batches")
async def batches(request: Request, gateway: GatewayService = Depends(get_gateway)) -> Response:
    return await gateway.proxy(request, "/v1/batches")


@router.post("/v1/messages")
async def messages(request: Request, gateway: GatewayService = Depends(get_gateway)) -> Response:
    return await gateway.proxy(request, "/v1/messages")


@router.api_route("/v1/realtime/openai", methods=["GET", "POST"])
async def realtime_openai(request: Request, gateway: GatewayService = Depends(get_gateway)) -> Response:
    return await gateway.proxy(request, "/v1/realtime/openai")


@router.post("/v1/model/load")
async def model_load(request: Request, gateway: GatewayService = Depends(get_gateway)) -> Response:
    return await gateway.proxy(request, "/v1/model/load")


@router.post("/v1/model/unload")
async def model_unload(request: Request, gateway: GatewayService = Depends(get_gateway)) -> Response:
    return await gateway.proxy(request, "/v1/model/unload")


@router.post("/v1/model/download")
async def model_download(request: Request, gateway: GatewayService = Depends(get_gateway)) -> Response:
    return await gateway.proxy(request, "/v1/model/download")


@router.get("/v1/model/download-status")
async def model_download_status(request: Request, gateway: GatewayService = Depends(get_gateway)) -> Response:
    return await gateway.proxy(request, "/v1/model/download-status")


@router.post("/utils/transform_request")
async def transform_request(
    payload: dict[str, Any] = Body(default_factory=dict),
    endpoint: str = Query(default="/v1/chat/completions"),
    gateway: GatewayService = Depends(get_gateway),
) -> dict[str, Any]:
    return await gateway.transform_request(endpoint=endpoint, payload=payload)


@router.post("/invocations")
async def invocations(
    request: Request,
    payload: dict[str, Any] = Body(default_factory=dict),
    gateway: GatewayService = Depends(get_gateway),
) -> Response:
    return await gateway.invoke_sagemaker_messages(payload=payload, request=request)
