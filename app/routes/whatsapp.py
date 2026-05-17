"""WhatsApp inbound channel — Twilio webhook with compliance.

Replicates the n8n WhatsApp Channel workflow:
- Same compliance handling as SMS (STOP/HELP/START)
- Idempotency check
- GPT-4 conversation with memory
- HubSpot sync
"""

from __future__ import annotations
import logging
from fastapi import APIRouter, Request, Depends
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.client import get_db
from app.db import queries
from app.services import llm
from app.services.hubspot import sync_call as hubspot_sync
from app.services.pii import mask_pii
from app.services.twilio_validation import verify_twilio_signature
from app.prompts.system import build_system_prompt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

_processed_sids: set[str] = set()
_STOP_WORDS = {"stop", "unsubscribe", "cancel", "end", "quit"}
_HELP_WORDS = {"help", "info"}
_START_WORDS = {"start", "unstop", "subscribe"}


@router.post("/inbound", dependencies=[Depends(verify_twilio_signature)])
async def whatsapp_inbound(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle inbound WhatsApp message from Twilio."""
    form = await request.form()
    message_sid = form.get("MessageSid", "")
    from_number = form.get("From", "").replace("whatsapp:", "")
    to_number = form.get("To", "").replace("whatsapp:", "")
    body = (form.get("Body", "") or "").strip()

    # Idempotency
    if message_sid in _processed_sids:
        return _twiml_empty()
    _processed_sids.add(message_sid)
    if len(_processed_sids) > 10000:
        _processed_sids.clear()

    # Tenant resolution
    tenant = await queries.get_tenant_by_phone(db, to_number)
    if not tenant:
        logger.warning("WhatsApp to unknown number: %s", to_number)
        return _twiml_empty()

    # Compliance
    body_lower = body.lower().strip()
    if body_lower in _STOP_WORDS:
        await db.execute(
            text("""
                INSERT INTO opt_outs (tenant_id, phone, channel, opted_out_at, reason)
                VALUES (:tid, :phone, 'whatsapp', NOW(), 'STOP keyword')
                ON CONFLICT (tenant_id, phone, channel) DO NOTHING
            """),
            {"tid": tenant.tenant_id, "phone": from_number},
        )
        await db.commit()
        await queries.log_analytics_event(
            db, tenant.tenant_id, "whatsapp_opt_out", "whatsapp", phone=from_number,
        )
        return _twiml_reply("You've been unsubscribed from WhatsApp messages. Reply START to resubscribe.")

    if body_lower in _HELP_WORDS:
        return _twiml_reply(
            f"Chat with {tenant.company_name or 'us'} here. Reply STOP to opt out."
        )

    if body_lower in _START_WORDS:
        await db.execute(
            text("UPDATE opt_outs SET resubscribed_at = NOW() WHERE tenant_id = :tid AND phone = :phone AND channel = 'whatsapp'"),
            {"tid": tenant.tenant_id, "phone": from_number},
        )
        await db.commit()
        return _twiml_reply("You've been resubscribed! How can we help?")

    # Check opt-out
    opt_out = await db.execute(
        text("SELECT 1 FROM opt_outs WHERE tenant_id = :tid AND phone = :phone AND channel IN ('whatsapp', 'all')"),
        {"tid": tenant.tenant_id, "phone": from_number},
    )
    if opt_out.first():
        return _twiml_empty()

    # Load memory + conversation
    memories = await queries.lookup_caller_memory(db, tenant.tenant_id, from_number)
    is_returning = len(memories) > 0
    system_prompt = build_system_prompt(tenant, memories, is_returning)

    result = await llm.chat(system_prompt, [], body)
    response_text = result.text or "Thanks for your message!"

    # Handle tool calls
    if result.name == "save_caller_memory" and result.args.get("key"):
        await queries.save_caller_memory(
            db, tenant.tenant_id, from_number,
            result.args["key"], result.args.get("value", ""),
            channel="whatsapp", session_id=message_sid,
        )
    elif result.name == "forget_caller":
        await queries.forget_caller(db, tenant.tenant_id, from_number)
    elif result.name == "set_memory_consent":
        await queries.save_caller_consent(
            db, tenant.tenant_id, from_number,
            result.args.get("consent", False), "whatsapp",
        )

    # Save conversation
    masked_body = mask_pii(body)
    customer_id = await queries.upsert_customer(db, tenant.tenant_id, from_number)
    await queries.create_conversation(
        db, tenant.tenant_id, customer_id=customer_id,
        channel="whatsapp", external_id=message_sid,
        summary=f"Caller: {masked_body}\nAI: {mask_pii(response_text)}",
    )

    # Analytics + HubSpot (skip browser test callers)
    await queries.log_analytics_event(
        db, tenant.tenant_id, "whatsapp_inbound", "whatsapp",
        phone=from_number, session_id=message_sid,
    )
    if not from_number.startswith("client:"):
        await hubspot_sync(
            phone=from_number, summary=f"WhatsApp: {masked_body}",
            access_token=tenant.hubspot_access_token,
        )

    return _twiml_reply(response_text)


def _twiml_reply(body: str) -> Response:
    return Response(
        content=f'<Response><Message>{body}</Message></Response>',
        media_type="text/xml",
    )


def _twiml_empty() -> Response:
    return Response(content="<Response/>", media_type="text/xml")
