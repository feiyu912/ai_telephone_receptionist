"""Voice preview endpoint — lets clients preview TTS voices."""

from __future__ import annotations
import logging
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.client import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["preview"])


@router.get("/preview")
async def voice_preview(
    voice_id: str = "Polly.Joanna-Neural",
    db: AsyncSession = Depends(get_db),
):
    """Return TwiML that plays a voice preview sample."""
    # Look up voice config from DB
    result = await db.execute(
        text("SELECT polly_voice, display_name FROM voice_config WHERE voice_id = :vid"),
        {"vid": voice_id},
    )
    row = result.mappings().first()

    if row:
        polly_voice = row["polly_voice"]
        display_name = row["display_name"]
    else:
        polly_voice = voice_id
        display_name = voice_id

    twiml = (
        f'<Response>'
        f'<Say voice="{polly_voice}">'
        f'Hi! I am {display_name}. This is a preview of my voice. How do I sound?'
        f'</Say></Response>'
    )
    return Response(content=twiml, media_type="text/xml")
