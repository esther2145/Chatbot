"""
Retrieval-augmented generation against the NSSF content, using Google Gemini
through its OpenAI-compatible endpoint. Streams tokens as they are produced.
"""
from openai import OpenAI
from qdrant_client import QdrantClient

from .config import settings

# Same OpenAI SDK, just pointed at Gemini's compatible endpoint.
_client = OpenAI(api_key=settings.gemini_api_key, base_url=settings.base_url)
_qdrant = QdrantClient(url=settings.qdrant_url)

SYSTEM_PROMPT = (
    "You are Nicky, the NSSF Uganda assistant. You help people with questions "
    "about membership, benefits, contributions, claims and NSSF services.\n\n"
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
    resp = _client.embeddings.create(model=settings.embed_model, input=text)
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


def stream_answer(history: list[dict], query: str):
    context = retrieve(query)

    if not context:
        yield {"type": "token", "content": NO_ANSWER}
        yield {"type": "done", "citations": []}
        return

    messages = _build_messages(history, query, context)
    stream = _client.chat.completions.create(
        model=settings.chat_model,
        messages=messages,
        stream=True,
        temperature=0.2,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield {"type": "token", "content": delta}

    citations, seen = [], set()
    for c in context:
        url = c.payload.get("url")
        if url and url not in seen:
            seen.add(url)
            citations.append(url)
    yield {"type": "done", "citations": citations}