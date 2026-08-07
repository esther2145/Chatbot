# import json
# import uuid
# from typing import Optional

# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import StreamingResponse
# from pydantic import BaseModel

# from . import rag
# from .config import settings
# from .memory import SessionMemory
# from .monitoring import trace_chat, trace_feedback
# from .schemas import ChatRequest, FeedbackRequest, HistoryResponse

# app = FastAPI(title="NSSF Assistant API")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# memory = SessionMemory(
#     max_turns=settings.max_turns,
#     ttl_seconds=settings.session_ttl_seconds,
# )


# class AskRequest(BaseModel):
#     question: str
#     session_id: Optional[str] = None


# @app.get("/health")
# def health():
#     return {"status": "ok"}


# @app.get("/api/status")
# def api_status():
#     return {"ready": True}


# @app.post("/api/ask")
# def api_ask(req: AskRequest):
#     session_id = req.session_id or str(uuid.uuid4())
#     history = memory.get(session_id)

#     full_answer = ""
#     citations = []
#     for event in rag.stream_answer(history, req.question):
#         if event["type"] == "token":
#             full_answer += event["content"]
#         elif event["type"] == "done":
#             citations = event["citations"]

#     memory.add(session_id, "user", req.question)
#     memory.add(session_id, "assistant", full_answer)
#     trace_chat(session_id, req.question, full_answer, citations)

#     return {
#         "ok": True,
#         "answer": full_answer,
#         "citations": citations,
#         "session_id": session_id,
#     }


# @app.post("/chat")
# def chat(req: ChatRequest):
#     session_id = req.session_id or str(uuid.uuid4())
#     history = memory.get(session_id)

#     def event_stream():
#         full_answer = ""
#         citations = []
#         for event in rag.stream_answer(history, req.message):
#             if event["type"] == "token":
#                 full_answer += event["content"]
#                 yield f"data: {json.dumps({'token': event['content']})}\n\n"
#             elif event["type"] == "done":
#                 citations = event["citations"]
#                 yield (
#                     "data: "
#                     + json.dumps(
#                         {"done": True, "citations": citations, "session_id": session_id}
#                     )
#                     + "\n\n"
#                 )
#         memory.add(session_id, "user", req.message)
#         memory.add(session_id, "assistant", full_answer)
#         trace_chat(session_id, req.message, full_answer, citations)

#     return StreamingResponse(event_stream(), media_type="text/event-stream")


# @app.get("/chat/history/{session_id}", response_model=HistoryResponse)
# def get_history(session_id: str):
#     return {"session_id": session_id, "messages": memory.get(session_id)}


# @app.post("/feedback")
# def feedback(req: FeedbackRequest):
#     trace_feedback(req.session_id, req.message, req.rating)
#     return {"status": "recorded"}

import json
import time
import uuid
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Literal, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from livekit import api as livekit_api
from pydantic import BaseModel

from . import rag
from .config import settings
from .monitoring import (
    monitoring_enabled,
    shutdown_monitoring,
    trace_chat,
    trace_feedback,
)
from .realtime import connect_realtime_session
from .schemas import ChatRequest, FeedbackRequest, HistoryResponse
from .storage import ConversationStore

@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    shutdown_monitoring()


app = FastAPI(title="NSSF Assistant API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

memory = ConversationStore(
    database_url=settings.database_url,
    max_turns=settings.max_turns,
    ttl_seconds=settings.session_ttl_seconds,
)


class AskRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    channel: Literal["text", "voice"] = "text"


class LiveKitTokenRequest(BaseModel):
    session_id: Optional[uuid.UUID] = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/status")
def api_status():
    return {
        "ready": True,
        "persistent_history": memory.persistent,
        "monitoring": monitoring_enabled(),
    }


@app.post("/realtime/session")
async def realtime_session():
    try:
        result = await connect_realtime_session()
        return result
    except Exception as exc:  # pragma: no cover - defensive runtime path
        return JSONResponse(status_code=502, content={"error": str(exc)})


@app.post("/livekit/token")
def livekit_token(req: LiveKitTokenRequest = LiveKitTokenRequest()):
    """Create a short-lived token with an isolated session for every voice call."""
    del req  # Kept in the request schema for backward-compatible clients.
    if not (
        settings.livekit_url
        and settings.livekit_api_key
        and settings.livekit_api_secret
    ):
        return JSONResponse(
            status_code=503,
            content={
                "error": (
                    "LiveKit is not configured. Set LIVEKIT_URL, "
                    "LIVEKIT_API_KEY, and LIVEKIT_API_SECRET."
                )
            },
        )

    # A call must never inherit a text chat or previous call's RAG history.
    # The transcript can still be displayed in the selected UI conversation,
    # but the voice agent always starts with a clean server-side session.
    session_id = str(uuid.uuid4())
    room_name = f"nssf__{session_id}__{uuid.uuid4().hex[:10]}"
    identity = f"web-{uuid.uuid4().hex}"
    token = (
        livekit_api.AccessToken(
            settings.livekit_api_key,
            settings.livekit_api_secret,
        )
        .with_identity(identity)
        .with_name("NSSF member")
        .with_ttl(timedelta(minutes=15))
        .with_grants(
            livekit_api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
            )
        )
        .to_jwt()
    )

    return {
        "serverUrl": settings.livekit_url,
        "participantToken": token,
        "roomName": room_name,
        "sessionId": session_id,
    }


@app.post("/api/ask")
def api_ask(req: AskRequest):
    started_at = time.perf_counter()
    session_id = req.session_id or str(uuid.uuid4())
    history = memory.get(session_id)

    full_answer = ""
    citations = []
    for event in rag.stream_answer(history, req.question):
        if event["type"] == "token":
            full_answer += event["content"]
        elif event["type"] == "done":
            citations = event["citations"]

    memory.add(session_id, "user", req.question)
    memory.add(session_id, "assistant", full_answer)
    trace_chat(
        session_id,
        req.question,
        full_answer,
        citations,
        channel=req.channel,
        latency_ms=round((time.perf_counter() - started_at) * 1000),
    )

    return {
        "ok": True,
        "answer": full_answer,
        "citations": citations,
        "session_id": session_id,
    }


@app.post("/chat")
def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    history = memory.get(session_id)

    def event_stream():
        started_at = time.perf_counter()
        full_answer = ""
        citations = []
        for event in rag.stream_answer(history, req.message):
            if event["type"] == "token":
                full_answer += event["content"]
                yield f"data: {json.dumps({'token': event['content']})}\n\n"
            elif event["type"] == "done":
                citations = event["citations"]
                yield (
                    "data: "
                    + json.dumps(
                        {"done": True, "citations": citations, "session_id": session_id}
                    )
                    + "\n\n"
                )
        memory.add(session_id, "user", req.message)
        memory.add(session_id, "assistant", full_answer)
        trace_chat(
            session_id,
            req.message,
            full_answer,
            citations,
            channel="text",
            latency_ms=round((time.perf_counter() - started_at) * 1000),
        )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/chat/history/{session_id}", response_model=HistoryResponse)
def get_history(session_id: str):
    return {"session_id": session_id, "messages": memory.get(session_id)}


@app.post("/feedback")
def feedback(req: FeedbackRequest):
    memory.add_feedback(req.session_id, req.message, req.rating)
    trace_feedback(req.session_id, req.message, req.rating)
    return {"status": "recorded"}
