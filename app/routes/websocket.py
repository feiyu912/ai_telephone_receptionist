"""WebSocket media stream handler for Growth/Pro tier.

Uses OpenAI Realtime API (gpt-realtime-mini) for sub-second latency.
No separate STT/TTS needed — audio in, audio out, all in one model.

Flow:
  Twilio mulaw audio → OpenAI Realtime → mulaw audio → Twilio
  (direct passthrough, no audio conversion)
"""

from __future__ import annotations
import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.db.client import get_session_factory
from app.db import queries
from app.services.realtime import RealtimeSession
from app.prompts.system import build_system_prompt

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


@router.websocket("/ws/media-stream/{call_sid}")
async def media_stream(ws: WebSocket, call_sid: str):
    await ws.accept()

    # Session state
    stream_sid: str | None = None
    tenant_id: str | None = None
    caller_phone: str = ""
    is_returning: bool = False
    conversation_history: list[dict] = []
    realtime: RealtimeSession | None = None

    # Lock for safe concurrent writes to Twilio WebSocket
    ws_write_lock = asyncio.Lock()

    audio_out_count = 0

    async def on_realtime_audio(audio_b64: str):
        """Forward OpenAI Realtime audio to Twilio."""
        nonlocal audio_out_count
        if stream_sid:
            async with ws_write_lock:
                try:
                    await ws.send_text(json.dumps({
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {"payload": audio_b64},
                    }))
                    audio_out_count += 1
                    if audio_out_count == 1:
                        logger.info("First audio out to Twilio: %d bytes b64", len(audio_b64))
                except Exception:
                    logger.exception("Failed to send audio to Twilio")

    async def on_transcript(role: str, text: str):
        """Track conversation transcripts for post-call processing."""
        logger.info("Transcript [%s]: %s", role, text[:80])
        conversation_history.append({"role": role, "content": text})

    async def on_tool_call(call_id: str, name: str, args: dict) -> str:
        """Handle function calls from the Realtime model."""
        factory = get_session_factory()
        async with factory() as db:
            tid = tenant_id or ""

            if name == "end_call":
                logger.info("Tool: end_call")
                return "Call ending. Say goodbye."

            elif name == "transfer_to_human":
                logger.info("Tool: transfer_to_human")
                await queries.log_analytics_event(
                    db, tid, "transfer_requested", "voice",
                    phone=caller_phone, session_id=call_sid,
                )
                return "Transferring the caller now."

            elif name == "book_appointment":
                logger.info("Tool: book_appointment %s", args)
                await queries.update_voice_session(
                    db, call_sid,
                    booking_context={"requested": True, "details": args},
                )
                return f"Appointment noted for {args.get('preferred_date', '')} at {args.get('preferred_time', '')}. Confirm with the caller."

            elif name == "save_caller_memory":
                key = args.get("key", "")
                value = args.get("value", "")
                if key and value:
                    await queries.save_caller_memory(
                        db, tid, caller_phone, key, value,
                        channel="voice", session_id=call_sid,
                    )
                return f"Saved: {key}={value}"

            elif name == "set_memory_consent":
                consent = args.get("consent", False)
                await queries.save_caller_consent(db, tid, caller_phone, consent, "voice")
                return f"Consent {'granted' if consent else 'declined'}."

            elif name == "forget_caller":
                await queries.forget_caller(db, tid, caller_phone)
                return "All caller data has been deleted."

            return "Unknown tool."

    # ── Main loop ──────────────────────────────────────────────────

    try:
        async for raw in ws.iter_text():
            msg = json.loads(raw)
            event = msg.get("event", "")

            if event == "connected":
                logger.info("Connected: %s", call_sid)

            elif event == "start":
                start_data = msg.get("start", {})
                stream_sid = start_data.get("streamSid")
                custom = start_data.get("customParameters", {})
                tenant_id = custom.get("tenant_id")
                caller_phone = custom.get("caller_phone", "")
                is_returning = custom.get("is_returning", "false") == "true"
                logger.info("Started: sid=%s tenant=%s", stream_sid, tenant_id)

                # Load tenant config + build system prompt
                greeting = ""
                system_prompt = ""
                try:
                    factory = get_session_factory()
                    async with factory() as db:
                        tenant = await queries.get_tenant_by_id(db, tenant_id) if tenant_id else None
                        if tenant:
                            memories = await queries.lookup_caller_memory(db, tenant.tenant_id, caller_phone)
                            system_prompt = build_system_prompt(tenant, memories, is_returning)

                            # Build greeting
                            if is_returning:
                                name_mem = next((m for m in memories if m.memory_key == "name"), None)
                                name = name_mem.memory_value if name_mem else None
                                if name and tenant.greeting_returning:
                                    greeting = tenant.greeting_returning.replace("{name}", name)
                                elif name:
                                    greeting = f"Welcome back, {name}! How can I help you today?"
                                else:
                                    greeting = tenant.greeting_returning or "Welcome back!"
                            else:
                                greeting = tenant.greeting_new or (
                                    f"Thank you for calling {tenant.company_name or 'us'}. "
                                    "How can I help you today?"
                                )
                except Exception:
                    logger.exception("Failed to load tenant config")
                    system_prompt = "You are a helpful AI receptionist. Answer calls warmly."
                    greeting = "Hello! How can I help you today?"

                # Start OpenAI Realtime session
                realtime = RealtimeSession(
                    system_prompt=system_prompt,
                    on_audio=on_realtime_audio,
                    on_transcript=on_transcript,
                    on_tool_call=on_tool_call,
                    voice="alloy",
                )
                await realtime.connect()
                logger.info("Realtime connected, sending greeting")

                # Send greeting
                await realtime.send_greeting(greeting)

            elif event == "media":
                # Forward Twilio audio directly to OpenAI Realtime
                if realtime:
                    audio_b64 = msg.get("media", {}).get("payload", "")
                    if audio_b64:
                        await realtime.send_audio(audio_b64)

            elif event == "stop":
                logger.info("Stopped: %s", call_sid)
                break

    except WebSocketDisconnect:
        logger.info("Disconnected: %s", call_sid)
    except Exception:
        logger.exception("WebSocket error: %s", call_sid)
    finally:
        if realtime:
            await realtime.close()

        # Save conversation
        try:
            factory = get_session_factory()
            async with factory() as db:
                await queries.update_voice_session(
                    db, call_sid,
                    conversation_history=conversation_history,
                    status="closed",
                )
        except Exception:
            pass
