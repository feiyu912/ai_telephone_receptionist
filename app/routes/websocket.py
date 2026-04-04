"""WebSocket media stream handler for Growth/Pro tier.

Uses Cartesia SDK for TTS (managed WebSocket), raw WebSocket for STT.
Outbound audio queue prevents concurrent write issues on Twilio WebSocket.
Streaming: GPT tokens → sentence buffer → Cartesia TTS → Twilio audio.
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
from app.services.tts import TTSContext, extract_sentences, VOICE_MAP, DEFAULT_VOICE_ID
from app.services import llm
from app.services.faq import match_faq
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
    stt_session: STTSession | None = None
    tts_ctx: TTSContext | None = None
    greeting_sent = False
    is_speaking = False

    # Outbound queue for safe concurrent writes to Twilio WebSocket
    outbound_queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def outbound_sender():
        """Dedicated task: sends queued messages to Twilio."""
        while True:
            msg = await outbound_queue.get()
            if msg is None:
                break
            try:
                await ws.send_json(msg)
            except Exception:
                break

    async def queue_audio(audio_bytes: bytes):
        """Queue TTS audio for Twilio playback."""
        if not stream_sid:
            return
        await outbound_queue.put({
            "event": "media",
            "streamSid": stream_sid,
            "media": {
                "payload": base64.b64encode(audio_bytes).decode("ascii"),
            },
        })

    async def on_transcript(text: str, is_final: bool):
        """Called by STT when transcription arrives."""
        nonlocal is_speaking
        logger.info("STT: '%s' final=%s", text, is_final)

        # Barge-in: cancel TTS if caller speaks during playback
        if is_speaking and is_final and tts_ctx:
            logger.info("Barge-in detected")
            await tts_ctx.cancel()
            is_speaking = False
            if stream_sid:
                await outbound_queue.put({"event": "clear", "streamSid": stream_sid})

        if is_final:
            asyncio.create_task(_process_speech(text))

    async def _process_speech(user_text: str):
        """Process speech: FAQ check → GPT streaming → TTS."""
        nonlocal conversation_history, is_speaking

        factory = get_session_factory()
        async with factory() as db:
            tenant = await queries.get_tenant_by_id(db, tenant_id) if tenant_id else None
            if not tenant:
                session_data = await queries.get_voice_session(db, call_sid)
                if session_data:
                    tenant = await queries.get_tenant_by_phone(db, session_data.get("called_number", ""))
            if not tenant:
                return

            memories = await queries.lookup_caller_memory(db, tenant.tenant_id, caller_phone)
            faqs = await queries.get_faq_entries(db, tenant.tenant_id)

            # FAQ check
            faq_match = match_faq(user_text, faqs)
            if faq_match:
                response_text = faq_match["answer"]
                conversation_history.append({"role": "user", "content": user_text})
                conversation_history.append({"role": "assistant", "content": response_text})
                if tts_ctx:
                    is_speaking = True
                    await tts_ctx.speak(response_text)
                    is_speaking = False
                await queries.update_voice_session(db, call_sid, conversation_history=conversation_history)
                return

            # Stream GPT → sentence buffer → TTS
            faq_context = "\n".join(f"Q: {f['question']}\nA: {f['answer']}" for f in faqs[:20])
            system_prompt = build_system_prompt(tenant, memories, is_returning, faq_context=faq_context)

            is_speaking = True

            async def sentence_generator():
                """Yield (sentence, is_last) as GPT streams tokens."""
                buffer = ""
                async for token in llm.chat_stream(system_prompt, conversation_history, user_text):
                    buffer += token
                    sentences, buffer = extract_sentences(buffer)
                    for s in sentences:
                        yield (s, False)
                # Final remaining text
                if buffer.strip():
                    yield (buffer.strip(), True)
                else:
                    yield ("", True)

            try:
                full_text = await tts_ctx.stream_sentences(sentence_generator())
            except Exception:
                logger.exception("Stream error for %s", call_sid)
                full_text = "I'm sorry, could you repeat that?"
                if tts_ctx:
                    await tts_ctx.speak(full_text)

            is_speaking = False

            conversation_history.append({"role": "user", "content": user_text})
            conversation_history.append({"role": "assistant", "content": full_text})
            if len(conversation_history) > 50:
                conversation_history = conversation_history[-50:]
            await queries.update_voice_session(db, call_sid, conversation_history=conversation_history)

    async def _send_greeting():
        """Send initial greeting via TTS SDK."""
        nonlocal greeting_sent, is_speaking
        if greeting_sent:
            return
        greeting_sent = True

        try:
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
                    name = name_mem.memory_value if name_mem else None
                    if name and tenant.greeting_returning:
                        greeting = tenant.greeting_returning.replace("{name}", name)
                    elif name:
                        greeting = f"Welcome back, {name}! How can I help you today?"
                    else:
                        greeting = tenant.greeting_returning or "Welcome back! How can I help you?"
                else:
                    greeting = tenant.greeting_new or (
                        f"Thank you for calling {tenant.company_name or 'us'}. "
                        "How can I help you today?"
                    )

                logger.info("Greeting: '%s'", greeting)
                conversation_history.append({"role": "assistant", "content": greeting})

                is_speaking = True
                await tts_ctx.speak(greeting)
                is_speaking = False
                logger.info("Greeting done")

        except Exception:
            logger.exception("Greeting failed for %s", call_sid)
            is_speaking = False

    # ── Main loop ──────────────────────────────────────────────────

    sender_task = asyncio.create_task(outbound_sender())

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

                # Resolve voice preference
                voice_id = DEFAULT_VOICE_ID
                try:
                    factory = get_session_factory()
                    async with factory() as db:
                        t = await queries.get_tenant_by_id(db, tenant_id)
                        if t:
                            voice_id = VOICE_MAP.get(t.selected_voice, DEFAULT_VOICE_ID)
                except Exception:
                    pass

                # Start STT
                stt_session = STTSession(on_transcript=on_transcript)
                await stt_session.connect()

                # Start TTS (SDK managed WebSocket)
                tts_ctx = TTSContext(voice_id=voice_id, on_audio=queue_audio)
                await tts_ctx.connect()

                # Send greeting
                asyncio.create_task(_send_greeting())

            elif event == "media":
                if stt_session:
                    audio_b64 = msg.get("media", {}).get("payload", "")
                    if audio_b64:
                        await stt_session.send_audio(base64.b64decode(audio_b64))

            elif event == "stop":
                logger.info("Stopped: %s", call_sid)
                break

    except WebSocketDisconnect:
        logger.info("Disconnected: %s", call_sid)
    except Exception:
        logger.exception("WebSocket error: %s", call_sid)
    finally:
        await outbound_queue.put(None)
        sender_task.cancel()
        if stt_session:
            await stt_session.close()
        if tts_ctx:
            await tts_ctx.close()
        try:
            factory = get_session_factory()
            async with factory() as db:
                await queries.update_voice_session(
                    db, call_sid, conversation_history=conversation_history, status="closed",
                )
        except Exception:
            pass
