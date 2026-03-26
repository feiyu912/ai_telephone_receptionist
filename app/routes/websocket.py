"""WebSocket media stream handler for Growth/Pro tier.

Twilio <Connect><Stream> sends bidirectional audio via WebSocket.
This handler bridges Twilio <-> Cartesia STT <-> GPT-4 <-> Cartesia TTS.
"""

from __future__ import annotations
import asyncio
import base64
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.db.client import get_session_factory
from app.db import queries
from app.services.stt import STTSession
from app.services.tts import tts_stream, VOICE_MAP, DEFAULT_VOICE_ID
from app.services import llm
from app.services.faq import match_faq
from app.prompts.system import build_system_prompt

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


@router.websocket("/ws/media-stream/{call_sid}")
async def media_stream(ws: WebSocket, call_sid: str):
    """Handle Twilio Media Stream WebSocket for a single call.

    Flow:
    1. Twilio opens WS, sends 'connected' + 'start' events
    2. Audio arrives as 'media' events (base64 mulaw 8kHz)
    3. We pipe audio to Cartesia STT
    4. On final transcript → GPT-4 → Cartesia TTS → pipe audio back to Twilio
    5. On 'stop' event → trigger post-call processing
    """
    await ws.accept()

    # Session state
    stream_sid: str | None = None
    tenant_id: str | None = None
    caller_phone: str = ""
    is_returning: bool = False
    conversation_history: list[dict] = []
    stt_session: STTSession | None = None
    pending_transcript: str = ""
    processing_lock = asyncio.Lock()
    greeting_sent = False

    async def on_transcript(text: str, is_final: bool):
        """Called by STT session when transcription arrives."""
        nonlocal pending_transcript

        if not is_final:
            # Accumulate partial results
            return

        # Final transcript — process it
        pending_transcript = text
        asyncio.create_task(_process_speech(text))

    async def _process_speech(user_text: str):
        """Process final STT transcript: FAQ check → GPT-4 → TTS → send audio."""
        nonlocal conversation_history

        async with processing_lock:
            factory = get_session_factory()
            async with factory() as db:
                tenant = await queries.get_tenant_by_id(db, tenant_id) if tenant_id else None
                if not tenant:
                    # Fallback: load from session
                    session_data = await queries.get_voice_session(db, call_sid)
                    if session_data:
                        tenant = await queries.get_tenant_by_phone(db, session_data.get("called_number", ""))

                if not tenant:
                    logger.error("No tenant for WS call %s", call_sid)
                    return

                memories = await queries.lookup_caller_memory(db, tenant.tenant_id, caller_phone)
                faqs = await queries.get_faq_entries(db, tenant.tenant_id)

                # Check FAQ first
                faq_match = match_faq(user_text, faqs)
                if faq_match:
                    ai_response = faq_match["answer"]
                else:
                    faq_context = "\n".join(
                        f"Q: {f['question']}\nA: {f['answer']}" for f in faqs[:20]
                    )
                    system_prompt = build_system_prompt(
                        tenant, memories, is_returning,
                        faq_context=faq_context,
                    )
                    ai_response = await llm.chat(
                        system_prompt, conversation_history, user_text
                    )

                # Parse tags
                action = llm.parse_tags(ai_response)

                # Update history
                conversation_history.append({"role": "user", "content": user_text})
                conversation_history.append({"role": "assistant", "content": action.clean_text})

                # Trim history (Growth=50)
                max_turns = 50
                if len(conversation_history) > max_turns:
                    conversation_history = conversation_history[-max_turns:]

                # Persist session
                await queries.update_voice_session(
                    db, call_sid, conversation_history=conversation_history,
                )

                # Stream TTS audio back to Twilio
                voice_id = VOICE_MAP.get(tenant.selected_voice, DEFAULT_VOICE_ID)
                await _send_tts(action.clean_text, voice_id)

                # Handle action tags
                if action.tag == "END_CALL":
                    await _close_stream()
                elif action.tag == "TRANSFER":
                    # For WebSocket path, we need to signal Twilio to transfer
                    # This requires closing the stream and using REST API
                    await queries.log_analytics_event(
                        db, tenant.tenant_id, "transfer_requested", "voice",
                        phone=caller_phone, session_id=call_sid,
                    )
                    await _close_stream()
                elif action.tag == "CONSENT_YES":
                    await queries.save_caller_consent(
                        db, tenant.tenant_id, caller_phone, True, "voice"
                    )
                elif action.tag == "CONSENT_NO":
                    await queries.save_caller_consent(
                        db, tenant.tenant_id, caller_phone, False, "voice"
                    )
                elif action.tag == "FORGET_ME":
                    await queries.forget_caller(db, tenant.tenant_id, caller_phone)

    async def _send_tts(text: str, voice_id: str):
        """Stream Cartesia TTS audio back to Twilio via WebSocket."""
        if not stream_sid:
            return
        try:
            async for audio_chunk in tts_stream(text, voice_id):
                payload = {
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {
                        "payload": base64.b64encode(audio_chunk).decode("ascii"),
                    },
                }
                await ws.send_json(payload)
        except Exception:
            logger.exception("TTS streaming error for call %s", call_sid)

    async def _send_greeting():
        """Send the initial greeting via TTS."""
        nonlocal greeting_sent
        if greeting_sent:
            return
        greeting_sent = True

        factory = get_session_factory()
        async with factory() as db:
            session_data = await queries.get_voice_session(db, call_sid)
            if not session_data:
                return

            tenant = await queries.get_tenant_by_phone(db, session_data.get("called_number", ""))
            if not tenant:
                return

            memories = await queries.lookup_caller_memory(db, tenant.tenant_id, caller_phone)

            if is_returning:
                name_mem = next((m for m in memories if m.memory_key == "name"), None)
                caller_name = name_mem.memory_value if name_mem else None
                if caller_name and tenant.greeting_returning:
                    greeting = tenant.greeting_returning.replace("{name}", caller_name)
                elif caller_name:
                    greeting = f"Welcome back, {caller_name}! How can I help you today?"
                else:
                    greeting = tenant.greeting_returning or "Welcome back! How can I help you?"
            else:
                greeting = tenant.greeting_new or (
                    f"Thank you for calling {tenant.company_name or 'us'}. "
                    "How can I help you today?"
                )

            conversation_history.append({"role": "assistant", "content": greeting})

            voice_id = VOICE_MAP.get(tenant.selected_voice, DEFAULT_VOICE_ID)
            await _send_tts(greeting, voice_id)

    async def _close_stream():
        """Gracefully close the media stream."""
        try:
            await ws.send_json({"event": "stop", "streamSid": stream_sid})
        except Exception:
            pass

    # ── Main WebSocket message loop ────────────────────────────────

    try:
        async for raw in ws.iter_text():
            msg = json.loads(raw)
            event = msg.get("event", "")

            if event == "connected":
                logger.info("Media stream connected: %s", call_sid)

            elif event == "start":
                start_data = msg.get("start", {})
                stream_sid = start_data.get("streamSid")
                custom = start_data.get("customParameters", {})
                tenant_id = custom.get("tenant_id")
                caller_phone = custom.get("caller_phone", "")
                is_returning = custom.get("is_returning", "false") == "true"

                logger.info(
                    "Stream started: sid=%s tenant=%s caller=%s",
                    stream_sid, tenant_id, caller_phone,
                )

                # Start STT session
                stt_session = STTSession(on_transcript=on_transcript)
                await stt_session.connect()

                # Send greeting
                asyncio.create_task(_send_greeting())

            elif event == "media":
                # Forward audio to STT
                if stt_session:
                    audio_b64 = msg.get("media", {}).get("payload", "")
                    if audio_b64:
                        audio_bytes = base64.b64decode(audio_b64)
                        await stt_session.send_audio(audio_bytes)

            elif event == "stop":
                logger.info("Media stream stopped: %s", call_sid)
                break

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: %s", call_sid)
    except Exception:
        logger.exception("WebSocket error: %s", call_sid)
    finally:
        # Cleanup
        if stt_session:
            await stt_session.close()

        # Save final session state
        try:
            factory = get_session_factory()
            async with factory() as db:
                await queries.update_voice_session(
                    db, call_sid,
                    conversation_history=conversation_history,
                    status="closed",
                )
        except Exception:
            logger.exception("Failed to save final session state: %s", call_sid)
