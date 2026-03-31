"""Cartesia Ink STT via WebSocket for real-time speech transcription.

Uses the Cartesia STT WebSocket API at wss://api.cartesia.ai/stt/websocket.
Audio is sent as raw binary frames (pcm_mulaw 8kHz from Twilio).
Transcripts come back as JSON with is_final flag.
"""

from __future__ import annotations
import asyncio
import json
import logging
from typing import Callable, Awaitable
import websockets
from app.config import get_settings

logger = logging.getLogger(__name__)

CARTESIA_STT_WS = "wss://api.cartesia.ai/stt/websocket"


class STTSession:
    """Manages a persistent STT WebSocket connection for one call.

    Receives raw mulaw 8kHz audio from Twilio and streams transcriptions.
    """

    def __init__(
        self,
        on_transcript: Callable[[str, bool], Awaitable[None]],
        language: str = "en",
    ):
        self._on_transcript = on_transcript
        self._language = language
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._running = False
        self._recv_task: asyncio.Task | None = None

    async def connect(self) -> None:
        settings = get_settings()

        # STT connection uses query params for config
        uri = (
            f"{CARTESIA_STT_WS}"
            f"?api_key={settings.cartesia_api_key}"
            f"&model=ink-whisper"
            f"&language={self._language}"
            f"&encoding=pcm_mulaw"
            f"&sample_rate=8000"
        )

        self._ws = await websockets.connect(uri)
        self._running = True

        # Start receiving transcriptions
        self._recv_task = asyncio.create_task(self._receive_loop())

    async def send_audio(self, audio_bytes: bytes) -> None:
        """Send raw audio bytes to Cartesia STT as binary WebSocket frame."""
        if self._ws and self._running:
            try:
                await self._ws.send(audio_bytes)
            except Exception:
                logger.debug("Failed to send audio to STT")

    async def _receive_loop(self) -> None:
        """Listen for transcription results from Cartesia."""
        try:
            async for msg in self._ws:
                # STT responses are JSON text messages
                if isinstance(msg, bytes):
                    continue

                data = json.loads(msg)
                msg_type = data.get("type", "")

                if msg_type == "transcript":
                    text = data.get("text", "").strip()
                    is_final = data.get("is_final", False)
                    if text:
                        await self._on_transcript(text, is_final)

                elif msg_type == "error":
                    logger.error("Cartesia STT error: %s", data.get("error", "unknown"))

                elif msg_type == "done":
                    logger.info("STT session done")
                    break

        except websockets.exceptions.ConnectionClosed:
            logger.info("STT WebSocket closed")
        except Exception:
            logger.exception("STT receive loop error")
        finally:
            self._running = False

    async def close(self) -> None:
        """Gracefully close the STT session."""
        self._running = False
        if self._ws:
            try:
                # Send "done" text command to close session cleanly
                await self._ws.send("done")
                await self._ws.close()
            except Exception:
                pass
        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
