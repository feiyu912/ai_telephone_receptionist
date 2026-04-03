"""WebSocket media stream handler for Growth/Pro tier.

Uses an outbound queue to safely send audio from background tasks
back through the Twilio WebSocket (avoids concurrent write issues).
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
from app.services.tts import TTSContext, extract_sentences, tts_stream, VOICE_MAP, DEFAULT_VOICE_ID
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

    # Outbound queue: all audio/commands to Twilio go through here
    # This prevents concurrent writes to the WebSocket
    outbound_queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def outbound_sender():
        """Dedicated task that sends queued messages to Twilio WebSocket."""
        chunks_sent = 0
        while True:
            msg = await outbound_queue.get()
            if msg is None:
                break
            try:
                await ws.send_json(msg)
                if msg.get("event") == "media":
                    chunks_sent += 1
                    if chunks_sent == 1:
                        logger.info("First audio chunk sent to Twilio")
            except Exception:
                break

    async def queue_audio(audio_bytes: bytes):
        """Queue a TTS audio chunk for sending to Twilio."""
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

        # Barge-in: cancel TTS if caller speaks
        if is_speaking and is_final and tts_ctx:
            logger.info("Barge-in: cancelling TTS")
            await tts_ctx.cancel()
            is_speaking = False
            if stream_sid:
                await outbound_queue.put({"event": "clear", "streamSid": stream_sid})

        if is_final:
            asyncio.create_task(_process_speech(text))

    async def _process_speech(user_text: str):
        """Stream GPT response sentence-by-sentence to TTS."""
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
                    tts_ctx.new_turn()
                    is_speaking = True
                    await tts_ctx.send_sentence(response_text, more_coming=False)
                    await asyncio.sleep(0.5)
                    is_speaking = False
                return

            # Stream GPT → sentence buffer → TTS
            faq_context = "\n".join(f"Q: {f['question']}\nA: {f['answer']}" for f in faqs[:20])
            system_prompt = build_system_prompt(tenant, memories, is_returning, faq_context=faq_context)

            if tts_ctx:
                tts_ctx.new_turn()

            is_speaking = True
            full_response = ""
            sentence_buffer = ""

            try:
                async for token in llm.chat_stream(system_prompt, conversation_history, user_text):
                    full_response += token
                    sentence_buffer += token

                    sentences, sentence_buffer = extract_sentences(sentence_buffer)
                    for sentence in sentences:
                        if tts_ctx and sentence.strip():
                            logger.info("→ TTS: '%s'", sentence[:60])
                            await tts_ctx.send_sentence(sentence, more_coming=True)

                # Send remaining text
                if sentence_buffer.strip() and tts_ctx:
                    logger.info("→ TTS final: '%s'", sentence_buffer.strip()[:60])
                    await tts_ctx.send_sentence(sentence_buffer.strip(), more_coming=False)

            except Exception:
                logger.exception("GPT stream error")
                if not full_response:
                    full_response = "I'm sorry, could you repeat that?"
                    if tts_ctx:
                        await tts_ctx.send_sentence(full_response, more_coming=False)

            await asyncio.sleep(0.5)
            is_speaking = False

            conversation_history.append({"role": "user", "content": user_text})
            conversation_history.append({"role": "assistant", "content": full_response})
            if len(conversation_history) > 50:
                conversation_history = conversation_history[-50:]
            await queries.update_voice_session(db, call_sid, conversation_history=conversation_history)

    async def _send_greeting():
        """Send initial greeting via one-shot TTS."""
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
                voice_id = VOICE_MAP.get(tenant.selected_voice, DEFAULT_VOICE_ID)
                chunk_count = 0
                async for audio_chunk in tts_stream(greeting, voice_id):
                    await queue_audio(audio_chunk)
                    chunk_count += 1
                is_speaking = False
                logger.info("Greeting queued: %d chunks", chunk_count)

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

                # Start STT
                stt_session = STTSession(on_transcript=on_transcript)
                await stt_session.connect()

                # Start persistent TTS context
                voice_id = DEFAULT_VOICE_ID
                try:
                    factory = get_session_factory()
                    async with factory() as db:
                        t = await queries.get_tenant_by_id(db, tenant_id)
                        if t:
                            voice_id = VOICE_MAP.get(t.selected_voice, DEFAULT_VOICE_ID)
                except Exception:
                    pass
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
        # Stop outbound sender
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
