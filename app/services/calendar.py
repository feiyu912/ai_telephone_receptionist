"""Outlook Calendar booking via Microsoft Graph API.

Ported from the battle-tested n8n "Appointment Booking" workflow that fixed
31 bugs in March 2026. Handles natural-language dates ("next Tuesday"),
loose AM/PM time parsing, and proper timezone-aware slot checking.
"""

from __future__ import annotations
import logging
import re
from datetime import datetime, timedelta, date as date_cls
from zoneinfo import ZoneInfo
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)

GRAPH_API = "https://graph.microsoft.com/v1.0"

# Weekday name → Python weekday() number (Mon=0 ... Sun=6)
_WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}


# ── Auth ───────────────────────────────────────────────────────────

async def _get_access_token() -> str | None:
    """Client-credentials OAuth token for Microsoft Graph."""
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
        logger.error("Failed to get Graph token: %s", resp.text[:300])
        return None


# ── Date & time parsing (from n8n to24h + natural language extensions) ─

def parse_natural_date(
    text: str,
    timezone: str = "America/Chicago",
) -> str | None:
    """Parse 'next Tuesday', 'tomorrow', '2026-04-20' → 'YYYY-MM-DD'.

    Returns None if the string can't be understood.
    """
    if not text:
        return None

    s = text.strip().lower()
    tz = ZoneInfo(timezone)
    today = datetime.now(tz).date()

    # Already ISO format?
    iso_match = re.match(r"^(\d{4}-\d{2}-\d{2})", s)
    if iso_match:
        try:
            datetime.strptime(iso_match.group(1), "%Y-%m-%d")
            return iso_match.group(1)
        except ValueError:
            pass

    # Keywords
    if s in ("today",):
        return today.isoformat()
    if s in ("tomorrow",):
        return (today + timedelta(days=1)).isoformat()
    if s in ("the day after tomorrow", "day after tomorrow"):
        return (today + timedelta(days=2)).isoformat()

    # "next <weekday>" or "<weekday>"
    m = re.match(r"^(?:(next|this|coming)\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)$", s)
    if m:
        modifier, day_word = m.group(1), m.group(2)
        target = _WEEKDAYS[day_word]
        current = today.weekday()
        days_ahead = (target - current) % 7
        # "next Tuesday" → if today is Mon, next Tue is tomorrow; if today is Tue, next Tue is 7 days
        if modifier == "next":
            days_ahead = days_ahead or 7
        elif days_ahead == 0:
            # Plain "Tuesday" on Tuesday → assume next week
            days_ahead = 7
        return (today + timedelta(days=days_ahead)).isoformat()

    # "Month Day" like "April 20" / "Apr 20"
    m = re.match(
        r"^(january|february|march|april|may|june|july|august|september|october|november|december|"
        r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\s+(\d{1,2})(?:,\s*(\d{4}))?$",
        s,
    )
    if m:
        month_map = {
            "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
            "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
            "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
        }
        month = month_map[m.group(1)]
        day = int(m.group(2))
        year = int(m.group(3)) if m.group(3) else today.year
        try:
            parsed = date_cls(year, month, day)
            # If the date is in the past this year, bump to next year
            if parsed < today and not m.group(3):
                parsed = date_cls(year + 1, month, day)
            return parsed.isoformat()
        except ValueError:
            return None

    return None


def to_24h(time_str: str) -> str | None:
    """Normalize '2 PM' / '2:30 pm' / '14:00' / '2' → 'HH:MM' in 24h.

    Returns None for non-time strings ('morning', etc.).
    """
    if not time_str or not isinstance(time_str, str):
        return None
    t = time_str.strip()

    # "2 PM" / "2:30 PM"
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(AM|PM|am|pm|a\.m\.|p\.m\.)$", t)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        period = m.group(3).upper().replace(".", "")
        if period.startswith("P") and hour < 12:
            hour += 12
        if period.startswith("A") and hour == 12:
            hour = 0
        return f"{hour:02d}:{minute:02d}"

    # Bare "14:00"
    m = re.match(r"^(\d{1,2}):(\d{2})$", t)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2))
        # Assume 1-7 without AM/PM means PM (business-hours heuristic)
        if 1 <= hour <= 7:
            hour += 12
        return f"{hour:02d}:{minute:02d}"

    # Bare "2" or "14"
    m = re.match(r"^(\d{1,2})$", t)
    if m:
        hour = int(m.group(1))
        if 1 <= hour <= 7:
            hour += 12
        return f"{hour:02d}:00"

    return None


def _parse_graph_datetime(s: str, default_tz: ZoneInfo) -> datetime:
    """Parse a Microsoft Graph dateTime string into an aware datetime.

    Graph returns like '2026-04-20T14:00:00.0000000' (no timezone) — we must
    treat it as being in the schedule's timezone, NOT replace with local.
    """
    # Trim sub-second precision if present
    s = s.split(".")[0] if "." in s else s
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        # Last resort
        dt = datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=default_tz)
    return dt


# ── Availability checking ─────────────────────────────────────────

async def check_availability(
    calendar_email: str,
    date_iso: str,
    timezone: str = "America/Chicago",
    duration_minutes: int = 60,
    buffer_minutes: int = 15,
    business_hours_start: int = 9,
    business_hours_end: int = 17,
) -> list[dict]:
    """Return available time slots for a date.

    Args:
        date_iso: 'YYYY-MM-DD' (already parsed — use parse_natural_date() first).

    Returns:
        [{"start": "2026-04-20T14:00:00-05:00", "end": "...", "label": "2 PM", "hour": 14, "minute": 0}, ...]
    """
    token = await _get_access_token()
    if not token:
        logger.warning("No Graph token — calendar not configured")
        return []

    tz = ZoneInfo(timezone)
    try:
        check_date = date_cls.fromisoformat(date_iso)
    except ValueError:
        logger.error("Invalid date format: %r", date_iso)
        return []

    start_dt = datetime.combine(check_date, datetime.min.time(), tzinfo=tz).replace(hour=business_hours_start)
    end_dt = datetime.combine(check_date, datetime.min.time(), tzinfo=tz).replace(hour=business_hours_end)

    # Ask Graph for busy periods
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GRAPH_API}/users/{calendar_email}/calendar/getSchedule",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "schedules": [calendar_email],
                "startTime": {"dateTime": start_dt.isoformat(), "timeZone": timezone},
                "endTime": {"dateTime": end_dt.isoformat(), "timeZone": timezone},
                "availabilityViewInterval": 30,
            },
            timeout=10,
        )

    if resp.status_code != 200:
        logger.error("Schedule check failed: %s", resp.text[:300])
        return []

    busy: list[tuple[datetime, datetime]] = []
    for schedule in resp.json().get("value", []):
        for item in schedule.get("scheduleItems", []):
            bs = _parse_graph_datetime(item["start"]["dateTime"], tz)
            be = _parse_graph_datetime(item["end"]["dateTime"], tz)
            busy.append((bs, be))

    # Walk the business-hours window in 30-min steps
    slots: list[dict] = []
    slot_dur = timedelta(minutes=duration_minutes)
    buf = timedelta(minutes=buffer_minutes)
    step = timedelta(minutes=30)
    cursor = start_dt
    while cursor + slot_dur <= end_dt:
        slot_end = cursor + slot_dur
        is_free = all(
            slot_end + buf <= bs or cursor >= be + buf
            for bs, be in busy
        )
        if is_free:
            label_hour = cursor.hour if cursor.hour <= 12 else cursor.hour - 12
            if label_hour == 0:
                label_hour = 12
            am_pm = "AM" if cursor.hour < 12 else "PM"
            minute_part = f":{cursor.minute:02d}" if cursor.minute else ""
            slots.append({
                "start": cursor.isoformat(),
                "end": slot_end.isoformat(),
                "label": f"{label_hour}{minute_part} {am_pm}",
                "hour": cursor.hour,
                "minute": cursor.minute,
            })
        cursor += step

    return slots


# ── Event creation ─────────────────────────────────────────────────

async def create_event(
    calendar_email: str,
    subject: str,
    start_iso: str,
    end_iso: str,
    timezone: str = "America/Chicago",
    attendee_email: str | None = None,
    attendee_name: str | None = None,
    notes: str = "",
) -> dict | None:
    """Create a calendar event. `start_iso`/`end_iso` include the timezone offset."""
    token = await _get_access_token()
    if not token:
        return None

    event_body: dict = {
        "subject": subject,
        "start": {"dateTime": start_iso, "timeZone": timezone},
        "end": {"dateTime": end_iso, "timeZone": timezone},
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

    logger.error("Failed to create event: %s", resp.text[:300])
    return None


# ── High-level booking flow ────────────────────────────────────────

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
    business_hours_start: int = 9,
    business_hours_end: int = 17,
) -> dict:
    """Full booking flow: parse inputs, check availability, create event.

    Handles natural language ("next Tuesday", "2 PM") — GPT doesn't need
    to convert.

    Returns:
        On success: {"success": True, "event": {...}, "slot": "2:00 PM"}
        On conflict: {"success": False, "available_slots": [...], "message": "..."}
        On error: {"success": False, "message": "..."}
    """
    # 1. Parse the date
    date_iso = parse_natural_date(preferred_date, timezone)
    if not date_iso:
        return {
            "success": False,
            "message": f"Could not understand the date '{preferred_date}'. Ask the caller for a specific date like 'April 20' or 'next Tuesday'.",
        }

    # 2. Parse the time (may be None for vague input like "morning")
    time_24h = to_24h(preferred_time)

    # 3. Get available slots
    slots = await check_availability(
        calendar_email, date_iso, timezone,
        duration_minutes, 15,
        business_hours_start, business_hours_end,
    )
    if not slots:
        return {
            "success": False,
            "available_slots": [],
            "message": f"No available slots on {date_iso}. Suggest another day.",
        }

    # 4. Match the requested time
    matched = None
    if time_24h:
        pref_hour, pref_min = int(time_24h.split(":")[0]), int(time_24h.split(":")[1])
        # Exact match first
        matched = next(
            (s for s in slots if s["hour"] == pref_hour and s["minute"] == pref_min),
            None,
        )
        # Otherwise same hour within 30 min
        if not matched:
            matched = next(
                (s for s in slots if s["hour"] == pref_hour and abs(s["minute"] - pref_min) <= 30),
                None,
            )

    if not matched:
        # Suggest up to 4 spaced-out alternatives
        if len(slots) > 4:
            interval = len(slots) // 4
            picks = [slots[0], slots[interval], slots[interval * 2], slots[-1]]
        else:
            picks = slots
        labels = ", ".join(s["label"] for s in picks)
        return {
            "success": False,
            "available_slots": picks,
            "message": (
                f"The time {preferred_time} is not available on {date_iso}. "
                f"Available: {labels}. Ask the caller which works."
            ),
        }

    # 5. Create the event (start/end already include timezone offset)
    event = await create_event(
        calendar_email=calendar_email,
        subject=f"Appointment — {caller_name or caller_phone} — {purpose}",
        start_iso=matched["start"],
        end_iso=matched["end"],
        timezone=timezone,
        attendee_email=caller_email,
        attendee_name=caller_name,
        notes=(
            f"Booked via AI Telephone Receptionist\n"
            f"Phone: {caller_phone}\n"
            f"Purpose: {purpose}"
        ),
    )

    if not event:
        return {"success": False, "message": "Could not create calendar event. Please try again."}

    return {
        "success": True,
        "event": event,
        "slot": matched["label"],
        "date": date_iso,
    }
