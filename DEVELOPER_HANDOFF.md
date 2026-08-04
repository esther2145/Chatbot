# Nicky Chatbot: Developer Handoff and Reproduction Guide

This guide lets another developer run the Nicky NSSF chatbot locally and
reproduce the deployed system. Run commands from the repository root unless a
step says otherwise.

## What the system uses

- React/Vite frontend
- FastAPI backend
- Qdrant vector database
- Azure OpenAI embeddings and Realtime models
- LiveKit Cloud voice agent
- Optional Supabase Postgres conversation history
- Render backend and frontend hosting

The repository contains code and safe configuration templates. It does not
contain API keys, passwords, or other secrets.

## Required software

Install:

- Git
- Python 3.11 (not Python 3.14)
- Node.js 20 or newer
- Docker Desktop
- LiveKit CLI for voice development/deployment

On Windows, verify the tools:

```powershell
git --version
py -3.11 --version
node --version
npm --version
docker --version
lk --version
```

Install the LiveKit CLI if required:

```powershell
winget install LiveKit.LiveKitCLI
```

## 1. Clone and configure the repository

```powershell
git clone https://github.com/esther2145/Chatbot.git
cd Chatbot
Copy-Item .env.example .env
```

Edit the root `.env`. Obtain real values from the project owner through a
password manager or another secure channel. Never send them in source control,
chat screenshots, or frontend `VITE_` variables.

Minimum working configuration:

```env
# Azure Realtime model used by text generation and live voice
AZURE_OPENAI_ENDPOINT=https://your-resource.cognitiveservices.azure.com
AZURE_OPENAI_API_KEY=your-secret-key
AZURE_OPENAI_DEPLOYMENT=your-realtime-deployment
AZURE_OPENAI_API_VERSION=2025-04-01-preview

# Azure embedding deployment used by ingestion and Qdrant search
AZURE_EMBED_ENDPOINT=https://your-resource.cognitiveservices.azure.com
AZURE_EMBED_API_KEY=your-secret-key
AZURE_EMBED_DEPLOYMENT=text-embedding-3-small
AZURE_EMBED_API_VERSION=2024-12-01-preview

# Local defaults; replace with Qdrant Cloud values for cloud deployment
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
COLLECTION=nssf

# Local browser/backend configuration
CORS_ORIGINS=http://localhost:5173
VITE_API_BASE_URL=http://127.0.0.1:8001

# LiveKit Cloud project
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your-livekit-api-key
LIVEKIT_API_SECRET=your-livekit-api-secret

# Optional Supabase Postgres history storage
DATABASE_URL=
```

`AZURE_CHAT_*`, `LANGFUSE_*`, and `OPENAI_API_KEY` are optional for the current
configuration.

## 2. Start the local text chatbot

Start Qdrant and the backend:

```powershell
docker compose up --build -d qdrant backend
docker compose ps
```

Verify the API:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
Invoke-RestMethod http://127.0.0.1:8001/api/status
```

Expected health response:

```json
{"status":"ok"}
```

Install and start the frontend in a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## 3. Load the NSSF knowledge into local Qdrant

Create the ingestion environment once:

```powershell
py -3.11 -m venv ingestion-venv
.\ingestion-venv\Scripts\python.exe -m pip install --upgrade pip
.\ingestion-venv\Scripts\python.exe -m pip install -r .\ingestion\requirements.txt
.\ingestion-venv\Scripts\python.exe -m playwright install chromium
```

Force this run to target the local Qdrant container, even if `.env` contains
cloud Qdrant values:

```powershell
$env:QDRANT_URL="http://127.0.0.1:6333"
$env:QDRANT_API_KEY=""
.\ingestion-venv\Scripts\python.exe .\ingestion\ingest.py
Remove-Item Env:QDRANT_URL
Remove-Item Env:QDRANT_API_KEY
```

Successful ingestion ends with output similar to:

```text
Done. Upserted 48 chunks into 'nssf'.
```

Inspect local Qdrant at `http://localhost:6333/dashboard`, then open the
`nssf` collection.

## 4. Run live voice locally

Create the voice-agent environment:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r .\voice-agent\requirements.txt
```

Start it in a third terminal:

```powershell
.\run-voice-agent.ps1
```

Keep that terminal open, open the frontend, select **Live voice**, and allow
microphone access. Do not start a second agent copy; only one process can use
the local health port `8081`.

Stop local services when finished:

```powershell
docker compose down
```

## 5. Optional persistent history with Supabase

Without `DATABASE_URL`, history uses backend memory and browser local storage.
It can be lost when the backend restarts.

To enable persistence:

1. Create a Supabase project.
2. In its dashboard, select **Connect**.
3. Copy the shared **Session pooler** connection string on port `5432`.
4. Replace `[YOUR-PASSWORD]` with the database password. Percent-encode special
   password characters when necessary.
5. Set the complete value as `DATABASE_URL` in `.env` and Render.

The backend automatically creates these tables on first use:

- `conversations`
- `messages`
- `feedback`

Confirm persistence with:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/api/status
```

Expected when connected:

```json
{"ready":true,"persistent_history":true}
```

## 6. Reproduce the cloud deployment

### Qdrant Cloud

1. Create or open a Qdrant Cloud cluster.
2. Create an API key.
3. Put its HTTPS URL and key in the local `.env`:

```env
QDRANT_URL=https://your-cluster.cloud.qdrant.io
QDRANT_API_KEY=your-secret-key
COLLECTION=nssf
```

Run ingestion without the temporary local overrides from section 3. Confirm
that the cloud `nssf` collection contains points.

### Render

1. Push the repository to GitHub.
2. In Render, select **New > Blueprint**.
3. Connect the repository, `main` branch, and `render.yaml`.
4. Enter every `sync: false` secret from the secure `.env` copy.
5. Deploy `nicky-nssf-api` and `nicky-nssf-chatbot`.

Use the real assigned URLs if Render changes the service names:

```env
CORS_ORIGINS=https://your-frontend.onrender.com
VITE_API_BASE_URL=https://your-backend.onrender.com
```

Test:

```powershell
Invoke-RestMethod https://your-backend.onrender.com/health
Invoke-RestMethod https://your-backend.onrender.com/api/status
```

The frontend URL must show **Service online**. A free Render service can take
about a minute to wake after inactivity.

### LiveKit Cloud agent

Register the existing LiveKit project through browser authentication:

```powershell
lk cloud auth
```

Alternatively, register it directly:

```powershell
lk project add nicky --url $env:LIVEKIT_URL --api-key $env:LIVEKIT_API_KEY --api-secret $env:LIVEKIT_API_SECRET --default
```

`voice-agent/livekit.toml` identifies the existing production agent. Deploy an
update from the voice-agent directory:

```powershell
cd voice-agent
lk agent deploy --yes .
lk agent status
```

For a completely new LiveKit project, remove the old agent ID from your local
copy of `voice-agent/livekit.toml` and create a new deployment with the required
secrets:

Create an ignored `voice-agent/.env.deploy` file:

```env
RAG_API_URL=https://your-backend.onrender.com/api/ask
AZURE_OPENAI_ENDPOINT=https://your-resource.cognitiveservices.azure.com
AZURE_OPENAI_API_KEY=your-secret-key
AZURE_OPENAI_DEPLOYMENT=your-realtime-deployment
LIVEKIT_AGENT_VOICE=coral
LIVEKIT_AGENT_VOICE_SPEED=1.0
```

```powershell
lk agent create --region ap-south --secrets-file .env.deploy --yes .
```

Never commit `.env.deploy`.

## 7. Final acceptance test

Complete all of these checks:

1. `/health` returns `{"status":"ok"}`.
2. `/api/status` returns `{"ready":true,...}`.
3. Ask a text question and receive an answer with official citations.
4. Ask a follow-up question and confirm it understands the same conversation.
5. Start live voice and confirm English transcription appears.
6. Ask a voice follow-up question and confirm context is retained.
7. End the call and confirm its transcript is added to chat history.
8. Start a new chat and confirm it does not continue the previous conversation.
9. Confirm the history title reflects the first user question.
10. If Supabase is configured, restart the backend and confirm history remains.

## 8. Common problems

### Python package version errors

Use Python 3.11 and recreate the affected virtual environment:

```powershell
py -3.11 -m venv ingestion-venv
```

Do not add `python==...` to a pip requirements file; pip does not install the
Python interpreter.

### Port 8081 is already in use

Another local LiveKit agent is running. Do not start a duplicate. Identify it:

```powershell
Get-NetTCPConnection -LocalPort 8081 -State Listen
```

### Frontend stays on Connecting or reports unexpected JSON

Confirm the frontend build variable contains the full backend URL, including
`https://`, then redeploy the static frontend:

```env
VITE_API_BASE_URL=https://your-backend.onrender.com
```

### Voice agent diagnosis

Start a test call while streaming deployment logs:

```powershell
cd voice-agent
lk agent logs
```

### Qdrant returns no useful answers

Confirm that `QDRANT_URL`, `QDRANT_API_KEY`, and `COLLECTION=nssf` refer to the
same cluster used during ingestion, and confirm that the collection contains
points.

## Updating the system

Backend and frontend updates deploy after pushing `main`:

```powershell
git add .
git commit -m "Describe the change"
git push origin main
```

Voice-agent code must also be deployed separately:

```powershell
cd voice-agent
lk agent deploy --yes .
```
