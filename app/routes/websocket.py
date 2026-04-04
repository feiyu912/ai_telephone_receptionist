"""WebSocket media stream handler for Growth/Pro tier.

Based on the official Twilio + OpenAI Realtime API example:
https://github.com/twilio-samples/speech-assistant-openai-realtime-api-python

Two concurrent tasks via asyncio.gather():
- receive_from_twilio: reads Twilio audio, forwards to OpenAI
- send_to_twilio: reads OpenAI audio/events, forwards to Twilio
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


@router.websocket("/ws/media-stream/{call_sid}")
async def media_stream(websocket: WebSocket, call_sid: str):
    """Handle Twilio Media Stream, bridge to OpenAI Realtime API."""
    await websocket.accept()
    settings = get_settings()

    # Load tenant config and build system prompt
    system_prompt = "You are a helpful AI receptionist."
    greeting = "Hello! How can I help you?"
    tenant_id = ""
    caller_phone = ""

    async with websockets.connect(
        "wss://api.openai.com/v1/realtime?model=gpt-realtime-mini",
        additional_headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
        },
    ) as openai_ws:

        # Connection state
        stream_sid = None
        latest_media_timestamp = 0
        last_assistant_item = None
        mark_queue = []
        response_start_timestamp_twilio = None
        conversation_history: list[dict] = []

        async def initialize_session():
            """Configure the OpenAI Realtime session (GA API format)."""
            session_update = {
                "type": "session.update",
                "session": {
                    "type": "realtime",
                    "model": "gpt-realtime-mini",
                    "instructions": system_prompt,
                    "audio": {
                        "input": {
                            "format": {"type": "audio/pcmu"},
                            "turn_detection": {"type": "server_vad"},
                            "transcription": {
                                "model": "gpt-4o-mini-transcribe",
                            },
                        },
                        "output": {
                            "format": {"type": "audio/pcmu"},
                            "voice": "alloy",
                        },
                    },
                    "tools": [{"type": "function", **t["function"]} for t in VOICE_TOOLS],
                },
            }
            await openai_ws.send(json.dumps(session_update))

        async def send_greeting():
            """Have the AI speak a greeting."""
            await openai_ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{
                        "type": "input_text",
                        "text": f"Greet the caller with: '{greeting}'",
                    }],
                },
            }))
            await openai_ws.send(json.dumps({"type": "response.create"}))

        async def receive_from_twilio():
            """Receive audio from Twilio, forward to OpenAI."""
            nonlocal stream_sid, latest_media_timestamp, tenant_id, caller_phone
            nonlocal system_prompt, greeting
            try:
                async for message in websocket.iter_text():
                    data = json.loads(message)

                    if data["event"] == "media" and openai_ws.open:
                        latest_media_timestamp = int(data["media"]["timestamp"])
                        await openai_ws.send(json.dumps({
                            "type": "input_audio_buffer.append",
                            "audio": data["media"]["payload"],
                        }))

                    elif data["event"] == "start":
                        start = data["start"]
                        stream_sid = start["streamSid"]
                        custom = start.get("customParameters", {})
                        tenant_id = custom.get("tenant_id", "")
                        caller_phone = custom.get("caller_phone", "")
                        is_returning = custom.get("is_returning", "false") == "true"

                        logger.info("Stream started: sid=%s tenant=%s", stream_sid, tenant_id)

                        # Load tenant config
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
                                        greeting = tenant.greeting_new or (
                                            f"Thank you for calling {tenant.company_name or 'us'}. "
                                            "How can I help you today?"
                                        )

                                    # Create voice session
                                    from app.models.schemas import VoiceSession
                                    session = VoiceSession(
                                        call_sid=call_sid, caller_phone=caller_phone,
                                        called_number=tenant.phone_number,
                                        tenant_id=tenant.tenant_id,
                                        tier=tenant.tier, selected_voice=tenant.selected_voice,
                                    )
                                    await queries.create_voice_session(db, session)
                        except Exception:
                            logger.exception("Failed to load tenant config")

                        # Initialize OpenAI session with tenant prompt
                        await initialize_session()
                        await send_greeting()

                    elif data["event"] == "mark":
                        if mark_queue:
                            mark_queue.pop(0)

            except WebSocketDisconnect:
                logger.info("Twilio disconnected: %s", call_sid)
                if openai_ws.open:
                    await openai_ws.close()

        async def send_to_twilio():
            """Receive events from OpenAI, forward audio to Twilio."""
            nonlocal last_assistant_item, response_start_timestamp_twilio
            try:
                audio_chunks = 0
                async for openai_message in openai_ws:
                    response = json.loads(openai_message)
                    event_type = response.get("type", "")

                    # Log all event types for debugging
                    if "audio" in event_type or event_type not in ("response.output_audio.delta",):
                        if event_type != "response.output_audio.delta":
                            logger.info("OpenAI event: %s", event_type)

                    # Forward audio to Twilio
                    if event_type == "response.output_audio.delta" and "delta" in response:
                        audio_chunks += 1
                        if audio_chunks == 1:
                            logger.info("First audio delta received, forwarding to Twilio")
                        audio_payload = base64.b64encode(
                            base64.b64decode(response["delta"])
                        ).decode("utf-8")
                        await websocket.send_json({
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {"payload": audio_payload},
                        })

                        # Track response timing for interruption
                        if response.get("item_id") and response["item_id"] != last_assistant_item:
                            response_start_timestamp_twilio = latest_media_timestamp
                            last_assistant_item = response["item_id"]

                        # Send mark after each audio chunk
                        if stream_sid:
                            await websocket.send_json({
                                "event": "mark",
                                "streamSid": stream_sid,
                                "mark": {"name": "responsePart"},
                            })
                            mark_queue.append("responsePart")

                    # Transcript of what AI said
                    elif event_type == "response.output_audio_transcript.done":
                        transcript = response.get("transcript", "")
                        if transcript:
                            logger.info("AI said: %s", transcript[:80])
                            conversation_history.append({"role": "assistant", "content": transcript})

                    # Transcript of what user said
                    elif event_type == "conversation.item.input_audio_transcription.completed":
                        transcript = response.get("transcript", "")
                        if transcript:
                            logger.info("User said: %s", transcript[:80])
                            conversation_history.append({"role": "user", "content": transcript})

                    # Function call completed
                    elif event_type == "response.function_call_arguments.done":
                        await handle_function_call(response, openai_ws)

                    # Interruption: user started speaking
                    elif event_type == "input_audio_buffer.speech_started":
                        logger.info("User speaking — interrupting AI")
                        if mark_queue and response_start_timestamp_twilio is not None:
                            elapsed = latest_media_timestamp - response_start_timestamp_twilio
                            if last_assistant_item:
                                await openai_ws.send(json.dumps({
                                    "type": "conversation.item.truncate",
                                    "item_id": last_assistant_item,
                                    "content_index": 0,
                                    "audio_end_ms": elapsed,
                                }))
                            await websocket.send_json({
                                "event": "clear",
                                "streamSid": stream_sid,
                            })
                            mark_queue.clear()
                            last_assistant_item = None
                            response_start_timestamp_twilio = None

                    # Log key events
                    elif event_type in ("error", "session.created", "session.updated"):
                        logger.info("OpenAI event: %s %s", event_type,
                                    response.get("error", {}) if event_type == "error" else "")

            except Exception as e:
                logger.error("send_to_twilio error: %s", e)

        async def handle_function_call(response, openai_ws):
            """Execute a function call and return result to OpenAI."""
            call_id = response.get("call_id", "")
            name = response.get("name", "")
            try:
                args = json.loads(response.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}

            logger.info("Tool call: %s(%s)", name, args)
            output = "Done."

            factory = get_session_factory()
            async with factory() as db:
                tid = tenant_id
                if name == "end_call":
                    output = "Call ending."
                elif name == "transfer_to_human":
                    await queries.log_analytics_event(db, tid, "transfer_requested", "voice", phone=caller_phone, session_id=call_sid)
                    output = "Transferring."
                elif name == "book_appointment":
                    await queries.update_voice_session(db, call_sid, booking_context={"requested": True, "details": args})
                    output = f"Appointment noted for {args.get('preferred_date', '')} at {args.get('preferred_time', '')}."
                elif name == "save_caller_memory":
                    key, value = args.get("key", ""), args.get("value", "")
                    if key and value:
                        await queries.save_caller_memory(db, tid, caller_phone, key, value, channel="voice", session_id=call_sid)
                    output = f"Saved {key}."
                elif name == "set_memory_consent":
                    await queries.save_caller_consent(db, tid, caller_phone, args.get("consent", False), "voice")
                    output = "Consent recorded."
                elif name == "forget_caller":
                    await queries.forget_caller(db, tid, caller_phone)
                    output = "Data deleted."

            await openai_ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": output,
                },
            }))
            await openai_ws.send(json.dumps({"type": "response.create"}))

        # Run both tasks concurrently
        await asyncio.gather(receive_from_twilio(), send_to_twilio())

    # Save conversation after disconnect
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
