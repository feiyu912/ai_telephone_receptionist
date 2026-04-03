"""Cartesia Sonic 3 TTS via WebSocket for real-time voice synthesis.

Supports:
1. tts_stream() — one-shot: send complete text, receive audio chunks
2. TTSContext — streaming continuation: pipe sentences as GPT generates them
"""

from __future__ import annotations
import asyncio
import base64
import json
import logging
import uuid
from typing import AsyncIterator, Callable, Awaitable
import websockets
from app.config import get_settings

logger = logging.getLogger(__name__)

CARTESIA_TTS_WS = "wss://api.cartesia.ai/tts/websocket"

DEFAULT_VOICE_ID = "a0e99841-438c-4a64-b679-ae501e7d6091"

VOICE_MAP = {
    "Polly.Matthew-Neural": "a0e99841-438c-4a64-b679-ae501e7d6091",
    "Polly.Joanna-Neural": "eda5bbff-1ff1-4886-8ef1-4e69a77640a0",
    "Polly.Amy-Neural": "79a125e8-cd45-4c13-8a67-188112f4dd22",
}

_OUTPUT_FORMAT = {
    "container": "raw",
    "encoding": "pcm_mulaw",
    "sample_rate": 8000,
}


class TTSContext:
    """Persistent TTS WebSocket for streaming sentence-by-sentence.

    Keeps one WebSocket open for the entire call. Each conversation turn
    uses a new context_id. Sentences within a turn use continue=True.

    Usage:
        tts = TTSContext(voice_id, on_audio=send_to_twilio)
        await tts.connect()

        # For each GPT sentence as it streams:
        await tts.send_sentence("Hello there.", more_coming=True)
        await tts.send_sentence("How can I help?", more_coming=False)

        # New conversation turn:
        tts.new_turn()
        await tts.send_sentence("Sure, let me look that up.", more_coming=False)

        await tts.close()
    """

    def __init__(
        self,
        voice_id: str | None = None,
        on_audio: Callable[[bytes], Awaitable[None]] | None = None,
    ):
        self._voice = voice_id or DEFAULT_VOICE_ID
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._context_id = str(uuid.uuid4())
        self._on_audio = on_audio
        self._recv_task: asyncio.Task | None = None
        self._connected = False

    async def connect(self) -> None:
        settings = get_settings()
        uri = (
            f"{CARTESIA_TTS_WS}"
            f"?api_key={settings.cartesia_api_key}"
            f"&cartesia_version=2025-04-16"
        )
        self._ws = await websockets.connect(uri)
        self._connected = True
        # Start background receiver that pipes audio to callback
        self._recv_task = asyncio.create_task(self._receive_loop())

    async def _receive_loop(self) -> None:
        """Background task: receive audio chunks and forward via callback."""
        try:
            async for msg in self._ws:
                data = json.loads(msg)
                msg_type = data.get("type", "")

                if msg_type == "chunk":
                    audio_b64 = data.get("data", "")
                    if audio_b64 and self._on_audio:
                        await self._on_audio(base64.b64decode(audio_b64))
                elif msg_type == "error":
                    logger.error("TTS error: %s", data.get("error"))
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception:
            logger.exception("TTS receive loop error")
        finally:
            self._connected = False

    async def send_sentence(self, text: str, more_coming: bool = False) -> None:
        """Send a sentence to TTS. Audio arrives via on_audio callback.

        Args:
            text: The sentence to speak.
            more_coming: True if more sentences follow in this turn.
        """
        if not self._ws or not self._connected or not text.strip():
            return

        request = {
            "model_id": "sonic-3",
            "transcript": text,
            "voice": {"mode": "id", "id": self._voice},
            "output_format": _OUTPUT_FORMAT,
            "language": "en",
            "context_id": self._context_id,
            "continue": more_coming,
        }
        await self._ws.send(json.dumps(request))

    async def cancel(self) -> None:
        """Cancel current TTS generation (for barge-in)."""
        if not self._ws or not self._connected:
            return
        cancel_msg = {
            "context_id": self._context_id,
            "cancel": True,
        }
        try:
            await self._ws.send(json.dumps(cancel_msg))
        except Exception:
            pass
        # Start fresh context for next response
        self._context_id = str(uuid.uuid4())

    def new_turn(self):
        """Start a new context for a new conversation turn."""
        self._context_id = str(uuid.uuid4())

    async def close(self) -> None:
        self._connected = False
        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass


# ── Sentence buffer for streaming GPT → TTS ───────────────────────

SENTENCE_ENDS = {".","!","?",";",":","—","–"}


def extract_sentences(buffer: str) -> tuple[list[str], str]:
    """Split buffer into complete sentences and remaining text.

    Returns (sentences, remainder).
    """
    sentences = []
    current = ""
    for char in buffer:
        current += char
        if char in SENTENCE_ENDS and len(current.strip()) > 5:
            sentences.append(current.strip())
            current = ""
    return sentences, current


# ── Simple one-shot TTS (used for greeting) ────────────────────────

async def tts_stream(text: str, voice_id: str | None = None) -> AsyncIterator[bytes]:
    """One-shot TTS: send full text, yield audio chunks."""
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
            request = {
                "model_id": "sonic-3",
                "transcript": text,
                "voice": {"mode": "id", "id": voice},
                "output_format": _OUTPUT_FORMAT,
                "language": "en",
                "context_id": context_id,
                "continue": False,
            }
            await ws.send(json.dumps(request))

            async for msg in ws:
                data = json.loads(msg)
                msg_type = data.get("type", "")

                if msg_type == "chunk":
                    audio_b64 = data.get("data", "")
                    if audio_b64:
                        yield base64.b64decode(audio_b64)
                    if data.get("done", False):
                        break
                elif msg_type == "done":
                    break
                elif msg_type == "error":
                    logger.error("Cartesia TTS error: %s", data.get("error"))
                    break
    except Exception:
        logger.exception("Cartesia TTS WebSocket error")
        raise
