"""WebSocket media stream handler for Growth/Pro tier.

Uses OpenAI Realtime API (gpt-realtime-mini) for sub-second latency.
Single-task WebSocket handling to avoid concurrent read/write issues.
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

    # Queue for outbound messages — drained in the main loop
    outbound: asyncio.Queue[str] = asyncio.Queue()

    async def on_realtime_audio(audio_b64: str):
        """Queue audio for Twilio (will be sent from main loop)."""
        if stream_sid:
            await outbound.put(json.dumps({
                "event": "media",
                "streamSid": stream_sid,
                "media": {"payload": audio_b64},
            }))

    async def on_transcript(role: str, text: str):
        logger.info("Transcript [%s]: %s", role, text[:80])
        conversation_history.append({"role": role, "content": text})

    async def on_tool_call(call_id: str, name: str, args: dict) -> str:
        factory = get_session_factory()
        async with factory() as db:
            tid = tenant_id or ""
            if name == "end_call":
                return "Call ending. Say goodbye."
            elif name == "transfer_to_human":
                await queries.log_analytics_event(db, tid, "transfer_requested", "voice", phone=caller_phone, session_id=call_sid)
                return "Transferring the caller now."
            elif name == "book_appointment":
                await queries.update_voice_session(db, call_sid, booking_context={"requested": True, "details": args})
                return f"Appointment noted for {args.get('preferred_date', '')} at {args.get('preferred_time', '')}."
            elif name == "save_caller_memory":
                key, value = args.get("key", ""), args.get("value", "")
                if key and value:
                    await queries.save_caller_memory(db, tid, caller_phone, key, value, channel="voice", session_id=call_sid)
                return f"Saved: {key}={value}"
            elif name == "set_memory_consent":
                await queries.save_caller_consent(db, tid, caller_phone, args.get("consent", False), "voice")
                return "Consent recorded."
            elif name == "forget_caller":
                await queries.forget_caller(db, tid, caller_phone)
                return "All caller data deleted."
            return "Done."

    # ── Main loop: handles BOTH inbound (Twilio) and outbound (to Twilio) ──

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

                # Load tenant config
                greeting = ""
                system_prompt = ""
                try:
                    factory = get_session_factory()
                    async with factory() as db:
                        tenant = await queries.get_tenant_by_id(db, tenant_id) if tenant_id else None
                        if tenant:
                            memories = await queries.lookup_caller_memory(db, tenant.tenant_id, caller_phone)
                            system_prompt = build_system_prompt(tenant, memories, is_returning)
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
                                greeting = tenant.greeting_new or f"Thank you for calling {tenant.company_name or 'us'}. How can I help you today?"
                except Exception:
                    logger.exception("Failed to load tenant config")
                    system_prompt = "You are a helpful AI receptionist."
                    greeting = "Hello! How can I help you?"

                # Start Realtime
                realtime = RealtimeSession(
                    system_prompt=system_prompt,
                    on_audio=on_realtime_audio,
                    on_transcript=on_transcript,
                    on_tool_call=on_tool_call,
                )
                await realtime.connect()
                logger.info("Realtime connected, sending greeting")
                await realtime.send_greeting(greeting)

            elif event == "media":
                if realtime:
                    audio_b64 = msg.get("media", {}).get("payload", "")
                    if audio_b64:
                        await realtime.send_audio(audio_b64)

            elif event == "stop":
                logger.info("Stopped: %s", call_sid)
                break

            # Drain outbound queue after each inbound message
            while not outbound.empty():
                try:
                    out_msg = outbound.get_nowait()
                    await ws.send_text(out_msg)
                except Exception:
                    break

    except WebSocketDisconnect:
        logger.info("Disconnected: %s", call_sid)
    except Exception:
        logger.exception("WebSocket error: %s", call_sid)
    finally:
        if realtime:
            await realtime.close()
        try:
            factory = get_session_factory()
            async with factory() as db:
                await queries.update_voice_session(db, call_sid, conversation_history=conversation_history, status="closed")
        except Exception:
            pass
