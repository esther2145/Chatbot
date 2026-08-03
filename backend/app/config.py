from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Azure OpenAI ---
    # Optional fallback for the standard OpenAI API. Azure deployments use
    # AZURE_OPENAI_API_KEY instead, so this must not prevent app startup.
    openai_api_key: str = ""
    azure_endpoint: str = ""
    azure_chat_deployment: str = "gpt-realtime-mini"
    azure_chat_endpoint: str = ""
    azure_chat_api_key: str = ""
    azure_chat_api_version: str = "2024-12-01-preview"
    embed_model: str = "text-embedding-3-small"

    # Realtime/WebSocket settings used by the chatbot
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = "gpt-realtime-mini"
    # Optional separate embedding endpoint/deployment (useful if embeddings
    # are deployed to a different Azure resource than chat/realtime)
    azure_embed_endpoint: str = ""
    azure_embed_api_key: str = ""
    azure_embed_deployment: str = ""
    azure_embed_api_version: str = "2024-12-01-preview"
    azure_openai_api_version: str = "2025-04-01-preview"

    # Qdrant and retrieval settings
    qdrant_url: str = "http://qdrant:6333"
    collection: str = "nssf"
    score_threshold: float = 0.2
    top_k: int = 5

    # Session memory
    max_turns: int = 8
    session_ttl_seconds: int = 3600

    # Optional monitoring
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # LiveKit Cloud. The API secret is server-only and must never be exposed
    # through a VITE_ variable or returned directly to the browser.
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""

    @property
    def base_url(self) -> str:
        if self.azure_endpoint:
            return self.azure_endpoint
        return "https://api.openai.com/v1"

    @property
    def chat_model(self) -> str:
        return self.azure_chat_deployment
    
settings = Settings()
