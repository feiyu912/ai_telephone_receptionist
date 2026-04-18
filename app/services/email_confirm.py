"""Email spelling confirmation flow via SMS.

After a call where we captured an email, send the caller an SMS asking
them to confirm or correct the spelling. Replies are handled by the
SMS inbound route.

Pending confirmations are stored in caller_memory with key
'pending_email_confirm' and value as JSON {"email": "...", "session_id": "..."}.
"""

from __future__ import annotations
import json
import logging
import re
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import queries
from app.services.sms import send_sms

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
YES_WORDS = {"yes", "y", "yep", "yeah", "yup", "correct", "confirm", "ok", "okay"}
NO_WORDS = {"no", "n", "nope", "wrong", "incorrect"}


async def request_email_confirmation(
    db: AsyncSession,
    tenant_id: str,
    caller_phone: str,
    from_phone: str,
    captured_email: str,
    session_id: str,
    company_name: str = "",
    twilio_account_sid: str | None = None,
    twilio_auth_token: str | None = None,
) -> bool:
    """Send the caller an SMS asking to confirm the captured email."""
    if not captured_email or not caller_phone or caller_phone.startswith("client:"):
        return False

    # Check opt-out
    opt_out = await db.execute(
        text(
            "SELECT 1 FROM opt_outs WHERE tenant_id = :tid AND phone = :phone "
            "AND channel IN ('sms', 'all') AND resubscribed_at IS NULL"
        ),
        {"tid": tenant_id, "phone": caller_phone},
    )
    if opt_out.first():
        logger.info("Skipping email confirm SMS (opted out): %s", caller_phone)
        return False

    # Store pending confirmation in caller_memory
    pending = json.dumps({"email": captured_email, "session_id": session_id})
    await queries.save_caller_memory(
        db, tenant_id, caller_phone,
        key="pending_email_confirm",
        value=pending,
        channel="sms",
        session_id=session_id,
    )

    msg = (
        f"Hi! This is {company_name or 'us'}. We have your email as "
        f"{captured_email}. Reply YES to confirm, or send the correct address."
    )
    if len(msg) > 320:
        msg = msg[:317] + "..."

    sid = await send_sms(
        caller_phone, from_phone, msg,
        account_sid=twilio_account_sid,
        auth_token=twilio_auth_token,
    )
    if sid:
        await queries.log_analytics_event(
            db, tenant_id, "email_confirmation_sent", "sms",
            phone=caller_phone, session_id=session_id,
            event_data={"email": captured_email},
        )
    return bool(sid)


async def handle_confirmation_reply(
    db: AsyncSession,
    tenant_id: str,
    caller_phone: str,
    body: str,
) -> str | None:
    """If the caller has a pending email confirmation, process their reply.

    Returns a reply message to send back, or None if no pending confirmation.
    """
    # Look up pending confirmation
    result = await db.execute(
        text(
            "SELECT memory_value FROM caller_memory "
            "WHERE tenant_id = :tid AND caller_phone = :phone "
            "AND memory_key = 'pending_email_confirm' "
            "AND (expires_at IS NULL OR expires_at > NOW())"
        ),
        {"tid": tenant_id, "phone": caller_phone},
    )
    row = result.first()
    if not row:
        return None

    try:
        pending = json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return None

    pending_email = pending.get("email", "")
    body_clean = body.strip().lower()
    body_first = body_clean.split()[0] if body_clean else ""

    # Case 1: caller confirmed
    if body_first in YES_WORDS:
        await _save_confirmed_email(db, tenant_id, caller_phone, pending_email)
        await _clear_pending(db, tenant_id, caller_phone)
        await queries.log_analytics_event(
            db, tenant_id, "email_confirmed", "sms",
            phone=caller_phone, event_data={"email": pending_email},
        )
        return "Thanks! Your email is confirmed."

    # Case 2: caller sent a new email address
    match = EMAIL_RE.search(body)
    if match:
        new_email = match.group(0)
        await _save_confirmed_email(db, tenant_id, caller_phone, new_email)
        await _clear_pending(db, tenant_id, caller_phone)
        await queries.log_analytics_event(
            db, tenant_id, "email_corrected", "sms",
            phone=caller_phone, event_data={"old": pending_email, "new": new_email},
        )
        return f"Got it! We've updated your email to {new_email}."

    # Case 3: explicit no
    if body_first in NO_WORDS:
        return f"Got it. Please reply with the correct email address."

    # Case 4: unclear
    return None


async def _save_confirmed_email(
    db: AsyncSession, tenant_id: str, phone: str, email: str
) -> None:
    """Save the confirmed email to caller_memory and customers tables."""
    await queries.save_caller_memory(
        db, tenant_id, phone, "email", email, channel="sms",
    )
    await db.execute(
        text(
            "UPDATE customers SET email = :email, updated_at = NOW() "
            "WHERE tenant_id = :tid AND phone = :phone"
        ),
        {"tid": tenant_id, "phone": phone, "email": email},
    )
    await db.commit()


async def _clear_pending(db: AsyncSession, tenant_id: str, phone: str) -> None:
    """Remove the pending_email_confirm entry."""
    await db.execute(
        text(
            "DELETE FROM caller_memory WHERE tenant_id = :tid "
            "AND caller_phone = :phone AND memory_key = 'pending_email_confirm'"
        ),
        {"tid": tenant_id, "phone": phone},
    )
    await db.commit()
