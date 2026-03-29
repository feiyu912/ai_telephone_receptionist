"""Twilio SMS service for sending follow-up messages and notifications."""

from __future__ import annotations
import logging
from twilio.rest import Client
from app.config import get_settings

logger = logging.getLogger(__name__)

_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        settings = get_settings()
        _client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    return _client


async def send_sms(to: str, from_: str, body: str) -> str | None:
    """Send an SMS via Twilio. Returns message SID or None on failure."""
    try:
        client = _get_client()
        message = client.messages.create(to=to, from_=from_, body=body)
        logger.info("SMS sent to %s: sid=%s", to, message.sid)
        return message.sid
    except Exception:
        logger.exception("Failed to send SMS to %s", to)
        return None


async def send_booking_confirmation(
    to: str, from_: str, caller_name: str,
    date: str, time: str, company_name: str,
) -> str | None:
    """Send a booking confirmation SMS."""
    body = (
        f"Hi {caller_name}, your appointment with {company_name} "
        f"is confirmed for {date} at {time}. "
        f"Reply STOP to opt out of messages."
    )
    return await send_sms(to, from_, body)


async def send_call_summary(
    to: str, from_: str, summary: str, company_name: str,
) -> str | None:
    """Send a post-call summary SMS."""
    body = (
        f"Thanks for calling {company_name}! "
        f"Here's a summary: {summary[:300]}\n\n"
        f"Reply STOP to opt out."
    )
    return await send_sms(to, from_, body)
