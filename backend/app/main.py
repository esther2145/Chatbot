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
import uuid
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import rag
from .config import settings
from .memory import SessionMemory
from .monitoring import trace_chat, trace_feedback
from .schemas import ChatRequest, FeedbackRequest, HistoryResponse

app = FastAPI(title="NSSF Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

memory = SessionMemory(
    max_turns=settings.max_turns,
    ttl_seconds=settings.session_ttl_seconds,
)


class AskRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/status")
def api_status():
    return {"ready": True}


@app.post("/api/ask")
def api_ask(req: AskRequest):
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
    trace_chat(session_id, req.question, full_answer, citations)

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
        trace_chat(session_id, req.message, full_answer, citations)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/chat/history/{session_id}", response_model=HistoryResponse)
def get_history(session_id: str):
    return {"session_id": session_id, "messages": memory.get(session_id)}


@app.post("/feedback")
def feedback(req: FeedbackRequest):
    trace_feedback(req.session_id, req.message, req.rating)
    return {"status": "recorded"}