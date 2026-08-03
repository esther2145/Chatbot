# Free deployment guide

This repository deploys as three managed pieces:

1. Qdrant Cloud stores the NSSF vectors.
2. Render hosts the FastAPI backend and React frontend.
3. LiveKit Cloud hosts the voice agent.

Secrets stay in provider dashboards or ignored `.env` files. Never commit them.

## 1. Push the deployment configuration

From the repository root:

```powershell
git status
git add .
git commit -m "Prepare Nicky for cloud deployment"
git push origin main
```

Confirm on GitHub that `.env` is not present in the repository.

## 2. Create the Qdrant database

1. Sign in at https://cloud.qdrant.io/.
2. Create a free cluster in Frankfurt.
3. Open the cluster and create an API key.
4. Copy the HTTPS cluster URL and API key.
5. In the local root `.env`, set:

```env
QDRANT_URL=https://your-cluster-url
QDRANT_API_KEY=your-qdrant-api-key
COLLECTION=nssf
```

Create a temporary ingestion environment and upload the NSSF data:

```powershell
python -m venv ingestion-venv
.\ingestion-venv\Scripts\python.exe -m pip install -r .\ingestion\requirements.txt
.\ingestion-venv\Scripts\python.exe -m playwright install chromium
.\ingestion-venv\Scripts\python.exe .\ingestion\ingest.py
```

In Qdrant Cloud, confirm that the `nssf` collection now contains points.

## 3. Deploy the backend and frontend on Render

1. Sign in at https://dashboard.render.com/ with GitHub.
2. Select **New > Blueprint**.
3. Connect `esther2145/Chatbot`.
4. Select the `main` branch and `render.yaml`.
5. Render will show two services: `nicky-nssf-api` and
   `nicky-nssf-chatbot`.
6. Enter every requested secret using the corresponding value from the local
   `.env`. Do not copy the placeholder values from `.env.example`.

Use these deployment-specific values:

```env
QDRANT_URL=https://your-cluster-url
QDRANT_API_KEY=your-qdrant-api-key
CORS_ORIGINS=https://nicky-nssf-chatbot.onrender.com
VITE_API_BASE_URL=https://nicky-nssf-api.onrender.com
```

If Render changes either service name because it is already taken, use the
actual URLs Render assigns and update `CORS_ORIGINS` and
`VITE_API_BASE_URL`, then manually redeploy both services.

Wait for both deployments to become **Live**, then test:

```text
https://nicky-nssf-api.onrender.com/health
https://nicky-nssf-chatbot.onrender.com
```

The health endpoint must return `{"status":"ok"}`. The first request after
15 minutes of inactivity can take about a minute on Render's free plan.

## 4. Deploy the voice agent on LiveKit Cloud

Install and authenticate the CLI:

```powershell
winget install LiveKit.LiveKitCLI
lk cloud auth
```

If browser authentication does not work, add the project manually with
`lk project add` using the project URL, API key, and API secret.

Create `voice-agent/.env.deploy` with only these values:

```env
RAG_API_URL=https://nicky-nssf-api.onrender.com/api/ask
AZURE_OPENAI_ENDPOINT=your-existing-azure-endpoint
AZURE_OPENAI_API_KEY=your-existing-azure-key
AZURE_OPENAI_DEPLOYMENT=your-existing-realtime-deployment
LIVEKIT_AGENT_VOICE=coral
LIVEKIT_AGENT_VOICE_SPEED=1.05
```

This file is ignored by Git. Deploy from the repository root:

```powershell
lk agent create --region ap-south --secrets-file .\voice-agent\.env.deploy .\voice-agent
```

When prompted, confirm the deployment. Check its state and logs:

```powershell
cd voice-agent
lk agent status
lk agent logs
```

After this succeeds, do not run `run-voice-agent.ps1` or the Docker
`voice-agent` service. LiveKit Cloud owns the worker.

## 5. Final test

1. Open the Render frontend URL in a private browser window.
2. Send a text question and confirm an answer and citation appear.
3. Select **Live voice**, allow microphone access, and complete a short call.
4. End the call and confirm the transcript appears in chat history.
5. In LiveKit Cloud, open **Agents > Sessions/Insights** and confirm the call,
   transcript, logs, and audio are present.

## Updating later

Backend and frontend updates deploy automatically after a push to `main`:

```powershell
git push origin main
```

Deploy voice-agent updates separately:

```powershell
lk agent deploy .\voice-agent
```
