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

    # Process initial Twilio events to get stream_sid and tenant config
    async for message in websocket.iter_text():
        data = json.loads(message)
        if data["event"] == "connected":
            logger.info("Connected: %s", call_sid)
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
            break  # Got start event, proceed to OpenAI connection

    if not stream_sid:
        logger.error("No stream_sid received")
        return

    # NOW connect to OpenAI — after we have tenant config
    async with websockets.connect(
        "wss://api.openai.com/v1/realtime?model=gpt-realtime-mini",
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

        # Initialize session — BEFORE asyncio.gather, like the official example
        await openai_ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "turn_detection": {"type": "server_vad"},
                "input_audio_format": "g711_ulaw",
                "output_audio_format": "g711_ulaw",
                "voice": "alloy",
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
                    if data["event"] == "media" and openai_ws.open:
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
                if openai_ws.open:
                    await openai_ws.close()

        async def send_to_twilio():
            nonlocal last_assistant_item, response_start_timestamp_twilio
            try:
                async for openai_message in openai_ws:
                    response = json.loads(openai_message)
                    event_type = response.get("type", "")

                    if event_type in LOG_EVENT_TYPES:
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

                    # User transcript
                    elif event_type == "conversation.item.input_audio_transcription.completed":
                        transcript = response.get("transcript", "")
                        if transcript:
                            logger.info("User: %s", transcript[:80])
                            conversation_history.append({"role": "user", "content": transcript})

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
            factory = get_session_factory()
            async with factory() as db:
                tid = tenant_id
                if name == "end_call":
                    return "Call ending."
                elif name == "transfer_to_human":
                    await queries.log_analytics_event(db, tid, "transfer_requested", "voice", phone=caller_phone, session_id=call_sid)
                    return "Transferring."
                elif name == "book_appointment":
                    await queries.update_voice_session(db, call_sid, booking_context={"requested": True, "details": args})
                    return f"Appointment noted for {args.get('preferred_date', '')} at {args.get('preferred_time', '')}."
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
