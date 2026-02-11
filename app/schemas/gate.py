from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    context: str = Field(default="")
    temperature: float = Field(default=1.0)


class ChatResponse(BaseModel):
    answer: str = Field(default="")
    history: list[ChatRequest] = Field(default_factory=list)
