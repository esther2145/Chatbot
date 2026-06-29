from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Google Gemini (free tier) via its OpenAI-compatible endpoint ---
    gemini_api_key: str
    base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    chat_model: str = "gemini-2.5-flash"
    embed_model: str = "gemini-embedding-001"

    qdrant_url: str = "http://qdrant:6333"
    collection: str = "nssf"

    # Below this similarity we say "I don't have that information" rather than guess.
    score_threshold: float = 0.2
    top_k: int = 5

    # How many past turns to keep per session (conversation memory).
    max_turns: int = 8
    session_ttl_seconds: int = 3600

    # Optional monitoring. Leave blank to disable.
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"


settings = Settings()