"""SMS inbound channel — Twilio webhook with TCPA compliance.

Replicates the n8n SMS Channel workflow:
- TCPA compliance (STOP/HELP/START)
- Idempotency check (prevent duplicate processing)
- Opt-out enforcement before any reply
- GPT-4 conversation brain
- Memory save + HubSpot sync
"""

from __future__ import annotations
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Request, Depends
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.client import get_db
from app.db import queries
from app.services import llm
from app.services.hubspot import sync_call as hubspot_sync
from app.services.pii import mask_pii
from app.prompts.system import build_system_prompt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sms", tags=["sms"])

# Track processed message SIDs for idempotency
_processed_sids: set[str] = set()

# TCPA compliance keywords
_STOP_WORDS = {"stop", "unsubscribe", "cancel", "end", "quit"}
_HELP_WORDS = {"help", "info"}
_START_WORDS = {"start", "unstop", "subscribe"}

# SMS response max length (SMS segment = 160 chars, 2 segments = 320)
SMS_MAX_LENGTH = 320


def _is_quiet_hours(timezone: str = "America/Chicago") -> bool:
    """Check if current time is in quiet hours (9pm-8am or weekends)."""
    now = datetime.now(ZoneInfo(timezone))
    if now.isoweekday() in (6, 7):  # Saturday, Sunday
        return True
    return now.hour >= 21 or now.hour < 8


@router.post("/inbound")
async def sms_inbound(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle inbound SMS from Twilio."""
    form = await request.form()
    message_sid = form.get("MessageSid", "")
    from_number = form.get("From", "")
    to_number = form.get("To", "")
    body = (form.get("Body", "") or "").strip()

    # Idempotency check
    if message_sid in _processed_sids:
        return _twiml_empty()
    _processed_sids.add(message_sid)
    # Keep set bounded
    if len(_processed_sids) > 10000:
        _processed_sids.clear()

    # Tenant resolution
    tenant = await queries.get_tenant_by_phone(db, to_number)
    if not tenant:
        logger.warning("SMS to unknown number: %s", to_number)
        return _twiml_empty()

    # TCPA quiet hours check (9pm-8am, no weekends)
    if _is_quiet_hours(tenant.business_hours_timezone):
        logger.info("SMS blocked by quiet hours: %s", from_number)
        return _twiml_empty()

    # TCPA compliance check (keyword matching — also catches "stop please" etc.)
    body_lower = body.lower().strip()
    body_first_word = body_lower.split()[0] if body_lower else ""
    if body_first_word in _STOP_WORDS or body_lower in _STOP_WORDS:
        await _handle_opt_out(db, tenant.tenant_id, from_number)
        return _twiml_reply("You've been unsubscribed. Reply START to resubscribe.")

    if body_lower in _HELP_WORDS:
        return _twiml_reply(
            f"Reply to chat with {tenant.company_name or 'us'}. "
            f"Reply STOP to opt out."
        )

    if body_lower in _START_WORDS:
        await _handle_opt_in(db, tenant.tenant_id, from_number)
        return _twiml_reply("You've been resubscribed! How can we help?")

    # Check opt-out before responding
    opt_out = await db.execute(
        text("SELECT 1 FROM opt_outs WHERE tenant_id = :tid AND phone = :phone AND channel IN ('sms', 'all')"),
        {"tid": tenant.tenant_id, "phone": from_number},
    )
    if opt_out.first():
        logger.info("SMS from opted-out number: %s", from_number)
        return _twiml_empty()

    # Load caller memory
    memories = await queries.lookup_caller_memory(db, tenant.tenant_id, from_number)
    is_returning = len(memories) > 0

    # Build system prompt and call GPT-4
    system_prompt = build_system_prompt(tenant, memories, is_returning)
    # Load recent SMS conversation history from DB
    history = await _get_sms_history(db, tenant.tenant_id, from_number)

    result = await llm.chat(system_prompt, history, body)
    response_text = result.text or "Thanks for your message! How can I help?"

    # Handle tool calls from GPT-4
    if result.name == "save_caller_memory" and result.args.get("key"):
        await queries.save_caller_memory(
            db, tenant.tenant_id, from_number,
            result.args["key"], result.args.get("value", ""),
            channel="sms", session_id=message_sid,
        )
    elif result.name == "forget_caller":
        await queries.forget_caller(db, tenant.tenant_id, from_number)
    elif result.name == "set_memory_consent":
        await queries.save_caller_consent(
            db, tenant.tenant_id, from_number,
            result.args.get("consent", False), "sms",
        )

    # Save conversation to DB
    masked_body = mask_pii(body)
    masked_response = mask_pii(response_text)
    customer_id = await queries.upsert_customer(db, tenant.tenant_id, from_number)
    await queries.create_conversation(
        db, tenant.tenant_id, customer_id=customer_id,
        channel="sms", external_id=message_sid,
        summary=f"Caller: {masked_body}\nAI: {masked_response}",
    )

    # Log analytics
    await queries.log_analytics_event(
        db, tenant.tenant_id, "sms_inbound", "sms",
        phone=from_number, session_id=message_sid,
    )

    # HubSpot sync (background)
    await hubspot_sync(phone=from_number, summary=f"SMS: {masked_body}")

    # Cap SMS length to 320 chars (2 SMS segments)
    if len(response_text) > SMS_MAX_LENGTH:
        response_text = response_text[:SMS_MAX_LENGTH - 3] + "..."

    return _twiml_reply(response_text)


# ── Helpers ────────────────────────────────────────────────────────

async def _get_sms_history(db: AsyncSession, tenant_id: str, phone: str) -> list[dict]:
    """Load recent SMS conversation summary for context."""
    result = await db.execute(
        text("""
            SELECT summary FROM conversations
            WHERE tenant_id = :tid AND channel = 'sms'
              AND customer_id IN (
                SELECT customer_id FROM customers WHERE tenant_id = :tid AND phone = :phone
              )
            ORDER BY created_at DESC LIMIT 5
        """),
        {"tid": tenant_id, "phone": phone},
    )
    history = []
    for r in result.mappings().all():
        summary = r.get("summary", "")
        if summary:
            # Parse "Caller: ...\nAI: ..." format back into messages
            for line in summary.split("\n"):
                if line.startswith("Caller: "):
                    history.append({"role": "user", "content": line[8:]})
                elif line.startswith("AI: "):
                    history.append({"role": "assistant", "content": line[4:]})
    return history[-20:]


async def _handle_opt_out(db: AsyncSession, tenant_id: str, phone: str):
    """Process STOP: insert opt-out record + log."""
    await db.execute(
        text("""
            INSERT INTO opt_outs (tenant_id, phone, channel, opted_out_at, reason)
            VALUES (:tid, :phone, 'sms', NOW(), 'STOP keyword')
            ON CONFLICT (tenant_id, phone, channel) DO NOTHING
        """),
        {"tid": tenant_id, "phone": phone},
    )
    await db.commit()
    await queries.log_analytics_event(
        db, tenant_id, "sms_opt_out", "sms", phone=phone,
    )


async def _handle_opt_in(db: AsyncSession, tenant_id: str, phone: str):
    """Process START: remove opt-out record."""
    await db.execute(
        text("""
            UPDATE opt_outs SET resubscribed_at = NOW()
            WHERE tenant_id = :tid AND phone = :phone AND channel = 'sms'
        """),
        {"tid": tenant_id, "phone": phone},
    )
    await db.commit()
    await queries.log_analytics_event(
        db, tenant_id, "sms_opt_in", "sms", phone=phone,
    )


def _twiml_reply(body: str) -> Response:
    xml = f'<Response><Message>{body}</Message></Response>'
    return Response(content=xml, media_type="text/xml")


def _twiml_empty() -> Response:
    return Response(content="<Response/>", media_type="text/xml")
