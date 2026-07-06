import os
import asyncio
import json
from typing import Any

import websockets

from .config import settings


async def connect_realtime_session() -> dict[str, Any]:
    endpoint = settings.azure_openai_endpoint or settings.azure_endpoint
    api_key = settings.azure_openai_api_key or settings.openai_api_key
    deployment = settings.azure_openai_deployment or settings.azure_chat_deployment
    api_version = settings.azure_openai_api_version

    if not endpoint or not api_key or not deployment:
        raise RuntimeError("Realtime settings are incomplete. Check AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, and AZURE_OPENAI_DEPLOYMENT.")

    ws_url = (
        f"{endpoint.replace('https://', 'wss://').rstrip('/')}/openai/realtime"
        f"?deployment={deployment}&api-version={api_version}"
    )
    headers = {
        "api-key": api_key,
        "OpenAI-Beta": "realtime=v1",
    }

    async with websockets.connect(ws_url, additional_headers=headers) as ws:
        first_message = await asyncio.wait_for(ws.recv(), timeout=10)
        return {
            "status": "connected",
            "url": ws_url,
            "message": first_message,
        }
