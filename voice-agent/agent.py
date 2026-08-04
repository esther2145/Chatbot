import os
import uuid

import httpx
from dotenv import load_dotenv
from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession, RunContext, function_tool
from livekit.plugins import openai
from openai.types import realtime as openai_realtime


load_dotenv()

RAG_API_URL = os.getenv("RAG_API_URL", "http://backend:8001/api/ask")


class NssfAssistant(Agent):
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(
            instructions=(
                "You are Nicky, the NSSF Uganda voice assistant. Be friendly, "
                "clear, and concise because your answers are spoken aloud. "
                "Always listen, transcribe, reason, and reply in English. "
                "Never translate the user's words into another language or "
                "switch languages unless the user explicitly asks you to. "
                "Use one consistent neutral English voice and accent for the "
                "entire call. Do not imitate the user's accent. "
                "Every call is a new conversation. Do not claim to remember "
                "or continue any earlier call. Only use information spoken "
                "during the current call. "
                "For every question about NSSF, membership, contributions, "
                "benefits, claims, balances, or services, you must call "
                "search_nssf before answering. Treat its result as the source "
                "of truth. Do not invent NSSF rules, figures, or procedures. "
                "If the knowledge service cannot answer, advise the user to "
                "confirm with NSSF Uganda."
            ),
        )

    @function_tool()
    async def search_nssf(
        self,
        context: RunContext,
        question: str = "",
    ) -> str:
        """Search the chatbot's verified NSSF knowledge base.

        Args:
            question: The user's complete NSSF question.
        """
        del context
        if not question.strip():
            return (
                "I did not receive the question correctly. Ask the user to "
                "repeat it briefly, then call search_nssf again."
            )
        try:
            async with httpx.AsyncClient(timeout=40) as client:
                response = await client.post(
                    RAG_API_URL,
                    json={"question": question, "session_id": self.session_id},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            return f"The NSSF knowledge service is unavailable: {exc}"

        # URLs are useful in text chat but make spoken responses unnecessarily
        # long and choppy. The text chatbot continues to show the citations.
        return payload.get("answer") or "No verified answer was found."


def azure_realtime_model():
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    if endpoint.startswith("https://"):
        endpoint = "wss://" + endpoint.removeprefix("https://")

    return openai.realtime.RealtimeModel.with_azure(
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", ""),
        azure_endpoint=endpoint,
        api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
        voice=os.getenv("LIVEKIT_AGENT_VOICE", "coral"),
        speed=float(os.getenv("LIVEKIT_AGENT_VOICE_SPEED", "1.0")),
        input_audio_transcription=openai_realtime.AudioTranscription(
            model="whisper-1",
            language="en",
            prompt="NSSF Uganda, membership, contributions, balances, benefits, claims",
        ),
        input_audio_noise_reduction="near_field",
    )


is_livekit_cloud = bool(os.getenv("LIVEKIT_AGENT_DEPLOYMENT"))

server = (
    AgentServer()
    if is_livekit_cloud
    else AgentServer(
        # A local Windows workstation can briefly report 100% CPU while the SDK
        # warms up, which causes LiveKit's default CPU-based load policy to reject
        # every call. One warm process is enough for this single-user chatbot.
        load_threshold=0.9,
        num_idle_processes=1,
    )
)


def active_call_load(agent_server: AgentServer) -> float:
    """Allow one active call and report full capacity before a second."""
    return min(len(agent_server.active_jobs) / 1.0, 1.0)


if not is_livekit_cloud:
    server.load_fnc = active_call_load


@server.rtc_session()
async def nssf_voice_agent(ctx: agents.JobContext):
    room_parts = ctx.room.name.split("__")
    session_id = room_parts[1] if len(room_parts) == 3 else str(uuid.uuid4())
    session = AgentSession(llm=azure_realtime_model())
    await session.start(room=ctx.room, agent=NssfAssistant(session_id))
    await session.generate_reply(
        instructions=(
            "Greet the user briefly as Nicky and invite them to ask an NSSF "
            "question. Speak only in English with the same voice and accent "
            "for the complete response."
        )
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
