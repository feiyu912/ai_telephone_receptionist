"""Dashboard authentication and signed token helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.config import get_settings

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
    settings = get_settings()
    if settings.auth_secret:
        return settings.auth_secret.encode("utf-8")

    derived = (
        settings.twilio_auth_token
        or settings.openai_api_key
        or settings.database_url
        or "voz-alta-dev-secret"
    )
    logger.warning("AUTH_SECRET is not configured; using a derived fallback secret.")
    return derived.encode("utf-8")


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


def _default_users() -> dict[str, dict[str, Any]]:
    return {
        "admin@360dmmc.com": {
            "password": "admin360",
            "user": {
                "email": "admin@360dmmc.com",
                "role": "admin",
                "tenant_id": "11111111-1111-1111-1111-111111111111",
                "tenant_name": "YourCompany",
            },
        },
        "emilio@360dmmc.com": {
            "password": "360group",
            "user": {
                "email": "emilio@360dmmc.com",
                "role": "client",
                "tenant_id": "11111111-1111-1111-1111-111111111111",
                "tenant_name": "YourCompany",
            },
        },
        "support@tenantb.com": {
            "password": "aplus2026",
            "user": {
                "email": "support@tenantb.com",
                "role": "client",
                "tenant_id": "22222222-2222-2222-2222-222222222222",
                "tenant_name": "TenantB",
            },
        },
    }


def get_dashboard_users() -> dict[str, dict[str, Any]]:
    settings = get_settings()
    if not settings.dashboard_users_json:
        logger.warning("DASHBOARD_USERS_JSON is not configured; using fallback dashboard users.")
        return _default_users()

    try:
        raw_users = json.loads(settings.dashboard_users_json)
    except json.JSONDecodeError as exc:
        logger.error("Invalid DASHBOARD_USERS_JSON: %s", exc)
        return _default_users()

    users: dict[str, dict[str, Any]] = {}
    for entry in raw_users:
        email = str(entry.get("email", "")).strip().lower()
        password = str(entry.get("password", ""))
        role = str(entry.get("role", "client"))
        tenant_id = str(entry.get("tenant_id", ""))
        tenant_name = str(entry.get("tenant_name", ""))
        if not email or not password or not tenant_id or role not in {"admin", "client"}:
            continue
        users[email] = {
            "password": password,
            "user": {
                "email": email,
                "role": role,
                "tenant_id": tenant_id,
                "tenant_name": tenant_name,
            },
        }
    return users or _default_users()


def authenticate_user(email: str, password: str) -> AuthUser | None:
    users = get_dashboard_users()
    entry = users.get(email.strip().lower())
    if not entry or not hmac.compare_digest(entry["password"], password):
        return None
    return AuthUser(**entry["user"])


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
