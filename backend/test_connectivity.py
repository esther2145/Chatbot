import os
import asyncio
import websockets
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Read connection settings from environment
ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")

# Azure OpenAI Realtime uses WebSockets (wss://), not HTTP.
# The portal displays the URL with ?model=, but the API requires ?deployment=.
WS_URL = (
    f"{ENDPOINT.replace('https://', 'wss://')}"
    f"/openai/realtime?deployment={DEPLOYMENT}&api-version={API_VERSION}"
)

# api-key authenticates the request; OpenAI-Beta opts into the realtime protocol.
HEADERS = {
    "api-key": API_KEY,
    "OpenAI-Beta": "realtime=v1",
}


async def test_connection():
    print(f"Connecting to: {WS_URL}")
    try:
        # Open a persistent WebSocket connection to the realtime endpoint
        async with websockets.connect(WS_URL, additional_headers=HEADERS) as ws:
            print("SUCCESS — WebSocket connection established.")

            # On connect, Azure sends a session.created event confirming the session is ready
            response = await asyncio.wait_for(ws.recv(), timeout=10)
            print(f"Server response: {response}")

    except asyncio.TimeoutError:
        # Connection succeeded but no session.created event arrived within 10 seconds
        print("Connected but no message received within timeout.")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(test_connection())
 

'''  env
AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com
AZURE_OPENAI_API_KEY=your-azure-openai-api-key
AZURE_OPENAI_DEPLOYMENT=your-realtime-deployment
AZURE_OPENAI_API_VERSION=2025-04-01-preview
'''
