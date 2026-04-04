"""Cartesia Sonic 3 TTS using the official Cartesia Python SDK.

The SDK handles WebSocket lifecycle, context management, and audio format
automatically — no manual JSON, no connection bugs.
"""

from __future__ import annotations
import logging
from typing import AsyncIterator, Callable, Awaitable
from cartesia import AsyncCartesia
from app.config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_VOICE_ID = "a0e99841-438c-4a64-b679-ae501e7d6091"

VOICE_MAP = {
    "Polly.Matthew-Neural": "a0e99841-438c-4a64-b679-ae501e7d6091",
    "Polly.Joanna-Neural": "eda5bbff-1ff1-4886-8ef1-4e69a77640a0",
    "Polly.Amy-Neural": "79a125e8-cd45-4c13-8a67-188112f4dd22",
}

OUTPUT_FORMAT = {
    "container": "raw",
    "encoding": "pcm_mulaw",
    "sample_rate": 8000,
}

_client: AsyncCartesia | None = None


def _get_client() -> AsyncCartesia:
    global _client
    if _client is None:
        _client = AsyncCartesia(api_key=get_settings().cartesia_api_key)
    return _client


class TTSContext:
    """Persistent TTS WebSocket connection for an entire call.

    Uses Cartesia SDK's websocket_connect for managed connection lifecycle.
    Each conversation turn gets a new context (maintains prosody within a turn).

    Usage:
        tts = TTSContext(voice_id, on_audio=send_to_twilio)
        await tts.connect()
        await tts.speak("Hello!")              # one-shot
        await tts.stream_sentences(gen)        # stream from GPT
        await tts.cancel()                     # barge-in
        await tts.close()
    """

    def __init__(
        self,
        voice_id: str | None = None,
        on_audio: Callable[[bytes], Awaitable[None]] | None = None,
    ):
        self._voice = voice_id or DEFAULT_VOICE_ID
        self._on_audio = on_audio
        self._conn = None
        self._conn_mgr = None

    async def connect(self) -> None:
        client = _get_client()
        self._conn_mgr = client.tts.websocket_connect()
        self._conn = await self._conn_mgr.__aenter__()

    async def speak(self, text: str) -> None:
        """Speak a complete text (one-shot, e.g. greeting)."""
        if not self._conn or not text.strip():
            return

        ctx = self._conn.context(
            model_id="sonic-3",
            voice={"mode": "id", "id": self._voice},
            output_format=OUTPUT_FORMAT,
        )
        await ctx.push(text)
        await ctx.no_more_inputs()

        async for resp in ctx.receive():
            if hasattr(resp, "audio") and resp.audio and self._on_audio:
                await self._on_audio(resp.audio)

    async def stream_sentences(self, sentence_gen) -> str:
        """Stream sentences from an async generator to TTS.

        Each sentence is pushed with continue=True, final with continue=False.
        Audio chunks are forwarded via on_audio callback as they arrive.

        Args:
            sentence_gen: async generator yielding (sentence: str, is_last: bool)

        Returns:
            Full concatenated text of all sentences spoken.
        """
        if not self._conn:
            return ""

        ctx = self._conn.context(
            model_id="sonic-3",
            voice={"mode": "id", "id": self._voice},
            output_format=OUTPUT_FORMAT,
        )

        full_text = ""
        import asyncio

        async def send_sentences():
            nonlocal full_text
            async for sentence, is_last in sentence_gen:
                if sentence.strip():
                    full_text += sentence
                    logger.info("→ TTS: '%s'", sentence.strip()[:60])
                    await ctx.push(sentence)
                if is_last:
                    break
            await ctx.no_more_inputs()

        async def receive_audio():
            async for resp in ctx.receive():
                if hasattr(resp, "audio") and resp.audio and self._on_audio:
                    await self._on_audio(resp.audio)

        # Run send and receive concurrently
        await asyncio.gather(send_sentences(), receive_audio())
        return full_text

    async def cancel(self) -> None:
        """Cancel current generation (for barge-in). Next speak/stream uses new context."""
        # SDK handles cancellation via new context — old context is abandoned
        pass

    async def close(self) -> None:
        if self._conn_mgr:
            try:
                await self._conn_mgr.__aexit__(None, None, None)
            except Exception:
                pass


# ── Sentence extraction for streaming ──────────────────────────────

SENTENCE_ENDS = {".", "!", "?", ";"}


def extract_sentences(buffer: str) -> tuple[list[str], str]:
    """Split buffer into complete sentences and remaining text."""
    sentences = []
    current = ""
    for char in buffer:
        current += char
        if char in SENTENCE_ENDS and len(current.strip()) > 5:
            sentences.append(current.strip())
            current = ""
    return sentences, current


# ── Simple one-shot TTS (backward compat) ──────────────────────────

async def tts_stream(text: str, voice_id: str | None = None) -> AsyncIterator[bytes]:
    """One-shot TTS using SDK. Yields audio chunks."""
    client = _get_client()
    voice = voice_id or DEFAULT_VOICE_ID

    async with client.tts.websocket_connect() as conn:
        ctx = conn.context(
            model_id="sonic-3",
            voice={"mode": "id", "id": voice},
            output_format=OUTPUT_FORMAT,
        )
        await ctx.push(text)
        await ctx.no_more_inputs()

        async for resp in ctx.receive():
            if hasattr(resp, "audio") and resp.audio:
                yield resp.audio
