from fastapi import APIRouter

gate_router = APIRouter(prefix="/api/v1")


@gate_router.post("/chat", summary="Send request to LLM via gate")
def chat():
    pass
