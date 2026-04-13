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
    twilio_api_key_sid: str = ""
    twilio_api_key_secret: str = ""
    twilio_twiml_app_sid: str = ""

    # --- Cartesia (STT + TTS) ---
    cartesia_api_key: str = ""

    # --- HubSpot ---
    hubspot_access_token: str = ""
    hubspot_client_id: str = ""
    hubspot_client_secret: str = ""

    # --- Microsoft Graph (Outlook Calendar + Email) ---
    ms_tenant_id: str = ""
    ms_client_id: str = ""
    ms_client_secret: str = ""
    ms_calendar_email: str = ""
    ms_sender_email: str = ""  # Mailbox used for sending emails (Mail.Send permission)

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000
    base_url: str = "http://localhost:8000"
    log_level: str = "info"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
