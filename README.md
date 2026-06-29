# NSSF Assistant (Nicky) — Backend

A retrieval-augmented chatbot that answers NSSF Uganda questions from the
official website content. FastAPI backend + Qdrant vector database + OpenAI,
with conversation memory, source citations, streaming answers, and optional
Langfuse monitoring.

## What's inside

    nssf-chatbot/
    ├── docker-compose.yml        # runs Qdrant + the backend together
    ├── .env.example              # copy to .env and add your OpenAI key
    ├── backend/                  # the chat API (serving layer)
    │   └── app/
    │       ├── main.py           # endpoints: /chat, /chat/history, /feedback
    │       ├── rag.py            # retrieval + answer generation
    │       ├── memory.py         # per-session conversation history
    │       ├── monitoring.py     # optional Langfuse tracing
    │       ├── config.py
    │       └── schemas.py
    ├── ingestion/                # the data pipeline (run separately)
    │   └── ingest.py             # scrape -> chunk -> embed -> load to Qdrant
    └── frontend-snippet/
        └── useChat.ts            # React hook for your existing UI

## How the two halves fit together

1. **Ingestion (data pipeline)** — `ingestion/ingest.py` reads NSSF pages,
   splits them, creates embeddings, and stores them in Qdrant. Run it whenever
   the NSSF site changes. It is a batch job, not part of the live chat.
2. **Chat (serving layer)** — the backend takes a question, finds matching
   content in Qdrant, and asks OpenAI to answer using only that content.

## Running it

### 1. Set your key
    cp .env.example .env
    # edit .env and paste your OpenAI key

### 2. Start Qdrant + the backend
    docker compose up --build
The API is now at http://localhost:8000 (try http://localhost:8000/health).

### 3. Load the NSSF content (one time, and whenever the site changes)
Run the ingestion pipeline against the running Qdrant:

    cd ingestion
    pip install -r requirements.txt
    OPENAI_API_KEY=sk-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
CHAT_MODEL=gpt-4o-mini QDRANT_URL=http://localhost:6333 python ingest.py

Edit `SEED_URLS` in `ingest.py` to point at the exact NSSF pages you want.

### 4. Connect your frontend
Copy `frontend-snippet/useChat.ts` into your React app and use it:

    const { messages, askedQuestions, isStreaming, send } = useChat();
    // render messages, show askedQuestions in the sidebar,
    // call send(question) on Send.

## Key features built in

- **Conversation memory** — each session keeps recent turns, so follow-up
  questions are understood in context.
- **Interruption-safe** — a new question aborts the previous in-flight answer
  (frontend), and the backend only saves completed turns, so context never
  gets confused.
- **Source citations** — answers come back with the NSSF page URLs they used.
- **"I don't know" handling** — if nothing relevant is found, the bot says so
  and points to NSSF instead of inventing an answer.
- **Streaming** — answers appear word-by-word.
- **Feedback** — POST /feedback with up/down logs to Langfuse.
- **Monitoring** — optional Langfuse tracing of every request.

## Endpoints

| Method | Path                       | Purpose                          |
|--------|----------------------------|----------------------------------|
| POST   | /chat                      | Ask a question (streams SSE)     |
| GET    | /chat/history/{session_id} | The questions asked in a session |
| POST   | /feedback                  | Thumbs up/down on an answer      |
| GET    | /health                    | Health check                     |

## Ideas to take it further

- **Scheduled re-scraping**: run the ingestion container on a weekly cron.
- **Hybrid search**: combine keyword + vector search in Qdrant to nail exact
  figures (contribution rates, dates).
- **Caching**: cache answers to common questions to cut cost and latency.
- **Evaluation set**: a fixed list of test questions + expected answers, run
  automatically to catch quality regressions.
- **Move sessions to Redis** when you run more than one backend replica.
