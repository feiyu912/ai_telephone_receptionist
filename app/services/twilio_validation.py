"""Twilio webhook signature validation.

Twilio signs every webhook with HMAC-SHA1(url + sorted(form-params)) using
TWILIO_AUTH_TOKEN, sent as the `X-Twilio-Signature` header. Without this
check, anyone who knows the endpoint URL can POST fake form data and
trigger calls, SMS, HubSpot writes, analytics poisoning, etc.

This is applied as a FastAPI dependency on every Twilio-facing route.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, Request, status
from twilio.request_validator import RequestValidator

from app.config import get_settings

logger = logging.getLogger(__name__)


def _canonical_url(request: Request) -> str:
    """Rebuild the URL Twilio would have signed.

    Behind nginx we see `http://api:8000/voice/incoming-call`, but Twilio
    signed `https://api.your-domain.com/voice/incoming-call`. Use the
    configured base_url to get the public URL Twilio actually hit, and
    preserve the request's query string.
    """
    settings = get_settings()
    base = settings.base_url.rstrip("/")
    path = request.url.path
    query = request.url.query
    return f"{base}{path}?{query}" if query else f"{base}{path}"


async def verify_twilio_signature(request: Request) -> None:
    """FastAPI dependency: reject requests without a valid Twilio signature.

    Falls open (logs a warning, allows the request) when TWILIO_AUTH_TOKEN
    is not configured — useful for local dev, never leave the token unset
    in production.
    """
    settings = get_settings()
    auth_token = settings.twilio_auth_token
    if not auth_token:
        logger.warning(
            "TWILIO_AUTH_TOKEN not set — skipping signature validation on %s",
            request.url.path,
        )
        return

    signature = request.headers.get("X-Twilio-Signature", "")
    if not signature:
        logger.warning("Missing X-Twilio-Signature on %s", request.url.path)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing Twilio signature",
        )

    # Cached on the Request object by Starlette; routes can still call
    # request.form() after us without re-parsing.
    form = await request.form()
    params = {k: str(v) for k, v in form.items()}

    validator = RequestValidator(auth_token)
    if not validator.validate(_canonical_url(request), params, signature):
        logger.warning(
            "Invalid Twilio signature on %s (from %s)",
            request.url.path,
            request.client.host if request.client else "unknown",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Twilio signature",
        )
