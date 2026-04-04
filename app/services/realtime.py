"""OpenAI Realtime API bridge for Twilio Media Streams.

Handles the bidirectional audio pipeline:
  Twilio mulaw audio → OpenAI Realtime → mulaw audio back → Twilio

No separate STT/TTS needed. Built-in voice activity detection (VAD),
function calling, and sub-second latency.
"""

from __future__ import annotations
import asyncio
import json
import logging
from typing import Callable, Awaitable
import websockets
from app.config import get_settings
from app.services.llm import VOICE_TOOLS

logger = logging.getLogger(__name__)

OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime"


class RealtimeSession:
    """Manages an OpenAI Realtime WebSocket session for one call.

    Bridges Twilio Media Stream audio directly to/from OpenAI Realtime.
    """

    def __init__(
        self,
        system_prompt: str,
        on_audio: Callable[[str], Awaitable[None]],  # base64 mulaw audio
        on_transcript: Callable[[str, str], Awaitable[None]] | None = None,  # (role, text)
        on_tool_call: Callable[[str, str, dict], Awaitable[str]] | None = None,  # (call_id, name, args) -> output
        voice: str = "alloy",
        model: str = "gpt-realtime-mini",
    ):
        self._system_prompt = system_prompt
        self._on_audio = on_audio
        self._on_transcript = on_transcript
        self._on_tool_call = on_tool_call
        self._voice = voice
        self._model = model
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._running = False
        self._recv_task: asyncio.Task | None = None

    async def connect(self) -> None:
        """Connect to OpenAI Realtime API and configure the session."""
        settings = get_settings()

        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "OpenAI-Beta": "realtime=v1",
        }

        self._ws = await websockets.connect(
            f"{OPENAI_REALTIME_URL}?model={self._model}",
            additional_headers=headers,
        )
        self._running = True

        # Wait for session.created
        msg = await self._ws.recv()
        data = json.loads(msg)
        if data.get("type") == "session.created":
            logger.info("Realtime session created: %s", data.get("session", {}).get("id", ""))

        # Configure session
        await self._send({
            "type": "session.update",
            "session": {
                "instructions": self._system_prompt,
                "voice": self._voice,
                "input_audio_format": "g711_ulaw",
                "output_audio_format": "g711_ulaw",
                "input_audio_transcription": {
                    "model": "gpt-4o-mini-transcribe",
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500,
                },
                "tools": [t["function"] for t in VOICE_TOOLS],
                "modalities": ["text", "audio"],
            },
        })

        # Start receiving events
        self._recv_task = asyncio.create_task(self._receive_loop())

    async def send_audio(self, audio_b64: str) -> None:
        """Forward base64 mulaw audio from Twilio to OpenAI Realtime."""
        if self._ws and self._running:
            await self._send({
                "type": "input_audio_buffer.append",
                "audio": audio_b64,
            })

    async def send_greeting(self, greeting_text: str) -> None:
        """Make the AI speak a greeting by injecting it as a conversation item."""
        # Add greeting as an assistant message, then create a response
        # to make it speak the greeting
        await self._send({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [{
                    "type": "input_text",
                    "text": f"[System: The call just started. Greet the caller warmly. Say: \"{greeting_text}\"]",
                }],
            },
        })
        await self._send({"type": "response.create"})

    async def _send(self, data: dict) -> None:
        if self._ws and self._running:
            try:
                await self._ws.send(json.dumps(data))
            except Exception:
                logger.debug("Failed to send to Realtime API")

    async def _receive_loop(self) -> None:
        """Process events from OpenAI Realtime."""
        try:
            async for msg in self._ws:
                data = json.loads(msg)
                event_type = data.get("type", "")

                # Audio output → forward to Twilio
                if event_type == "response.audio.delta":
                    audio_b64 = data.get("delta", "")
                    if audio_b64:
                        await self._on_audio(audio_b64)

                # Transcript of what AI said
                elif event_type == "response.audio_transcript.done":
                    transcript = data.get("transcript", "")
                    if transcript and self._on_transcript:
                        await self._on_transcript("assistant", transcript)

                # Transcript of what user said
                elif event_type == "conversation.item.input_audio_transcription.completed":
                    transcript = data.get("transcript", "")
                    if transcript and self._on_transcript:
                        await self._on_transcript("user", transcript)

                # Function call completed
                elif event_type == "response.function_call_arguments.done":
                    call_id = data.get("call_id", "")
                    name = data.get("name", "")
                    args_str = data.get("arguments", "{}")
                    try:
                        args = json.loads(args_str)
                    except json.JSONDecodeError:
                        args = {}

                    logger.info("Tool call: %s(%s)", name, args)

                    # Execute the tool
                    output = ""
                    if self._on_tool_call:
                        output = await self._on_tool_call(call_id, name, args)

                    # Send function output back to Realtime
                    await self._send({
                        "type": "conversation.item.create",
                        "item": {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": output or "Done.",
                        },
                    })
                    # Trigger AI to continue speaking after tool call
                    await self._send({"type": "response.create"})

                # Response done
                elif event_type == "response.done":
                    pass  # Response cycle complete

                # Error
                elif event_type == "error":
                    logger.error("Realtime API error: %s", data.get("error", {}))

                # Speech started (for barge-in tracking)
                elif event_type == "input_audio_buffer.speech_started":
                    logger.debug("User started speaking")

                elif event_type == "input_audio_buffer.speech_stopped":
                    logger.debug("User stopped speaking")

        except websockets.exceptions.ConnectionClosed:
            logger.info("Realtime WebSocket closed")
        except Exception:
            logger.exception("Realtime receive loop error")
        finally:
            self._running = False

    async def close(self) -> None:
        """Close the Realtime session."""
        self._running = False
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
