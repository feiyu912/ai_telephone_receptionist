"""Server-side authentication routes for the dashboard."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from app.config import get_settings
from app.services.auth import (
    SESSION_COOKIE,
    AuthUser,
    authenticate_user,
    create_session_token,
    get_current_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


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
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
        path="/",
    )


@router.post("/login")
async def login(body: LoginRequest, response: Response):
    user = await authenticate_user(body.email, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

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
