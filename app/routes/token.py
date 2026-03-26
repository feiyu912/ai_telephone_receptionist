"""Twilio Access Token endpoint for browser-based test dialer."""

from __future__ import annotations
import uuid
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from app.config import get_settings

router = APIRouter(tags=["token"])


@router.get("/voice/twilio-token")
@router.post("/voice/twilio-token")
async def twilio_token():
    """Generate a Twilio Access Token for the browser Voice SDK.

    The browser SDK uses this token to connect to Twilio,
    then Twilio calls our /voice/incoming-call webhook.
    """
    settings = get_settings()

    token = AccessToken(
        settings.twilio_account_sid,
        settings.twilio_api_key_sid,
        settings.twilio_api_key_secret,
        identity=f"test-dialer-{uuid.uuid4().hex[:8]}",
    )

    voice_grant = VoiceGrant(
        outgoing_application_sid=settings.twilio_twiml_app_sid,
        incoming_allow=True,
    )
    token.add_grant(voice_grant)

    return JSONResponse({
        "token": token.to_jwt(),
    })
