from typing import Optional, Literal
from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None  # omit on first message; server returns one


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class HistoryResponse(BaseModel):
    session_id: str
    messages: list[Turn]


class FeedbackRequest(BaseModel):
    session_id: str
    message: str
    rating: Literal["up", "down"]
