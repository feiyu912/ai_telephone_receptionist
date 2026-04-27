"""Twilio Access Token endpoint for browser-based test dialer.

Tenant-aware: a logged-in user's home tenant determines which Twilio
account (and therefore which API Key + TwiML App) the access token is
minted for, so a YourCompany admin gets a YourCompany token and an Aplus admin
gets an Aplus token. Falls back to the global env vars only when the
tenant row in `account_settings` hasn't been populated yet.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant

from app.config import get_settings
from app.db import queries
from app.db.client import get_db
from app.services.auth import AuthUser, require_admin

router = APIRouter(tags=["token"])


@router.get("/voice/twilio-token")
@router.post("/voice/twilio-token")
async def twilio_token(
    user: AuthUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Mint a Twilio Voice SDK access token for the calling tenant."""
    settings = get_settings()

    tenant = await queries.get_tenant_by_id(db, user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    account_sid    = tenant.twilio_account_sid    or settings.twilio_account_sid
    api_key_sid    = tenant.twilio_api_key_sid    or settings.twilio_api_key_sid
    api_key_secret = tenant.twilio_api_key_secret or settings.twilio_api_key_secret
    twiml_app_sid  = tenant.twilio_twiml_app_sid  or settings.twilio_twiml_app_sid

    if not (account_sid and api_key_sid and api_key_secret and twiml_app_sid):
        raise HTTPException(
            status_code=503,
            detail="Twilio Voice SDK credentials not configured for this tenant",
        )

    token = AccessToken(
        account_sid,
        api_key_sid,
        api_key_secret,
        identity=f"test-dialer-{uuid.uuid4().hex[:8]}",
    )
    token.add_grant(VoiceGrant(
        outgoing_application_sid=twiml_app_sid,
        incoming_allow=True,
    ))

    return JSONResponse({"token": token.to_jwt()})
