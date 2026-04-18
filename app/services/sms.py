"""Twilio SMS service for sending follow-up messages and notifications.

Per-tenant credentials are optional — pass `account_sid` and
`auth_token` to send via a specific Twilio (sub)account, otherwise
the global TWILIO_* env vars are used. Clients are cached per
(sid, token) pair so we don't rebuild a TLS connection every call.
"""

from __future__ import annotations
import logging
from twilio.rest import Client
from app.config import get_settings

logger = logging.getLogger(__name__)

_clients: dict[tuple[str, str], Client] = {}


def _get_client(account_sid: str | None, auth_token: str | None) -> Client | None:
    settings = get_settings()
    sid = account_sid or settings.twilio_account_sid
    token = auth_token or settings.twilio_auth_token
    if not sid or not token:
        return None
    key = (sid, token)
    client = _clients.get(key)
    if client is None:
        client = Client(sid, token)
        _clients[key] = client
    return client


async def send_sms(
    to: str,
    from_: str,
    body: str,
    account_sid: str | None = None,
    auth_token: str | None = None,
) -> str | None:
    """Send an SMS via Twilio. Returns message SID or None on failure."""
    client = _get_client(account_sid, auth_token)
    if client is None:
        logger.warning("send_sms skipped: no Twilio credentials configured")
        return None
    try:
        message = client.messages.create(to=to, from_=from_, body=body)
        logger.info("SMS sent to %s: sid=%s", to, message.sid)
        return message.sid
    except Exception:
        logger.exception("Failed to send SMS to %s", to)
        return None


async def send_booking_confirmation(
    to: str, from_: str, caller_name: str,
    date: str, time: str, company_name: str,
    account_sid: str | None = None,
    auth_token: str | None = None,
) -> str | None:
    """Send a booking confirmation SMS."""
    body = (
        f"Hi {caller_name}, your appointment with {company_name} "
        f"is confirmed for {date} at {time}. "
        f"Reply STOP to opt out of messages."
    )
    return await send_sms(to, from_, body, account_sid, auth_token)


async def send_call_summary(
    to: str, from_: str, summary: str, company_name: str,
    account_sid: str | None = None,
    auth_token: str | None = None,
) -> str | None:
    """Send a post-call summary SMS."""
    body = (
        f"Thanks for calling {company_name}! "
        f"Here's a summary: {summary[:300]}\n\n"
        f"Reply STOP to opt out."
    )
    return await send_sms(to, from_, body, account_sid, auth_token)
