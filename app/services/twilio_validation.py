"""Twilio webhook signature validation.

Twilio signs every webhook with HMAC-SHA1(url + sorted(form-params)) using
the auth token of the account that owns the receiving number. Without
this check, anyone who knows the endpoint URL can POST fake form data.

Per-tenant auth: if the form's `To` (or `WhatsApp: To`) maps to a
tenant with its own `twilio_auth_token`, validate with that token;
otherwise fall back to the global env var. Tenant resolution is just a
DB read — the lookup itself is unauthenticated, but validation *with*
that tenant's token still fails for forged requests, so impersonation
is blocked.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, Request, status
from twilio.request_validator import RequestValidator

from app.config import get_settings
from app.db import queries
from app.db.client import get_session_factory

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


async def _resolve_tenant_auth_token(to_number: str) -> str | None:
    """Load the auth token for the tenant that owns `to_number`, or None."""
    if not to_number:
        return None
    # Twilio sends WhatsApp numbers prefixed `whatsapp:+1...`; strip it.
    phone = to_number.replace("whatsapp:", "")
    try:
        factory = get_session_factory()
        async with factory() as db:
            tenant = await queries.get_tenant_by_phone(db, phone)
            return tenant.twilio_auth_token if tenant else None
    except Exception:
        logger.exception("Failed to resolve tenant auth token for To=%s", phone)
        return None


async def verify_twilio_signature(request: Request) -> None:
    """FastAPI dependency: reject requests without a valid Twilio signature.

    Falls open (logs a warning, allows the request) when no auth token
    is available — intended for local dev, never leave unset in prod.
    """
    settings = get_settings()

    # Cached on the Request object by Starlette; routes can still call
    # request.form() after us without re-parsing.
    form = await request.form()
    params = {k: str(v) for k, v in form.items()}

    tenant_token = await _resolve_tenant_auth_token(params.get("To", ""))
    auth_token = tenant_token or settings.twilio_auth_token

    if not auth_token:
        logger.warning(
            "No Twilio auth token available — skipping signature validation on %s",
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

    validator = RequestValidator(auth_token)
    if not validator.validate(_canonical_url(request), params, signature):
        logger.warning(
            "Invalid Twilio signature on %s (from %s, tenant_token=%s)",
            request.url.path,
            request.client.host if request.client else "unknown",
            "yes" if tenant_token else "fallback",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Twilio signature",
        )
