"""WebSocket media stream handler for Growth/Pro tier.

Twilio <Connect><Stream> sends bidirectional audio via WebSocket.
This handler bridges Twilio <-> Cartesia STT <-> GPT-4/5 <-> Cartesia TTS.

Key features:
- Streaming: GPT tokens → sentence buffer → Cartesia TTS continuation
- Barge-in: caller speech cancels current TTS and triggers new response
- Persistent TTS WebSocket for low-latency sentence piping
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
    processing_lock = asyncio.Lock()
    greeting_sent = False
    is_speaking = False  # True when TTS is playing

    audio_chunks_sent = 0

    async def send_audio_to_twilio(audio_bytes: bytes):
        """Callback: pipe TTS audio chunk to Twilio."""
        nonlocal audio_chunks_sent
        if not stream_sid:
            logger.warning("No stream_sid, dropping audio chunk")
            return
        payload = {
            "event": "media",
            "streamSid": stream_sid,
            "media": {
                "payload": base64.b64encode(audio_bytes).decode("ascii"),
            },
        }
        try:
            await ws.send_json(payload)
            audio_chunks_sent += 1
            if audio_chunks_sent == 1:
                logger.info("First audio chunk sent to Twilio: %d bytes", len(audio_bytes))
        except Exception:
            logger.exception("Failed to send audio to Twilio")

    async def on_transcript(text: str, is_final: bool):
        """Called by STT when transcription arrives."""
        nonlocal is_speaking
        logger.info("STT: '%s' final=%s speaking=%s", text, is_final, is_speaking)

        # Barge-in: if caller speaks while TTS is playing, cancel TTS
        if is_speaking and is_final and tts_ctx:
            logger.info("Barge-in detected, cancelling TTS")
            await tts_ctx.cancel()
            is_speaking = False
            # Also clear Twilio's audio buffer
            if stream_sid:
                try:
                    await ws.send_json({"event": "clear", "streamSid": stream_sid})
                except Exception:
                    pass

        if not is_final:
            return
        asyncio.create_task(_process_speech(text))

    async def _process_speech(user_text: str):
        """Stream GPT response sentence-by-sentence to TTS."""
        nonlocal conversation_history, is_speaking

        async with processing_lock:
            factory = get_session_factory()
            async with factory() as db:
                tenant = await queries.get_tenant_by_id(db, tenant_id) if tenant_id else None
                if not tenant:
                    session_data = await queries.get_voice_session(db, call_sid)
                    if session_data:
                        tenant = await queries.get_tenant_by_phone(db, session_data.get("called_number", ""))
                if not tenant:
                    logger.error("No tenant for call %s", call_sid)
                    return

                memories = await queries.lookup_caller_memory(db, tenant.tenant_id, caller_phone)
                faqs = await queries.get_faq_entries(db, tenant.tenant_id)

                # Check FAQ first
                faq_match = match_faq(user_text, faqs)
                if faq_match:
                    # FAQ match: send directly to TTS
                    response_text = faq_match["answer"]
                    conversation_history.append({"role": "user", "content": user_text})
                    conversation_history.append({"role": "assistant", "content": response_text})
                    if tts_ctx:
                        tts_ctx.new_turn()
                        is_speaking = True
                        await tts_ctx.send_sentence(response_text, more_coming=False)
                        # Wait a bit for audio to finish
                        await asyncio.sleep(0.5)
                        is_speaking = False
                else:
                    # Stream GPT → sentence buffer → TTS
                    faq_context = "\n".join(
                        f"Q: {f['question']}\nA: {f['answer']}" for f in faqs[:20]
                    )
                    system_prompt = build_system_prompt(
                        tenant, memories, is_returning,
                        faq_context=faq_context,
                    )

                    if tts_ctx:
                        tts_ctx.new_turn()

                    is_speaking = True
                    full_response = ""
                    sentence_buffer = ""

                    try:
                        async for token in llm.chat_stream(
                            system_prompt, conversation_history, user_text
                        ):
                            full_response += token
                            sentence_buffer += token

                            # Check for complete sentences
                            sentences, sentence_buffer = extract_sentences(sentence_buffer)
                            for sentence in sentences:
                                if tts_ctx and sentence.strip():
                                    logger.info("Streaming sentence to TTS: '%s'", sentence[:50])
                                    await tts_ctx.send_sentence(sentence, more_coming=True)

                        # Send remaining buffer as final sentence
                        if sentence_buffer.strip() and tts_ctx:
                            logger.info("Streaming final to TTS: '%s'", sentence_buffer.strip()[:50])
                            await tts_ctx.send_sentence(sentence_buffer.strip(), more_coming=False)

                    except Exception:
                        logger.exception("GPT streaming error for %s", call_sid)
                        # Fallback: if streaming failed, try non-streaming
                        if not full_response:
                            result = await llm.chat(system_prompt, conversation_history, user_text)
                            full_response = result.text or "I'm sorry, could you repeat that?"
                            if tts_ctx:
                                await tts_ctx.send_sentence(full_response, more_coming=False)

                    # Wait for TTS to finish playing
                    await asyncio.sleep(1.0)
                    is_speaking = False

                    response_text = full_response
                    conversation_history.append({"role": "user", "content": user_text})
                    conversation_history.append({"role": "assistant", "content": response_text})

                # Trim history
                if len(conversation_history) > 50:
                    conversation_history = conversation_history[-50:]

                # Persist session
                await queries.update_voice_session(
                    db, call_sid, conversation_history=conversation_history,
                )

    async def _send_greeting():
        """Send initial greeting via one-shot TTS."""
        nonlocal greeting_sent, is_speaking
        if greeting_sent:
            return
        greeting_sent = True
        logger.info("Sending greeting for call %s", call_sid)

        try:
            factory = get_session_factory()
            async with factory() as db:
                session_data = await queries.get_voice_session(db, call_sid)
                if not session_data:
                    logger.error("No session for greeting: %s", call_sid)
                    return

                tenant = await queries.get_tenant_by_phone(db, session_data.get("called_number", ""))
                if not tenant:
                    logger.error("No tenant for greeting: %s", call_sid)
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

                logger.info("Greeting: '%s'", greeting)
                conversation_history.append({"role": "assistant", "content": greeting})

                # Use one-shot TTS for greeting (simpler)
                is_speaking = True
                voice_id = VOICE_MAP.get(tenant.selected_voice, DEFAULT_VOICE_ID)
                chunk_count = 0
                async for audio_chunk in tts_stream(greeting, voice_id):
                    await send_audio_to_twilio(audio_chunk)
                    chunk_count += 1
                is_speaking = False
                logger.info("Greeting sent: %d TTS chunks, %d sent to Twilio", chunk_count, audio_chunks_sent)

        except Exception:
            logger.exception("Greeting failed for %s", call_sid)
            is_speaking = False

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

                # Set up persistent TTS context for streaming
                voice_id = DEFAULT_VOICE_ID
                # Load tenant voice preference
                try:
                    factory = get_session_factory()
                    async with factory() as db:
                        tenant = await queries.get_tenant_by_id(db, tenant_id)
                        if tenant:
                            voice_id = VOICE_MAP.get(tenant.selected_voice, DEFAULT_VOICE_ID)
                except Exception:
                    pass
                tts_ctx = TTSContext(voice_id=voice_id, on_audio=send_audio_to_twilio)
                await tts_ctx.connect()

                # Send greeting
                asyncio.create_task(_send_greeting())

            elif event == "media":
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
        if stt_session:
            await stt_session.close()
        if tts_ctx:
            await tts_ctx.close()

        try:
            factory = get_session_factory()
            async with factory() as db:
                await queries.update_voice_session(
                    db, call_sid,
                    conversation_history=conversation_history,
                    status="closed",
                )
        except Exception:
            logger.exception("Failed to save session: %s", call_sid)
