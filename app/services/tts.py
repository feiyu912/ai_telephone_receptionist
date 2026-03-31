"""Cartesia Sonic 3 TTS via WebSocket for real-time voice synthesis.

Uses the Cartesia WebSocket API at wss://api.cartesia.ai/tts/websocket
with pcm_mulaw encoding at 8kHz for Twilio Media Streams.
"""

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

# Default Cartesia voice ID
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
) -> AsyncIterator[bytes]:
    """Stream TTS audio chunks from Cartesia Sonic 3 via WebSocket.

    Yields raw audio bytes (pcm_mulaw 8kHz for Twilio Media Streams).
    """
    settings = get_settings()
    voice = voice_id or DEFAULT_VOICE_ID
    context_id = str(uuid.uuid4())

    uri = (
        f"{CARTESIA_TTS_WS}"
        f"?api_key={settings.cartesia_api_key}"
        f"&cartesia_version=2025-04-16"
    )

    try:
        async with websockets.connect(uri) as ws:
            # Send TTS request per Cartesia API spec
            request = {
                "model_id": "sonic-3",
                "transcript": text,
                "voice": {
                    "mode": "id",
                    "id": voice,
                },
                "output_format": {
                    "container": "raw",
                    "encoding": "pcm_mulaw",
                    "sample_rate": 8000,
                },
                "language": "en",
                "context_id": context_id,
                "continue": False,
            }
            await ws.send(json.dumps(request))

            # Receive audio chunks
            async for msg in ws:
                data = json.loads(msg)
                msg_type = data.get("type", "")

                if msg_type == "chunk":
                    audio_b64 = data.get("data", "")
                    if audio_b64:
                        yield base64.b64decode(audio_b64)
                    # Check if this chunk is the last one
                    if data.get("done", False):
                        break

                elif msg_type == "done":
                    break

                elif msg_type == "error":
                    logger.error("Cartesia TTS error: %s", data.get("error", "unknown"))
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
