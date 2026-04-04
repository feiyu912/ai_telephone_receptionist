"""Outlook Calendar booking via Microsoft Graph API.

Handles availability checking and event creation for appointment booking.
Uses OAuth2 client credentials flow for server-to-server access.
"""

from __future__ import annotations
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)

GRAPH_API = "https://graph.microsoft.com/v1.0"


async def _get_access_token() -> str | None:
    """Get Microsoft Graph access token using client credentials."""
    settings = get_settings()
    if not settings.ms_tenant_id or not settings.ms_client_id:
        return None

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://login.microsoftonline.com/{settings.ms_tenant_id}/oauth2/v2.0/token",
            data={
                "client_id": settings.ms_client_id,
                "client_secret": settings.ms_client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("access_token")
        logger.error("Failed to get Graph token: %s", resp.text)
        return None


async def check_availability(
    calendar_email: str,
    date: str,
    timezone: str = "America/Chicago",
    duration_minutes: int = 60,
    buffer_minutes: int = 15,
    business_hours_start: int = 9,
    business_hours_end: int = 17,
) -> list[dict]:
    """Check calendar availability and return available time slots.

    Args:
        calendar_email: The Outlook calendar owner's email.
        date: The date to check (e.g. "2026-04-10").
        timezone: Timezone for business hours.
        duration_minutes: Meeting duration.
        buffer_minutes: Buffer between meetings.
        business_hours_start: Start hour (24h).
        business_hours_end: End hour (24h).

    Returns:
        List of available slots: [{"start": "09:00", "end": "10:00"}, ...]
    """
    token = await _get_access_token()
    if not token:
        logger.warning("No Graph token — calendar not configured")
        return []

    tz = ZoneInfo(timezone)
    try:
        check_date = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=tz)
    except ValueError:
        logger.error("Invalid date format: %s", date)
        return []

    start_dt = check_date.replace(hour=business_hours_start, minute=0)
    end_dt = check_date.replace(hour=business_hours_end, minute=0)

    # Get busy times from Outlook
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GRAPH_API}/users/{calendar_email}/calendar/getSchedule",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "schedules": [calendar_email],
                "startTime": {"dateTime": start_dt.isoformat(), "timeZone": timezone},
                "endTime": {"dateTime": end_dt.isoformat(), "timeZone": timezone},
                "availabilityViewInterval": duration_minutes,
            },
            timeout=10,
        )

    if resp.status_code != 200:
        logger.error("Schedule check failed: %s", resp.text)
        return []

    # Parse busy times
    busy_times = []
    for schedule in resp.json().get("value", []):
        for item in schedule.get("scheduleItems", []):
            busy_start = datetime.fromisoformat(item["start"]["dateTime"]).replace(tzinfo=tz)
            busy_end = datetime.fromisoformat(item["end"]["dateTime"]).replace(tzinfo=tz)
            busy_times.append((busy_start, busy_end))

    # Build available slots
    slots = []
    current = start_dt
    while current + timedelta(minutes=duration_minutes) <= end_dt:
        slot_end = current + timedelta(minutes=duration_minutes)
        is_free = all(
            slot_end + timedelta(minutes=buffer_minutes) <= bs or current >= be + timedelta(minutes=buffer_minutes)
            for bs, be in busy_times
        )
        if is_free:
            slots.append({
                "start": current.strftime("%H:%M"),
                "end": slot_end.strftime("%H:%M"),
            })
        current += timedelta(minutes=30)  # 30-min intervals

    return slots


async def create_event(
    calendar_email: str,
    subject: str,
    start_time: str,
    end_time: str,
    timezone: str = "America/Chicago",
    attendee_email: str | None = None,
    attendee_name: str | None = None,
    notes: str = "",
) -> dict | None:
    """Create a calendar event in Outlook.

    Args:
        calendar_email: The calendar owner's email.
        subject: Event title.
        start_time: ISO format datetime string.
        end_time: ISO format datetime string.
        timezone: Timezone.
        attendee_email: Optional attendee email.
        attendee_name: Optional attendee name.
        notes: Optional notes/description.

    Returns:
        Event data dict with id and webLink, or None on failure.
    """
    token = await _get_access_token()
    if not token:
        return None

    event_body = {
        "subject": subject,
        "start": {"dateTime": start_time, "timeZone": timezone},
        "end": {"dateTime": end_time, "timeZone": timezone},
        "body": {"contentType": "text", "content": notes},
    }

    if attendee_email:
        event_body["attendees"] = [{
            "emailAddress": {"address": attendee_email, "name": attendee_name or ""},
            "type": "required",
        }]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GRAPH_API}/users/{calendar_email}/events",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=event_body,
            timeout=10,
        )

    if resp.status_code == 201:
        data = resp.json()
        logger.info("Calendar event created: %s", data.get("id"))
        return {"id": data.get("id"), "webLink": data.get("webLink")}

    logger.error("Failed to create event: %s", resp.text)
    return None


async def book_appointment(
    calendar_email: str,
    caller_phone: str,
    caller_name: str | None,
    caller_email: str | None,
    preferred_date: str,
    preferred_time: str,
    purpose: str = "Consultation",
    timezone: str = "America/Chicago",
    duration_minutes: int = 60,
) -> dict:
    """Full booking flow: check availability, create event, return result.

    Returns:
        {"success": True, "event": {...}, "slot": "10:00-11:00"} or
        {"success": False, "available_slots": [...], "message": "..."}
    """
    # Check availability
    slots = await check_availability(calendar_email, preferred_date, timezone, duration_minutes)

    if not slots:
        return {
            "success": False,
            "available_slots": [],
            "message": f"No available slots on {preferred_date}.",
        }

    # Try to match preferred time
    matched_slot = None
    for slot in slots:
        if preferred_time.lower() in slot["start"].lower() or slot["start"].startswith(preferred_time[:2]):
            matched_slot = slot
            break

    if not matched_slot:
        return {
            "success": False,
            "available_slots": slots[:5],
            "message": f"The requested time {preferred_time} is not available. Here are available slots.",
        }

    # Create the event
    start_dt = f"{preferred_date}T{matched_slot['start']}:00"
    end_dt = f"{preferred_date}T{matched_slot['end']}:00"

    event = await create_event(
        calendar_email=calendar_email,
        subject=f"Appointment — {caller_name or caller_phone} — {purpose}",
        start_time=start_dt,
        end_time=end_dt,
        timezone=timezone,
        attendee_email=caller_email,
        attendee_name=caller_name,
        notes=f"Booked via AI Voice Agent\nPhone: {caller_phone}\nPurpose: {purpose}",
    )

    if event:
        return {
            "success": True,
            "event": event,
            "slot": f"{matched_slot['start']}-{matched_slot['end']}",
        }

    return {"success": False, "message": "Failed to create calendar event."}
