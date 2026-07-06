from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Azure OpenAI ---
    openai_api_key: str
    azure_endpoint: str = ""
    azure_chat_deployment: str = "gpt-realtime-mini"
    embed_model: str = "text-embedding-3-small"

    # Realtime/WebSocket settings used by the chatbot
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = "gpt-realtime-mini"
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

    @property
    def base_url(self) -> str:
        if self.azure_endpoint:
            return self.azure_endpoint
        return "https://api.openai.com/v1"

    @property
    def chat_model(self) -> str:
        return self.azure_chat_deployment
    
settings = Settings()    