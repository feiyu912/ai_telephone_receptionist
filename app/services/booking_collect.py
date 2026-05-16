"""Booking info collection via SMS.

When a caller wants to book an appointment during a call but doesn't
provide their name or email, we send an SMS asking for the missing info.
Replies are handled by the SMS inbound route.

Pending booking states are stored in caller_memory with key
'pending_booking_info' and value as JSON.
"""

from __future__ import annotations
import json
import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import queries
from app.services.sms import send_sms
from app.services.calendar import book_appointment
from app.services.hubspot import sync_call as hubspot_sync
from app.services.llm import _get_client

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


async def request_booking_info(
    db: AsyncSession,
    tenant_id: str,
    caller_phone: str,
    from_phone: str,
    missing_fields: list[str],
    proposed_date: str,
    proposed_time: str,
    purpose: str,
    duration_minutes: int,
    session_id: str,
    company_name: str = "",
    twilio_account_sid: str | None = None,
    twilio_auth_token: str | None = None,
) -> bool:
    """Send the caller an SMS asking for missing booking info."""
    if not caller_phone or caller_phone.startswith("client:"):
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
        logger.info("Skipping booking info SMS (opted out): %s", caller_phone)
        return False

    # Build human-readable missing fields text
    field_labels = []
    if "name" in missing_fields:
        field_labels.append("name")
    if "email" in missing_fields:
        field_labels.append("email address")
    if len(field_labels) == 2:
        missing_text = "name and email address"
    else:
        missing_text = field_labels[0] if field_labels else "information"

    # Store pending booking info in caller_memory
    pending = json.dumps({
        "session_id": session_id,
        "missing_fields": missing_fields,
        "proposed_date": proposed_date,
        "proposed_time": proposed_time,
        "purpose": purpose,
        "duration_minutes": duration_minutes,
        "collected_name": "",
        "collected_email": "",
        "status": "pending",
    })
    await queries.save_caller_memory(
        db, tenant_id, caller_phone,
        key="pending_booking_info",
        value=pending,
        channel="sms",
        session_id=session_id,
    )

    # Format date/time for SMS
    date_label = _friendly_date(proposed_date)
    time_label = proposed_time
    msg = (
        f"Hi! This is {company_name or 'us'}. We have your appointment request "
        f"for {date_label} at {time_label}. To confirm your booking, please reply "
        f"with your {missing_text}."
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
            db, tenant_id, "booking_info_requested", "sms",
            phone=caller_phone, session_id=session_id,
            event_data={"missing_fields": missing_fields},
        )
    return bool(sid)


async def handle_booking_info_reply(
    db: AsyncSession,
    tenant_id: str,
    caller_phone: str,
    body: str,
) -> str | None:
    """If the caller has a pending booking info request, process their reply.

    Returns a reply message to send back, or None if no pending booking.
    """
    # Look up pending booking info
    result = await db.execute(
        text(
            "SELECT memory_value FROM caller_memory "
            "WHERE tenant_id = :tid AND caller_phone = :phone "
            "AND memory_key = 'pending_booking_info' "
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

    missing_fields = pending.get("missing_fields", [])
    if not missing_fields:
        await _clear_pending(db, tenant_id, caller_phone)
        return None

    # Parse name and email from the reply
    parsed = await _parse_booking_reply(body)
    collected_name = pending.get("collected_name", "")
    collected_email = pending.get("collected_email", "")

    if parsed.get("name"):
        collected_name = parsed["name"]
    if parsed.get("email"):
        collected_email = parsed["email"]

    # Update pending state
    still_missing = []
    if "name" in missing_fields and not collected_name:
        still_missing.append("name")
    if "email" in missing_fields and not collected_email:
        still_missing.append("email")

    if still_missing:
        pending["missing_fields"] = still_missing
        pending["collected_name"] = collected_name
        pending["collected_email"] = collected_email
        await queries.save_caller_memory(
            db, tenant_id, caller_phone,
            key="pending_booking_info",
            value=json.dumps(pending),
            channel="sms",
            session_id=pending.get("session_id", ""),
        )
        field_labels = []
        if "name" in still_missing:
            field_labels.append("name")
        if "email" in still_missing:
            field_labels.append("email address")
        if len(field_labels) == 2:
            missing_text = "name and email address"
        else:
            missing_text = field_labels[0]
        return f"Thanks! We still need your {missing_text}. Please reply with the missing info."

    # All info collected — create the booking
    pending["collected_name"] = collected_name
    pending["collected_email"] = collected_email
    pending["missing_fields"] = []

    # Get tenant config for calendar details
    tenant = await queries.get_tenant_by_id(db, tenant_id)
    if not tenant:
        await _clear_pending(db, tenant_id, caller_phone)
        return "Sorry, we couldn't find your account. Please call us to book."

    calendar_email = tenant.calendar_email or tenant.sender_email
    if not calendar_email:
        await _clear_pending(db, tenant_id, caller_phone)
        return "Sorry, our calendar isn't set up yet. Please call us to confirm."

    # Create the calendar event
    booking_result = await book_appointment(
        calendar_email=calendar_email,
        caller_phone=caller_phone,
        caller_name=collected_name,
        caller_email=collected_email,
        preferred_date=pending.get("proposed_date", ""),
        preferred_time=pending.get("proposed_time", ""),
        purpose=pending.get("purpose", "Consultation"),
        timezone=tenant.business_hours_timezone or "America/Chicago",
        duration_minutes=pending.get("duration_minutes", tenant.booking_duration_minutes or 60),
        business_hours_start=tenant.business_hours_start or 9,
        business_hours_end=tenant.business_hours_end or 17,
        tenant_id=tenant_id,
    )

    if not booking_result.get("success"):
        logger.error("Failed to create booking from SMS: %s", booking_result)
        # Don't clear pending — let them try again or call in
        return (
            "Sorry, we couldn't find an available slot. "
            "Please reply with a different time or call us to book."
        )

    # Also sync to HubSpot if configured
    try:
        meeting_data = {
            "meeting_datetime": pending.get("proposed_date", "") + "T" + pending.get("proposed_time", "") + ":00",
            "meeting_duration_minutes": pending.get("duration_minutes", 30),
            "calendar_subject": pending.get("purpose", "Consultation"),
            "calendar_notes": f"Booked via SMS follow-up after voice call.",
            "caller_name": collected_name,
        }
        await hubspot_sync(
            phone=caller_phone,
            name=collected_name,
            email=collected_email,
            summary="Booking completed via SMS follow-up",
            session_id=pending.get("session_id", ""),
            meeting_data=meeting_data,
            access_token=tenant.hubspot_access_token,
        )
    except Exception:
        logger.exception("HubSpot sync failed for booking collection %s", caller_phone)

    # Save the collected info to customer record
    await queries.upsert_customer(
        db, tenant_id, caller_phone,
        name=collected_name, email=collected_email,
    )
    for key, value in [("name", collected_name), ("email", collected_email)]:
        if value:
            await queries.save_caller_memory(
                db, tenant_id, caller_phone,
                key=key, value=value,
                channel="sms",
                session_id=pending.get("session_id", ""),
            )

    await _clear_pending(db, tenant_id, caller_phone)
    await queries.log_analytics_event(
        db, tenant_id, "booking_completed_via_sms", "sms",
        phone=caller_phone,
        session_id=pending.get("session_id", ""),
        event_data={
            "name": collected_name,
            "email": collected_email,
            "date": pending.get("proposed_date"),
            "time": pending.get("proposed_time"),
        },
    )

    slot = booking_result.get("slot", pending.get("proposed_time", ""))
    date_label = _friendly_date(pending.get("proposed_date", ""))
    return f"Thanks {collected_name}! Your appointment for {date_label} at {slot} is confirmed. See you then!"


async def _parse_booking_reply(body: str) -> dict:
    """Use GPT to extract name and email from an SMS reply."""
    if not body:
        return {}

    # Fast-path: regex for email
    email_match = EMAIL_RE.search(body)
    email = email_match.group(0) if email_match else None

    client = _get_client()
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract the person's name and email from this SMS reply. "
                        "Return ONLY valid JSON: {\"name\": \"...\", \"email\": \"...\"}. "
                        "If a field is missing, use null."
                    ),
                },
                {"role": "user", "content": body},
            ],
            max_tokens=100,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)
    except Exception:
        logger.exception("Failed to parse booking reply")
        data = {}

    # Override with regex email if GPT missed it
    if email and not data.get("email"):
        data["email"] = email

    return {
        "name": data.get("name") or None,
        "email": data.get("email") or None,
    }


async def _clear_pending(db: AsyncSession, tenant_id: str, phone: str) -> None:
    """Remove the pending_booking_info entry."""
    await db.execute(
        text(
            "DELETE FROM caller_memory WHERE tenant_id = :tid "
            "AND caller_phone = :phone AND memory_key = 'pending_booking_info'"
        ),
        {"tid": tenant_id, "phone": phone},
    )
    await db.commit()


def _friendly_date(date_str: str) -> str:
    """Convert ISO date or natural language to a human-friendly label."""
    if not date_str:
        return "the requested date"
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        today = datetime.now(ZoneInfo("America/Chicago")).date()
        delta = (dt.date() - today).days
        if delta == 0:
            return "today"
        if delta == 1:
            return "tomorrow"
        return dt.strftime("%A, %B %d")
    except ValueError:
        return date_str
