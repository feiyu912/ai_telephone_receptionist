"""Voicemail transcription via OpenAI Whisper.

Downloads recorded audio from Twilio and transcribes it to text.
"""

from __future__ import annotations
import io
import logging
import httpx
from openai import AsyncOpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)


async def download_recording(recording_url: str, account_sid: str | None = None, auth_token: str | None = None) -> bytes:
    """Download a Twilio recording as MP3.

    Twilio recording URLs look like:
    https://api.twilio.com/2010-04-01/Accounts/.../Recordings/RE...
    They require HTTP Basic Auth.
    """
    # Ensure we fetch the MP3 variant
    url = recording_url if recording_url.endswith(".mp3") else f"{recording_url}.mp3"

    auth = None
    if account_sid and auth_token:
        auth = (account_sid, auth_token)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, auth=auth, follow_redirects=True)
        resp.raise_for_status()
        return resp.content


async def transcribe_audio(audio_bytes: bytes) -> str:
    """Transcribe audio bytes using OpenAI Whisper."""
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    resp = await client.audio.transcriptions.create(
        model="whisper-1",
        file=("voicemail.mp3", io.BytesIO(audio_bytes)),
    )
    return resp.text or ""


async def transcribe_recording(recording_url: str, account_sid: str | None = None, auth_token: str | None = None) -> str:
    """Download a Twilio recording and transcribe it."""
    audio = await download_recording(recording_url, account_sid, auth_token)
    return await transcribe_audio(audio)
