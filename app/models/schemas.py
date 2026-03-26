"""Pydantic models for request/response validation."""

from __future__ import annotations
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class TenantConfig(BaseModel):
    """Row from account_settings — everything needed to handle a call."""
    phone_number: str
    tenant_id: str
    slug: str | None = None
    company_name: str | None = None
    tier: str = "starter"
    selected_voice: str = "Polly.Matthew-Neural"
    system_prompt: str | None = None
    system_prompt_growth: str | None = None
    greeting_new: str | None = None
    greeting_returning: str | None = None
    after_hours_message: str | None = None
    voicemail_email: str | None = None
    hubspot_booking_link: str | None = None
    business_hours_start: int = 9
    business_hours_end: int = 17
    business_hours_timezone: str = "America/Chicago"
    business_hours_days: list[int] = [1, 2, 3, 4, 5]
    hunt_group_numbers: list[str] = []
    transfer_timeout: int = 20
    booking_enabled: bool = False
    booking_duration_minutes: int = 60
    booking_buffer_minutes: int = 15
    booking_advance_days: int = 30
    google_calendar_id: str = "primary"
    memory_expiry_days: int = 90
    memory_consent_required: bool = True
    pii_verification_required: bool = True
    webhook_base_url: str | None = None
    is_active: bool = True


class CallerMemory(BaseModel):
    memory_key: str
    memory_value: str
    privacy_tier: str = "protected"


class VoiceSession(BaseModel):
    call_sid: str
    caller_phone: str
    called_number: str | None = None
    tenant_id: str
    customer_id: str | None = None
    tier: str = "starter"
    selected_voice: str = "Polly.Matthew-Neural"
    conversation_history: list[dict] = []
    session_metadata: dict = {}
    status: str = "active"


class ConversationTurn(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: str | None = None


class TagAction(BaseModel):
    """Parsed action tags from LLM response."""
    tag: str | None = None  # END_CALL, TRANSFER, BOOK, CONSENT_YES, CONSENT_NO, FORGET_ME
    clean_text: str = ""  # Response text with tags removed


class ExtractedFacts(BaseModel):
    """Facts extracted from a conversation by GPT-4."""
    name: str | None = None
    company: str | None = None
    role: str | None = None
    email: str | None = None
    interest: str | None = None
    last_topic: str | None = None
    callback_requested: bool = False
    sentiment: str | None = None
    intent: str | None = None
    outcome: str | None = None
