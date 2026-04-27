"""Server-side authentication routes for the dashboard."""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.config import get_settings
from app.services.auth import (
    SESSION_COOKIE,
    AuthUser,
    authenticate_user,
    create_session_token,
    get_current_user,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


# ── Login rate limiting ───────────────────────────────────────────
# Per-IP sliding window over FAILED login attempts. Successful logins
# clear the IP's counter. In-process only — resets on container restart
# and not shared across uvicorn workers. Good enough as defense in
# depth on top of bcrypt; promote to Redis if we scale to >1 worker.

_LOGIN_WINDOW_SEC = 5 * 60
_LOGIN_MAX_FAILED = 10
_failed_logins: dict[str, deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    # nginx sets X-Forwarded-For; take the leftmost (original client)
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(ip: str) -> None:
    now = time.monotonic()
    bucket = _failed_logins[ip]
    # Drop stamps older than the window
    while bucket and now - bucket[0] > _LOGIN_WINDOW_SEC:
        bucket.popleft()
    if len(bucket) >= _LOGIN_MAX_FAILED:
        retry_in = int(_LOGIN_WINDOW_SEC - (now - bucket[0]))
        logger.warning("Login rate-limited for %s (retry in %ds)", ip, retry_in)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Try again later.",
            headers={"Retry-After": str(retry_in)},
        )


def _record_failure(ip: str) -> None:
    _failed_logins[ip].append(time.monotonic())


def _clear_failures(ip: str) -> None:
    _failed_logins.pop(ip, None)


class LoginRequest(BaseModel):
    email: str
    password: str


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=7 * 24 * 60 * 60,
        path="/",
    )


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response):
    ip = _client_ip(request)
    _check_rate_limit(ip)

    user = await authenticate_user(body.email, body.password)
    if not user:
        _record_failure(ip)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    _clear_failures(ip)
    token = create_session_token(user)
    _set_session_cookie(response, token)
    return user.model_dump()


@router.get("/session")
async def session(user: AuthUser = Depends(get_current_user)):
    return user.model_dump()


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key=SESSION_COOKIE, path="/")
    return {"status": "logged_out"}
