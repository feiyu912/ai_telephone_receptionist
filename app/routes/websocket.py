"""WebSocket media stream handler for Growth/Pro tier.

Based on the official Twilio + OpenAI Realtime API example:
https://github.com/twilio-samples/speech-assistant-openai-realtime-api-python
"""

from __future__ import annotations
import asyncio
import base64
import json
import logging
import websockets
from fastapi import APIRouter, WebSocket
from fastapi.websockets import WebSocketDisconnect

from app.db.client import get_session_factory
from app.db import queries
from app.services.llm import VOICE_TOOLS
from app.prompts.system import build_system_prompt
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])

LOG_EVENT_TYPES = [
    "error", "response.content.done", "rate_limits.updated",
    "response.done", "input_audio_buffer.committed",
    "input_audio_buffer.speech_stopped", "input_audio_buffer.speech_started",
    "session.created", "session.updated",
]


@router.websocket("/ws/media-stream/{call_sid}")
async def media_stream(websocket: WebSocket, call_sid: str):
    await websocket.accept()
    settings = get_settings()

    # Wait for Twilio's connected + start events BEFORE connecting to OpenAI
    stream_sid = None
    tenant_id = ""
    caller_phone = ""
    system_prompt = "You are a helpful AI receptionist."
    greeting = "Hello! How can I help you?"

    # Process initial Twilio events to get stream_sid and tenant config.
    # SECURITY: tenant_id is resolved from the server-side voice_sessions
    # row (keyed by call_sid, created in /voice/incoming-call). We do NOT
    # trust customParameters.tenant_id — a crafted start event could
    # otherwise impersonate any tenant and leak their prompt / FAQs.
    async for message in websocket.iter_text():
        data = json.loads(message)
        if data["event"] == "connected":
            logger.info("Connected: %s", call_sid)
        elif data["event"] == "start":
            start = data["start"]
            stream_sid = start["streamSid"]

            try:
                factory = get_session_factory()
                async with factory() as db:
                    voice_session = await queries.get_voice_session(db, call_sid)
                    if not voice_session:
                        logger.warning(
                            "WebSocket start for unknown call_sid=%s — closing",
                            call_sid,
                        )
                        await websocket.close(code=1008)
                        return

                    tenant_id = voice_session["tenant_id"]
                    caller_phone = voice_session["caller_phone"]
                    logger.info("Stream started: sid=%s tenant=%s", stream_sid, tenant_id)

                    tenant = await queries.get_tenant_by_id(db, tenant_id)
                    if not tenant:
                        logger.warning("Tenant %s not found for call %s", tenant_id, call_sid)
                        await websocket.close(code=1008)
                        return

                    memories = await queries.lookup_caller_memory(
                        db, tenant.tenant_id, caller_phone
                    )
                    is_returning = len(memories) > 0
                    faqs = await queries.get_faq_entries(db, tenant.tenant_id)
                    faq_context = "\n".join(
                        f"Q: {f['question']}\nA: {f['answer']}" for f in faqs[:30]
                    )
                    system_prompt = build_system_prompt(
                        tenant, memories, is_returning, faq_context=faq_context
                    )
                    if is_returning:
                        name_mem = next(
                            (m for m in memories if m.memory_key == "name"), None
                        )
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
                logger.exception("Failed to load tenant config for call %s", call_sid)
                await websocket.close(code=1011)
                return
            break  # Got start event, proceed to OpenAI connection

    if not stream_sid:
        logger.error("No stream_sid received")
        return

    # NOW connect to OpenAI — after we have tenant config
    async with websockets.connect(
        f"wss://api.openai.com/v1/realtime?model={tenant.selected_model or 'gpt-realtime-mini'}",
        additional_headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "OpenAI-Beta": "realtime=v1",
        },
    ) as openai_ws:

        # State
        latest_media_timestamp = 0
        last_assistant_item = None
        mark_queue = []
        response_start_timestamp_twilio = None
        conversation_history: list[dict] = []
        end_call_pending = False  # Set when end_call tool fires; hangup after farewell

        # Initialize session — BEFORE asyncio.gather, like the official example
        await openai_ws.send(json.dumps({
            "type": "session.update",
            "session": {
                # VAD tuned for telephony where echo from speakers can leak
                # back into the mic. threshold higher than default 0.5 +
                # longer silence_duration_ms reduce echo-triggered barge-ins.
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.65,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500,
                },
                "input_audio_format": "g711_ulaw",
                "output_audio_format": "g711_ulaw",
                "input_audio_transcription": {"model": "whisper-1"},
                "voice": tenant.selected_voice or "alloy",
                "instructions": system_prompt,
                "modalities": ["text", "audio"],
                "tools": [{"type": "function", **t["function"]} for t in VOICE_TOOLS],
            },
        }))

        # Send greeting
        await openai_ws.send(json.dumps({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": f"Greet the caller with: '{greeting}'"}],
            },
        }))
        await openai_ws.send(json.dumps({"type": "response.create"}))

        async def receive_from_twilio():
            nonlocal latest_media_timestamp
            try:
                async for message in websocket.iter_text():
                    data = json.loads(message)
                    if data["event"] == "media" and openai_ws.state.name == "OPEN":
                        latest_media_timestamp = int(data["media"]["timestamp"])
                        await openai_ws.send(json.dumps({
                            "type": "input_audio_buffer.append",
                            "audio": data["media"]["payload"],
                        }))
                    elif data["event"] == "mark":
                        if mark_queue:
                            mark_queue.pop(0)
            except WebSocketDisconnect:
                logger.info("Twilio disconnected: %s", call_sid)
                if openai_ws.state.name == "OPEN":
                    await openai_ws.close()

        audio_chunks_sent = 0

        async def send_to_twilio():
            nonlocal last_assistant_item, response_start_timestamp_twilio, audio_chunks_sent
            try:
                async for openai_message in openai_ws:
                    response = json.loads(openai_message)
                    event_type = response.get("type", "")

                    if event_type == "error":
                        # Surface the full error body so we can see *why* OpenAI bailed
                        # (bad model name, scope mismatch, rate limit, etc.)
                        logger.error("OpenAI error event: %s", response)
                    elif event_type in LOG_EVENT_TYPES:
                        logger.info("OpenAI: %s", event_type)

                    # Forward audio to Twilio
                    if response.get("type") == "response.audio.delta" and "delta" in response:
                        audio_payload = base64.b64encode(
                            base64.b64decode(response["delta"])
                        ).decode("utf-8")
                        await websocket.send_json({
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {"payload": audio_payload},
                        })
                        audio_chunks_sent += 1
                        if audio_chunks_sent == 1:
                            logger.info("AUDIO SENT to Twilio: first chunk %d chars, streamSid=%s", len(audio_payload), stream_sid)
                        elif audio_chunks_sent % 50 == 0:
                            logger.info("AUDIO SENT to Twilio: %d chunks total", audio_chunks_sent)

                        if response.get("item_id") and response["item_id"] != last_assistant_item:
                            response_start_timestamp_twilio = latest_media_timestamp
                            last_assistant_item = response["item_id"]

                        # Send mark
                        await websocket.send_json({
                            "event": "mark",
                            "streamSid": stream_sid,
                            "mark": {"name": "responsePart"},
                        })
                        mark_queue.append("responsePart")

                    # AI transcript
                    elif event_type == "response.audio_transcript.done":
                        transcript = response.get("transcript", "")
                        if transcript:
                            logger.info("AI: %s", transcript[:80])
                            conversation_history.append({"role": "assistant", "content": transcript})
                            # Persist incrementally so status_callback sees up-to-date history
                            try:
                                factory = get_session_factory()
                                async with factory() as db:
                                    await queries.update_voice_session(
                                        db, call_sid, conversation_history=conversation_history,
                                    )
                            except Exception:
                                logger.debug("Failed to persist AI turn")

                    # User transcript
                    elif event_type == "conversation.item.input_audio_transcription.completed":
                        transcript = response.get("transcript", "")
                        if transcript:
                            logger.info("User: %s", transcript[:80])
                            conversation_history.append({"role": "user", "content": transcript})
                            try:
                                factory = get_session_factory()
                                async with factory() as db:
                                    await queries.update_voice_session(
                                        db, call_sid, conversation_history=conversation_history,
                                    )
                            except Exception:
                                logger.debug("Failed to persist user turn")

                    # Response complete — if end_call was triggered, hang up after farewell audio
                    elif event_type == "response.done":
                        if end_call_pending:
                            # Check if this response actually contained spoken audio (the farewell)
                            output_items = response.get("response", {}).get("output", [])
                            has_audio = any(
                                item.get("type") == "message" and any(
                                    c.get("type") == "audio" for c in item.get("content", [])
                                )
                                for item in output_items
                            )
                            if has_audio:
                                logger.info("Farewell finished, hanging up call %s", call_sid)
                                # Wait for audio to finish playing on caller's side
                                await asyncio.sleep(2.5)
                                try:
                                    await websocket.send_json({
                                        "event": "stop",
                                        "streamSid": stream_sid,
                                    })
                                except Exception:
                                    pass
                                try:
                                    await websocket.close()
                                except Exception:
                                    pass
                                try:
                                    await openai_ws.close()
                                except Exception:
                                    pass
                                return

                    # Function call
                    elif event_type == "response.function_call_arguments.done":
                        call_id = response.get("call_id", "")
                        name = response.get("name", "")
                        try:
                            args = json.loads(response.get("arguments", "{}"))
                        except json.JSONDecodeError:
                            args = {}
                        logger.info("Tool: %s(%s)", name, args)
                        output = await handle_tool_call(name, args)
                        await openai_ws.send(json.dumps({
                            "type": "conversation.item.create",
                            "item": {"type": "function_call_output", "call_id": call_id, "output": output},
                        }))
                        await openai_ws.send(json.dumps({"type": "response.create"}))

                    # Interruption
                    elif event_type == "input_audio_buffer.speech_started":
                        if mark_queue and response_start_timestamp_twilio is not None:
                            elapsed = latest_media_timestamp - response_start_timestamp_twilio
                            if last_assistant_item:
                                await openai_ws.send(json.dumps({
                                    "type": "conversation.item.truncate",
                                    "item_id": last_assistant_item,
                                    "content_index": 0,
                                    "audio_end_ms": elapsed,
                                }))
                            await websocket.send_json({"event": "clear", "streamSid": stream_sid})
                            mark_queue.clear()
                            last_assistant_item = None
                            response_start_timestamp_twilio = None

            except Exception as e:
                logger.error("send_to_twilio error: %s", e)

        async def handle_tool_call(name: str, args: dict) -> str:
            nonlocal end_call_pending
            factory = get_session_factory()
            async with factory() as db:
                tid = tenant_id
                if name == "end_call":
                    end_call_pending = True
                    return "Call ending. Say the farewell now, then I will hang up."
                elif name == "transfer_to_human":
                    await queries.log_analytics_event(db, tid, "transfer_requested", "voice", phone=caller_phone, session_id=call_sid)
                    # Realtime WS owns the call audio — to actually transfer
                    # we have to hand the call back to Twilio and redirect it
                    # to TwiML that <Dial>s the hunt group. Do that via the
                    # Twilio REST API with the tenant's own credentials.
                    if not tenant.hunt_group_numbers:
                        return "No hunt group configured. Tell the caller no one is available right now."
                    try:
                        from twilio.rest import Client as TwilioRestClient
                        from app.config import get_settings as _gs
                        s = _gs()
                        sid   = tenant.twilio_account_sid or s.twilio_account_sid
                        tok   = tenant.twilio_auth_token  or s.twilio_auth_token
                        base  = s.base_url.rstrip("/")
                        TwilioRestClient(sid, tok).calls(call_sid).update(
                            method="POST",
                            url=f"{base}/voice/transfer/{call_sid}",
                        )
                        # The redirect closes the media stream from Twilio's
                        # side; mark the session so post-call processing knows.
                        await queries.update_voice_session(db, call_sid, status="transferred")
                        return "Hand-off triggered. Tell the caller to hold while we connect."
                    except Exception:
                        logger.exception("Live-transfer redirect failed for %s", call_sid)
                        return "Transfer failed. Tell the caller you couldn't reach a teammate and offer to take a message."
                elif name == "book_appointment":
                    await queries.update_voice_session(db, call_sid, booking_context={"requested": True, "details": args})
                    # Try to book via Outlook Calendar (per-tenant mailbox + timezone, fall back to global env)
                    from app.services.calendar import book_appointment
                    from app.config import get_settings as gs
                    cal_email = tenant.calendar_email or gs().ms_calendar_email
                    if cal_email:
                        result = await book_appointment(
                            calendar_email=cal_email,
                            caller_phone=caller_phone,
                            caller_name=args.get("caller_name"),
                            caller_email=args.get("caller_email"),
                            preferred_date=args.get("preferred_date", ""),
                            preferred_time=args.get("preferred_time", ""),
                            purpose=args.get("purpose", "Consultation"),
                            timezone=tenant.business_hours_timezone,
                            duration_minutes=tenant.booking_duration_minutes,
                            business_hours_start=tenant.business_hours_start,
                            business_hours_end=tenant.business_hours_end,
                            tenant_id=tenant.tenant_id,
                        )
                        from app.prompts.system import _friendly_tz
                        tz_label = _friendly_tz(tenant.business_hours_timezone or "America/Chicago")
                        if result.get("success"):
                            return (
                                f"Appointment booked for {result['date']} at {result['slot']} {tz_label}. "
                                f"Confirm to the caller using exactly this date+time+timezone."
                            )
                        elif result.get("available_slots"):
                            slots_str = ", ".join(f"{s['label']} {tz_label}" for s in result["available_slots"])
                            return f"That time is not available. Available slots: {slots_str}. Ask the caller which they prefer."
                        return result.get("message", "Could not book. Ask caller to try another date.")
                    return f"Appointment noted for {args.get('preferred_date', '')} at {args.get('preferred_time', '')}. Calendar not configured yet."
                elif name == "save_caller_memory":
                    key, value = args.get("key", ""), args.get("value", "")
                    if key and value:
                        await queries.save_caller_memory(db, tid, caller_phone, key, value, channel="voice", session_id=call_sid)
                    return f"Saved {key}."
                elif name == "set_memory_consent":
                    await queries.save_caller_consent(db, tid, caller_phone, args.get("consent", False), "voice")
                    return "Consent recorded."
                elif name == "forget_caller":
                    await queries.forget_caller(db, tid, caller_phone)
                    return "Data deleted."
                elif name == "verify_identity":
                    ok = await queries.verify_caller_identity(
                        db, tid, caller_phone,
                        claimed_name=args.get("name", ""),
                        claimed_email=args.get("email", ""),
                    )
                    if ok:
                        # Reload memory and rebuild the system prompt with
                        # protected facts unlocked, then push it to OpenAI.
                        memories = await queries.lookup_caller_memory(db, tid, caller_phone)
                        new_prompt = build_system_prompt(
                            tenant, memories, is_returning=True,
                            identity_verified=True, faq_context=faq_context,
                        )
                        await openai_ws.send(json.dumps({
                            "type": "session.update",
                            "session": {"instructions": new_prompt},
                        }))
                        await queries.log_analytics_event(
                            db, tid, "identity_verified", "voice",
                            phone=caller_phone, session_id=call_sid,
                        )
                        return (
                            "Identity verified. Their stored details are now available "
                            "to you — you may reference their email and other protected "
                            "info naturally."
                        )
                    return (
                        "Identity verification FAILED. Treat the caller as a new person. "
                        "Do NOT reveal any stored details. Apologize politely and ask "
                        "them to provide info fresh."
                    )
                return "Done."

        await asyncio.gather(receive_from_twilio(), send_to_twilio())

    # Save conversation after disconnect
    try:
        factory = get_session_factory()
        async with factory() as db:
            await queries.update_voice_session(
                db, call_sid, conversation_history=conversation_history, status="closed",
            )
    except Exception:
        pass
