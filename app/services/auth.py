"""Dashboard authentication and signed token helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Any

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import text

from app.config import get_settings
from app.db.client import get_session_factory

logger = logging.getLogger(__name__)

SESSION_COOKIE = "voz_alta_session"
STATE_TTL_SECONDS = 10 * 60
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60


class AuthUser(BaseModel):
    email: str
    role: str
    tenant_id: str
    tenant_name: str


def _urlsafe_b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _urlsafe_b64decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def _auth_secret() -> bytes:
    """Return the HMAC key for signing session / OAuth-state tokens.

    In production (COOKIE_SECURE=true) AUTH_SECRET MUST be set explicitly;
    otherwise tokens would be signed with something else (Twilio token,
    OpenAI key, DB URL) that already appears in error traces and logs —
    leaking any of those would let an attacker forge sessions.
    """
    settings = get_settings()
    if settings.auth_secret:
        return settings.auth_secret.encode("utf-8")

    if settings.cookie_secure:
        raise RuntimeError(
            "AUTH_SECRET must be set when COOKIE_SECURE=true. "
            "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(48))'"
        )

    logger.warning(
        "AUTH_SECRET is not configured; using a dev-only fallback secret. "
        "Set AUTH_SECRET before running with COOKIE_SECURE=true."
    )
    return b"voz-alta-dev-secret-do-not-use-in-prod"


def _sign_payload(payload_b64: str) -> str:
    digest = hmac.new(
        _auth_secret(),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _urlsafe_b64encode(digest)


def _encode_token(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = _urlsafe_b64encode(raw)
    signature = _sign_payload(payload_b64)
    return f"{payload_b64}.{signature}"


def _decode_token(token: str) -> dict[str, Any]:
    try:
        payload_b64, signature = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("Malformed token") from exc

    expected_sig = _sign_payload(payload_b64)
    if not hmac.compare_digest(signature, expected_sig):
        raise ValueError("Invalid signature")

    payload = json.loads(_urlsafe_b64decode(payload_b64).decode("utf-8"))
    exp = int(payload.get("exp", 0))
    if exp < int(time.time()):
        raise ValueError("Token expired")

    return payload


_LOOKUP_USER_SQL = text(
    """
    SELECT email, password_hash, role, tenant_id::text AS tenant_id, tenant_name
    FROM dashboard_users
    WHERE email = :email
    """
)


async def authenticate_user(email: str, password: str) -> AuthUser | None:
    """Look up a dashboard user in Supabase and verify the bcrypt password."""
    normalized = email.strip().lower()
    if not normalized or not password:
        return None

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(_LOOKUP_USER_SQL, {"email": normalized})
        row = result.mappings().first()

    if not row:
        return None

    try:
        ok = bcrypt.checkpw(password.encode("utf-8"), row["password_hash"].encode("utf-8"))
    except ValueError:
        logger.warning("Malformed password_hash for user %s", normalized)
        return None
    if not ok:
        return None

    return AuthUser(
        email=row["email"],
        role=row["role"],
        tenant_id=row["tenant_id"],
        tenant_name=row["tenant_name"],
    )


def create_session_token(user: AuthUser) -> str:
    payload = {
        **user.model_dump(),
        "type": "session",
        "exp": int(time.time()) + SESSION_TTL_SECONDS,
    }
    return _encode_token(payload)


def parse_session_token(token: str) -> AuthUser:
    payload = _decode_token(token)
    if payload.get("type") != "session":
        raise ValueError("Unexpected token type")
    return AuthUser(
        email=payload["email"],
        role=payload["role"],
        tenant_id=payload["tenant_id"],
        tenant_name=payload["tenant_name"],
    )


def build_oauth_state(tenant_id: str, service: str) -> str:
    payload = {
        "type": "oauth_state",
        "tenant_id": tenant_id,
        "service": service,
        "nonce": _urlsafe_b64encode(
            hashlib.sha256(f"{tenant_id}:{service}:{time.time()}".encode("utf-8")).digest()[:12]
        ),
        "exp": int(time.time()) + STATE_TTL_SECONDS,
    }
    return _encode_token(payload)


def parse_oauth_state(state: str, expected_service: str) -> str:
    payload = _decode_token(state)
    if payload.get("type") != "oauth_state":
        raise ValueError("Unexpected state token type")
    if payload.get("service") != expected_service:
        raise ValueError("Unexpected OAuth service")
    return str(payload["tenant_id"])


async def get_current_user(request: Request) -> AuthUser:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    try:
        return parse_session_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


async def require_admin(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


async def require_tenant_access(
    tenant_id: str,
    user: AuthUser = Depends(get_current_user),
) -> AuthUser:
    if user.role == "admin" or user.tenant_id == tenant_id:
        return user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant access denied")
