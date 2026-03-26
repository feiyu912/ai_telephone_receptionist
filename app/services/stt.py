"""Cartesia Ink STT via WebSocket for real-time speech transcription."""

from __future__ import annotations
import asyncio
import base64
import json
import logging
import uuid
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
        """
        Args:
            on_transcript: async callback(text, is_final) called for each transcript.
            language: language code for STT.
        """
        self._on_transcript = on_transcript
        self._language = language
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._running = False
        self._recv_task: asyncio.Task | None = None

    async def connect(self) -> None:
        settings = get_settings()
        uri = f"{CARTESIA_STT_WS}?api_key={settings.cartesia_api_key}&cartesia_version=2025-04-16"

        self._ws = await websockets.connect(uri)
        self._running = True

        # Send config
        config = {
            "context_id": str(uuid.uuid4()),
            "model_id": "ink",
            "encoding": "ulaw",
            "sample_rate": 8000,
            "language": self._language,
        }
        await self._ws.send(json.dumps(config))

        # Start receiving transcriptions
        self._recv_task = asyncio.create_task(self._receive_loop())

    async def send_audio(self, audio_bytes: bytes) -> None:
        """Send raw audio chunk to Cartesia STT."""
        if self._ws and self._running:
            payload = {
                "type": "audio",
                "data": base64.b64encode(audio_bytes).decode("ascii"),
            }
            await self._ws.send(json.dumps(payload))

    async def _receive_loop(self) -> None:
        """Listen for transcription results from Cartesia."""
        try:
            async for msg in self._ws:
                data = json.loads(msg)
                msg_type = data.get("type", "")

                if msg_type == "transcript":
                    text = data.get("text", "").strip()
                    is_final = data.get("is_final", False)
                    if text:
                        await self._on_transcript(text, is_final)

                elif msg_type == "error":
                    logger.error("Cartesia STT error: %s", data)

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
                # Send end-of-stream
                await self._ws.send(json.dumps({"type": "end"}))
                await self._ws.close()
            except Exception:
                pass
        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
