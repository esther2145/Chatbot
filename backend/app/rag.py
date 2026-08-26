"""Retrieval-augmented generation against the indexed NSSF content."""
import json

from openai import AzureOpenAI, OpenAI
from qdrant_client import QdrantClient  # type: ignore[import]
from websockets.sync.client import connect

from .config import settings

def _client(api_key: str, endpoint: str, api_version: str):
    """Build a client with the correct URL format for Azure or OpenAI."""
    if endpoint:
        return AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version,
        )
    return OpenAI(api_key=api_key or settings.openai_api_key)


# Embeddings may live in a separate Azure resource. If not configured, use the
# main Azure resource, but the model name must still be an actual deployment.
embed_client = _client(
    settings.azure_embed_api_key
    or settings.azure_openai_api_key
    or settings.openai_api_key,
    settings.azure_embed_endpoint
    or settings.azure_openai_endpoint
    or settings.azure_endpoint,
    settings.azure_embed_api_version,
)
_qdrant = QdrantClient(
    url=settings.qdrant_url,
    api_key=settings.qdrant_api_key or None,
)

SYSTEM_PROMPT = """You are Nicky, the official virtual assistant for the National Social Security
Fund (NSSF) of Uganda. You were created to help members, employers, and the
general public understand NSSF services, policies, and processes.

PERSONALITY & TONE:
- You are warm, patient, professional, and approachable.
- Use simple, everyday English. Avoid jargon unless the user uses it first.
- You may use light humour when appropriate, but never about someone's money,
  retirement, or financial concerns.
- Be concise. Prefer short, direct answers.
- Never sound robotic, overly formal, or like you're reading from a manual.

CONVERSATIONAL AWARENESS:
- Greetings: When the user says hello, hi, hey, good morning, etc., respond
  warmly. Example: "Hey there! I'm Nicky, your NSSF Uganda assistant. What
  can I help you with today?"
- If the user has already greeted you earlier, don't re-introduce yourself.
- Identity: If asked who you are, say you are Nicky, NSSF Uganda's virtual
  assistant. If asked who built you, say the NSSF digital team. Do not mention
  Azure, OpenAI, or any underlying model.
- If asked whether you are human or AI, be honest: you are an AI assistant.
- Personal questions: You do NOT have access to any user's personal data.
  If asked "what is my name", "what is my balance", or any account-specific
  question, explain you don't have access and suggest the NSSF Member Portal
  at portal.nssfug.org, the nearest branch, or the toll-free line 0800 100 066.
- Never guess or fabricate personal information.
- Farewells: Respond warmly when the user says goodbye.
- Off-topic: Engage briefly with small talk, then steer back to NSSF.

KNOWLEDGE BOUNDARIES:
- Answer ONLY based on the NSSF Uganda website content provided in the user
  message context.
- If unsure or the answer is not in the content, say so honestly. Never guess.
- When you don't have the answer, suggest:
  1. Visiting www.nssfug.org
  2. Calling 0800 100 066
  3. Visiting the nearest NSSF branch
  4. Emailing customerservice@nssfug.org
- If a question is ambiguous, ask a clarifying question before answering.

SENSITIVE TOPICS:
- Death or disability claims: respond with empathy.
- Complaints: acknowledge feelings, provide helpful next steps.
- Legal or tax advice: clarify you cannot give legal or tax advice.

OUTPUT FORMAT:
- Write in natural, speakable sentences (user may be on text-to-speech).
- Avoid markdown formatting unless necessary.
- Use numbered steps for processes.
- Keep simple answers under 150 words, complex ones under 300.

LANGUAGE:
- Default to English.
- If the user writes in Luganda or another Ugandan language, respond in
  that language if you can do so accurately. Otherwise respond in English."""


def _embed(text: str) -> list[float]:
    model = settings.azure_embed_deployment or settings.embed_model
    resp = embed_client.embeddings.create(model=model, input=text)
    return resp.data[0].embedding


def retrieve(query: str):
    vector = _embed(query)
    hits = _qdrant.search(
        collection_name=settings.collection,
        query_vector=vector,
        limit=settings.top_k,
        with_payload=True,
    )
    return [h for h in hits if h.score >= settings.score_threshold]


def _build_messages(history: list[dict], query: str, context) -> list[dict]:
    context_block = "\n\n".join(
        f"[Source: {c.payload.get('url', 'NSSF website')}]\n{c.payload.get('text', '')}"
        for c in context
    )
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append(
        {
            "role": "user",
            "content": f"Context from the NSSF website:\n{context_block}\n\n"
            f"Question: {query}",
        }
    )
    return messages


def _realtime_text_stream(messages: list[dict]):
    """Generate text with the existing Azure Realtime deployment."""
    endpoint = settings.azure_openai_endpoint or settings.azure_endpoint
    api_key = settings.azure_openai_api_key or settings.openai_api_key
    deployment = settings.azure_openai_deployment or settings.azure_chat_deployment
    api_version = settings.azure_openai_api_version

    if not endpoint or not api_key or not deployment:
        raise RuntimeError("Azure Realtime endpoint, key, or deployment is missing")

    ws_url = (
        f"{endpoint.replace('https://', 'wss://').rstrip('/')}/openai/realtime"
        f"?deployment={deployment}&api-version={api_version}"
    )
    headers = {
        "api-key": api_key,
        "OpenAI-Beta": "realtime=v1",
    }

    # Realtime accepts text conversation items. Add the system instructions,
    # prior turns, retrieved context, and current question to the conversation.
    with connect(ws_url, additional_headers=headers, open_timeout=15) as ws:
        for message in messages:
            content_type = "text" if message["role"] == "assistant" else "input_text"
            ws.send(
                json.dumps(
                    {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "message",
                            "role": message["role"],
                            "content": [
                                {"type": content_type, "text": message["content"]}
                            ],
                        },
                    }
                )
            )

        ws.send(
            json.dumps(
                {
                    "type": "response.create",
                    "response": {"modalities": ["text"], "temperature": 0.6},
                }
            )
        )

        while True:
            event = json.loads(ws.recv(timeout=60))
            event_type = event.get("type")
            if event_type in {"response.text.delta", "response.output_text.delta"}:
                delta = event.get("delta", "")
                if delta:
                    yield delta
            elif event_type in {"response.done", "response.completed"}:
                break
            elif event_type == "error":
                error = event.get("error", {})
                raise RuntimeError(error.get("message", str(error)))


def stream_answer(history: list[dict], query: str):
    context = retrieve(query)
    messages = _build_messages(history, query, context)
    for delta in _realtime_text_stream(messages):
        yield {"type": "token", "content": delta}

    citations, seen = [], set()
    for c in context:
        url = c.payload.get("url")
        if url and url not in seen:
            seen.add(url)
            citations.append(url)
    yield {"type": "done", "citations": citations}
