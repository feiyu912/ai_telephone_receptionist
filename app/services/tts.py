"""Cartesia Sonic 3 TTS via WebSocket for real-time voice synthesis."""

from __future__ import annotations
import asyncio
import base64
import json
import logging
import uuid
from typing import AsyncIterator
import websockets
from app.config import get_settings

logger = logging.getLogger(__name__)

CARTESIA_TTS_WS = "wss://api.cartesia.ai/tts/websocket"

# Default Cartesia voice ID — can be overridden per tenant
DEFAULT_VOICE_ID = "a0e99841-438c-4a64-b679-ae501e7d6091"

# Voice mapping: Polly voice name -> Cartesia voice ID
VOICE_MAP = {
    "Polly.Matthew-Neural": "a0e99841-438c-4a64-b679-ae501e7d6091",
    "Polly.Joanna-Neural": "eda5bbff-1ff1-4886-8ef1-4e69a77640a0",
    "Polly.Amy-Neural": "79a125e8-cd45-4c13-8a67-188112f4dd22",
}


async def tts_stream(
    text: str,
    voice_id: str | None = None,
    output_format: str = "raw_mulaw_8000",
) -> AsyncIterator[bytes]:
    """Stream TTS audio chunks from Cartesia Sonic 3 via WebSocket.

    Yields raw audio bytes (mulaw 8kHz for Twilio Media Streams).
    """
    settings = get_settings()
    voice = voice_id or DEFAULT_VOICE_ID

    uri = f"{CARTESIA_TTS_WS}?api_key={settings.cartesia_api_key}&cartesia_version=2025-04-16"

    try:
        async with websockets.connect(uri) as ws:
            context_id = str(uuid.uuid4())

            # Send TTS request
            request = {
                "context_id": context_id,
                "model_id": "sonic-3",
                "transcript": text,
                "voice": {"mode": "id", "id": voice},
                "output_format": {
                    "container": "raw",
                    "encoding": "ulaw",
                    "sample_rate": 8000,
                },
                "language": "en",
            }
            await ws.send(json.dumps(request))

            # Receive audio chunks
            async for msg in ws:
                data = json.loads(msg)
                if data.get("type") == "chunk":
                    audio_b64 = data.get("data")
                    if audio_b64:
                        yield base64.b64decode(audio_b64)
                elif data.get("type") == "done":
                    break

    except Exception:
        logger.exception("Cartesia TTS WebSocket error")
        raise


async def tts_full(text: str, voice_id: str | None = None) -> bytes:
    """Get complete TTS audio as a single bytes buffer."""
    chunks = []
    async for chunk in tts_stream(text, voice_id):
        chunks.append(chunk)
    return b"".join(chunks)
