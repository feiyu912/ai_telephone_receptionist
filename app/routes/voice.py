"""Twilio voice webhook routes — incoming call + status callback.

Handles tier-based routing:
  Starter  → HTTP path (TwiML Gather/Say with Polly)
  Growth/Pro → WebSocket path (Connect/Stream → Cartesia)
"""

from __future__ import annotations
import logging
from fastapi import APIRouter, Request, Depends
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.client import get_db
from app.db import queries
from app.models.schemas import VoiceSession, TenantConfig
from app.services import llm
from app.services.faq import match_faq
from app.services.pii import mask_pii
from app.services.sms import send_sms, send_call_summary
from app.services.hubspot import sync_call as hubspot_sync
from app.services.email import send_voicemail_alert
from app.services.email_confirm import request_email_confirmation
from app.prompts.system import build_system_prompt
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["voice"])


# ── Incoming Call ──────────────────────────────────────────────────

@router.post("/incoming-call")
async def incoming_call(request: Request, db: AsyncSession = Depends(get_db)):
    """Twilio POSTs here when a call arrives. Resolves tenant, routes by tier."""
    form = await request.form()
    to_number = form.get("To", "")
    from_number = form.get("From", "")
    call_sid = form.get("CallSid", "")

    # 1. Tenant resolution
    tenant = await queries.get_tenant_by_phone(db, to_number)
    if not tenant:
        logger.warning("No tenant found for %s", to_number)
        return _twiml_response(
            '<Response><Say voice="Polly.Matthew-Neural">'
            "Sorry, this number is not configured. Goodbye."
            "</Say><Hangup/></Response>"
        )

    # 2. Load caller memory + check if returning
    memories = await queries.lookup_caller_memory(db, tenant.tenant_id, from_number)
    is_returning = len(memories) > 0

    # 3. Create voice session
    session = VoiceSession(
        call_sid=call_sid,
        caller_phone=from_number,
        called_number=to_number,
        tenant_id=tenant.tenant_id,
        tier=tenant.tier,
        selected_voice=tenant.selected_voice,
    )
    await queries.create_voice_session(db, session)

    # 4. Log analytics
    await queries.log_analytics_event(
        db, tenant.tenant_id, "call_started", "voice",
        phone=from_number, session_id=call_sid,
        event_data={"tier": tenant.tier, "is_returning": is_returning},
    )

    # 5. Route by tier (AI is 24/7, no business hours check)
    if tenant.tier in ("growth", "pro"):
        return _websocket_route(tenant, call_sid, from_number, is_returning)
    else:
        return _starter_route(tenant, is_returning, from_number, memories)


# ── Starter Tier: HTTP Gather/Say Loop ─────────────────────────────

@router.post("/starter-gather")
async def starter_gather(request: Request, db: AsyncSession = Depends(get_db)):
    """Handles Twilio <Gather> callback with caller speech for Starter tier."""
    form = await request.form()
    call_sid = form.get("CallSid", "")
    speech_result = form.get("SpeechResult", "")
    from_number = form.get("From", "")
    to_number = form.get("To", "")

    if not speech_result:
        # No speech detected — retry
        session_data = await queries.get_voice_session(db, call_sid)
        retry = (session_data or {}).get("session_metadata", {}).get("retry_count", 0)
        if retry >= 2:
            return _twiml_response(
                '<Response><Say voice="Polly.Matthew-Neural">'
                "I'm sorry, I couldn't hear you. Goodbye."
                "</Say><Hangup/></Response>"
            )
        if session_data:
            meta = session_data.get("session_metadata", {})
            meta["retry_count"] = retry + 1
            await queries.update_voice_session(db, call_sid, session_metadata=meta)
        settings = get_settings()
        return _twiml_response(
            f'<Response><Gather input="speech" timeout="5" speechTimeout="auto" '
            f'action="{settings.base_url}/voice/starter-gather">'
            f'<Say voice="Polly.Matthew-Neural">I didn\'t catch that. Could you please repeat?</Say>'
            f'</Gather></Response>'
        )

    # Load tenant + session
    tenant = await queries.get_tenant_by_phone(db, to_number)
    if not tenant:
        return _twiml_response('<Response><Say>Error.</Say><Hangup/></Response>')

    session_data = await queries.get_voice_session(db, call_sid)
    history = (session_data or {}).get("conversation_history", [])
    memories = await queries.lookup_caller_memory(db, tenant.tenant_id, from_number)
    is_returning = len(memories) > 0

    # Reset retry on successful speech
    meta = (session_data or {}).get("session_metadata", {})
    meta["retry_count"] = 0

    # Check FAQ first
    faqs = await queries.get_faq_entries(db, tenant.tenant_id)
    faq_match = match_faq(speech_result, faqs)

    if faq_match:
        response_text = faq_match["answer"]
        tool_name = None
        tool_args = {}
    else:
        # Build system prompt and call GPT-4 with function calling
        faq_context = "\n".join(f"Q: {f['question']}\nA: {f['answer']}" for f in faqs[:20])
        system_prompt = build_system_prompt(
            tenant, memories, is_returning,
            identity_verified=meta.get("identity_verified", False),
            faq_context=faq_context,
        )
        result = await llm.chat(system_prompt, history, speech_result)
        response_text = result.text
        tool_name = result.name
        tool_args = result.args

    # Update conversation history
    history.append({"role": "user", "content": speech_result})
    history.append({"role": "assistant", "content": response_text})

    # Apply history limits: Starter=20
    if len(history) > 20:
        history = history[-20:]

    await queries.update_voice_session(
        db, call_sid, conversation_history=history, session_metadata=meta
    )

    # Handle tool calls
    settings = get_settings()

    if tool_name == "end_call":
        farewell = tool_args.get("farewell_message", response_text or "Goodbye!")
        return _twiml_response(
            f'<Response>'
            f'<Say voice="{tenant.selected_voice}">{_xml_escape(farewell)}</Say>'
            f'<Hangup/></Response>'
        )

    if tool_name == "transfer_to_human":
        hold_msg = tool_args.get("hold_message", "Let me connect you now.")
        return _build_transfer_twiml(tenant, hold_msg)

    if tool_name == "book_appointment":
        await queries.update_voice_session(
            db, call_sid,
            booking_context={"requested": True, "details": tool_args},
        )

    if tool_name == "set_memory_consent":
        consent = tool_args.get("consent", False)
        await queries.save_caller_consent(db, tenant.tenant_id, from_number, consent, "voice")

    if tool_name == "forget_caller":
        await queries.forget_caller(db, tenant.tenant_id, from_number)

    if tool_name == "save_caller_memory":
        key = tool_args.get("key", "")
        value = tool_args.get("value", "")
        if key and value:
            await queries.save_caller_memory(
                db, tenant.tenant_id, from_number, key, value,
                channel="voice", session_id=call_sid,
            )

    # If tool call returned no text, generate a follow-up
    if not response_text and tool_name:
        response_text = "Got it. Is there anything else I can help you with?"

    # Continue conversation
    return _twiml_response(
        f'<Response><Gather input="speech" timeout="5" speechTimeout="auto" '
        f'action="{settings.base_url}/voice/starter-gather">'
        f'<Say voice="{tenant.selected_voice}">{_xml_escape(response_text)}</Say>'
        f'</Gather></Response>'
    )


# ── Voicemail ──────────────────────────────────────────────────────

@router.post("/voicemail")
async def voicemail(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle voicemail recording completion."""
    form = await request.form()
    call_sid = form.get("CallSid", "")
    recording_url = form.get("RecordingUrl", "")
    tenant_id = form.get("tenant_id", "") or request.query_params.get("tenant_id", "")

    if tenant_id and call_sid:
        await queries.log_analytics_event(
            db, tenant_id, "voicemail_received", "voice",
            session_id=call_sid,
            event_data={"recording_url": recording_url},
        )

    return _twiml_response(
        '<Response><Say voice="Polly.Matthew-Neural">'
        "Thank you for your message. Goodbye."
        "</Say><Hangup/></Response>"
    )


# ── Status Callback (post-call processing) ─────────────────────────

@router.post("/status-callback")
async def status_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """Twilio calls this when a call ends. Triggers fact extraction + memory save."""
    form = await request.form()
    call_sid = form.get("CallSid", "")
    call_status = form.get("CallStatus", "")

    if not call_sid:
        return Response(status_code=200)

    session_data = await queries.get_voice_session(db, call_sid)
    if not session_data:
        logger.warning("Status callback for unknown session: %s", call_sid)
        return Response(status_code=200)

    # Close session
    await queries.update_voice_session(db, call_sid, status="closed")

    tenant_id = str(session_data["tenant_id"])
    phone = session_data["caller_phone"]
    history = session_data.get("conversation_history", [])
    if not history:
        history = []

    # Check if voicemail (no user turns)
    user_turns = sum(1 for h in history if h.get("role") == "user")
    is_voicemail = user_turns == 0

    # Build transcript with PII masking
    transcript_lines = []
    for turn in history:
        role = "Caller" if turn["role"] == "user" else "AI"
        transcript_lines.append(f"{role}: {turn['content']}")
    transcript = "\n".join(transcript_lines)
    masked_transcript = mask_pii(transcript)

    # Extract facts via GPT-4
    if not is_voicemail and transcript:
        try:
            facts = await llm.extract_facts(masked_transcript)

            # Save extracted facts as caller memory
            fact_dict = facts.model_dump(exclude_none=True)
            for key, value in fact_dict.items():
                if isinstance(value, bool):
                    value = str(value).lower()
                await queries.save_caller_memory(
                    db, tenant_id, phone, key, str(value),
                    channel="voice", session_id=call_sid,
                )

            # Upsert customer record
            customer_id = await queries.upsert_customer(
                db, tenant_id, phone,
                name=facts.name, email=facts.email,
                key_facts=fact_dict,
            )

            # Create conversation record
            await queries.create_conversation(
                db, tenant_id,
                customer_id=customer_id or session_data.get("customer_id"),
                channel="voice",
                external_id=call_sid,
                summary=masked_transcript[:500],
                intent=facts.intent,
                outcome=facts.outcome,
                sentiment=facts.sentiment,
            )

            # Analyze follow-up actions (SMS + calendar)
            tenant = await queries.get_tenant_by_id(db, str(tenant_id))
            sms_action = await llm.analyze_sms_action(masked_transcript)

            # HubSpot sync (with meeting data if calendar needed)
            meeting_data = None
            if sms_action.get("needs_calendar") and sms_action.get("has_specific_time"):
                meeting_data = sms_action

            await hubspot_sync(
                phone=phone, name=facts.name, email=facts.email,
                summary=masked_transcript[:500], session_id=call_sid,
                meeting_data=meeting_data,
            )

            # SMS follow-up (skip browser callers, check opt-out)
            if sms_action.get("needs_sms") and tenant and not phone.startswith("client:"):
                opt_out = await db.execute(
                    text("SELECT 1 FROM opt_outs WHERE phone = :phone AND tenant_id = :tid"),
                    {"phone": phone, "tid": tenant_id},
                )
                if not opt_out.first():
                    sms_body = sms_action.get("sms_body", "")

                    # If booking but no specific time, insert booking link
                    if sms_action.get("needs_calendar") and not sms_action.get("has_specific_time"):
                        booking_link = tenant.hubspot_booking_link or ""
                        if booking_link and sms_body:
                            sms_body = sms_body.replace("[booking_link]", booking_link)

                    if sms_action.get("sms_type") == "summary":
                        await send_call_summary(
                            phone, tenant.phone_number,
                            masked_transcript[:300], tenant.company_name or "",
                        )
                    elif sms_body:
                        # Cap at 320 chars
                        if len(sms_body) > 320:
                            sms_body = sms_body[:317] + "..."
                        await send_sms(phone, tenant.phone_number, sms_body)

                    await queries.log_analytics_event(
                        db, tenant_id, "sms_followup_sent", "voice",
                        phone=phone, session_id=call_sid,
                        event_data=sms_action,
                    )

            # Email follow-up if caller provided email
            if facts.email and tenant:
                try:
                    from app.services.email import send_followup_email
                    await send_followup_email(
                        to_email=facts.email,
                        caller_name=facts.name or "there",
                        summary=masked_transcript[:300],
                        company_name=tenant.company_name or "",
                    )
                except Exception:
                    logger.debug("Email follow-up skipped (email not configured)")

            # Send email confirmation SMS so caller can correct typos
            if facts.email and tenant and not phone.startswith("client:"):
                try:
                    await request_email_confirmation(
                        db=db,
                        tenant_id=str(tenant_id),
                        caller_phone=phone,
                        from_phone=tenant.phone_number,
                        captured_email=facts.email,
                        session_id=call_sid,
                        company_name=tenant.company_name or "",
                    )
                except Exception:
                    logger.exception("Email confirmation SMS failed for %s", call_sid)

        except Exception:
            logger.exception("Post-call processing failed for %s", call_sid)

    # Voicemail email notification
    if is_voicemail:
        try:
            tenant = await queries.get_tenant_by_id(db, str(tenant_id))
            if tenant and tenant.voicemail_email:
                await send_voicemail_alert(
                    to_email=tenant.voicemail_email,
                    caller_phone=phone,
                    company_name=tenant.company_name or "",
                )
        except Exception:
            logger.exception("Voicemail email failed for %s", call_sid)

    # Log call completed
    await queries.log_analytics_event(
        db, tenant_id, "call_completed", "voice",
        phone=phone, session_id=call_sid,
        event_data={
            "status": call_status,
            "is_voicemail": is_voicemail,
            "turns": len(history),
        },
    )

    return Response(status_code=200)


# ── Helper functions ───────────────────────────────────────────────

def _twiml_response(xml: str) -> Response:
    return Response(content=xml, media_type="text/xml")


def _xml_escape(text: str) -> str:
    """Escape XML special characters for TwiML."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _starter_route(
    tenant: TenantConfig, is_returning: bool, from_number: str,
    memories: list,
) -> Response:
    """Build initial TwiML for Starter tier — greeting + first Gather."""
    if is_returning:
        name_mem = next((m for m in memories if m.memory_key == "name"), None)
        caller_name = name_mem.memory_value if name_mem else None
        if caller_name and tenant.greeting_returning:
            greeting = tenant.greeting_returning.replace("{name}", caller_name)
        elif caller_name:
            greeting = f"Welcome back, {caller_name}! How can I help you today?"
        else:
            greeting = tenant.greeting_returning or "Welcome back! How can I help you today?"
    else:
        greeting = tenant.greeting_new or (
            f"Thank you for calling {tenant.company_name or 'us'}. "
            "How can I help you today?"
        )

    settings = get_settings()
    return _twiml_response(
        f'<Response><Gather input="speech" timeout="5" speechTimeout="auto" '
        f'action="{settings.base_url}/voice/starter-gather">'
        f'<Say voice="{tenant.selected_voice}">{_xml_escape(greeting)}</Say>'
        f'</Gather></Response>'
    )


def _websocket_route(
    tenant: TenantConfig, call_sid: str, caller_phone: str, is_returning: bool,
) -> Response:
    """Build TwiML for Growth/Pro tier — Connect to WebSocket media stream."""
    settings = get_settings()
    ws_url = settings.base_url.replace("https://", "wss://").replace("http://", "ws://")

    return _twiml_response(
        f'<Response>'
        f'<Connect>'
        f'<Stream url="{ws_url}/ws/media-stream/{call_sid}">'
        f'<Parameter name="tenant_id" value="{tenant.tenant_id}"/>'
        f'<Parameter name="caller_phone" value="{caller_phone}"/>'
        f'<Parameter name="is_returning" value="{str(is_returning).lower()}"/>'
        f'</Stream>'
        f'</Connect>'
        f'</Response>'
    )


def _build_transfer_twiml(tenant: TenantConfig, hold_message: str) -> Response:
    """Build TwiML for hunt group transfer with sequential dial."""
    if not tenant.hunt_group_numbers:
        return _twiml_response(
            f'<Response><Say voice="{tenant.selected_voice}">'
            "I'm sorry, no one is available to take your call right now. "
            "Please try again later.</Say><Hangup/></Response>"
        )

    dial_numbers = "".join(
        f'<Number>{n}</Number>' for n in tenant.hunt_group_numbers
    )
    return _twiml_response(
        f'<Response>'
        f'<Say voice="{tenant.selected_voice}">{_xml_escape(hold_message)}</Say>'
        f'<Dial timeout="{tenant.transfer_timeout}">'
        f'{dial_numbers}'
        f'</Dial>'
        f'<Say voice="{tenant.selected_voice}">'
        "I'm sorry, no one was available. Please try again later."
        "</Say><Hangup/></Response>"
    )
