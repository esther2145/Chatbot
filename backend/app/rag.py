"""Retrieval-augmented generation against the indexed NSSF content."""
import json

from openai import AzureOpenAI, OpenAI
from qdrant_client import QdrantClient
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

SYSTEM_PROMPT = (
    "You are Nicky, the NSSF Uganda assistant. You help people with questions "
    "about membership, benefits, contributions, claims and NSSF services.\n\n"
    "Use simple language that anyone can understand.\n"
    "Start with a direct answer before explaining details.\n"
    "Use bullet points for procedures with multiple steps.\n"
    "Do not say 'Great question'.\n"
    "Keep answers below 150 words unless more detail is requested.\n"
    "Use a professional but warm tone.\n"
    "Rules:\n"
    "1. Answer ONLY using the provided context from the NSSF website.\n"
    "2. If the context does not contain the answer, say you don't have that "
    "information and suggest contacting NSSF Uganda directly. Do NOT guess.\n"
    "3. Never invent figures, rates, dates, or policies.\n"
    "4. Keep answers clear, friendly and concise.\n"
    "5. For anything involving a personal financial decision, remind the user "
    "to confirm with NSSF directly."
)

NO_ANSWER = (
    "I don't have that information in the NSSF material I can access right now. "
    "For an accurate answer, please contact NSSF Uganda directly on their "
    "official channels or visit the nearest branch."
)


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

    if not context:
        yield {"type": "token", "content": NO_ANSWER}
        yield {"type": "done", "citations": []}
        return

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
