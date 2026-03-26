"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # --- Supabase / PostgreSQL ---
    supabase_url: str = ""
    supabase_anon_key: str = ""
    database_url: str = ""

    # --- OpenAI ---
    openai_api_key: str = ""

    # --- Twilio ---
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""

    # --- Cartesia (STT + TTS) ---
    cartesia_api_key: str = ""

    # --- HubSpot ---
    hubspot_access_token: str = ""

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000
    base_url: str = "http://localhost:8000"
    log_level: str = "info"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
