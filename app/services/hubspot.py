"""HubSpot CRM integration — contact sync and engagement notes.

Per-tenant access tokens are optional. Pass `access_token` to write to a
tenant's own HubSpot portal; omit it to fall back to the global
HUBSPOT_ACCESS_TOKEN env var.
"""

from __future__ import annotations
import logging
import re
import time
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)

HUBSPOT_API = "https://api.hubapi.com"


def _headers(access_token: str | None = None) -> dict:
    token = access_token or get_settings().hubspot_access_token
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


async def search_contact(phone: str, access_token: str | None = None) -> dict | None:
    """Search HubSpot for a contact by phone number."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{HUBSPOT_API}/crm/v3/objects/contacts/search",
            headers=_headers(access_token),
            json={
                "filterGroups": [{
                    "filters": [{
                        "propertyName": "phone",
                        "operator": "EQ",
                        "value": phone,
                    }]
                }],
                "properties": ["firstname", "lastname", "email", "phone"],
            },
            timeout=10,
        )
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            return results[0] if results else None
        logger.warning("HubSpot search failed: %s", resp.text)
        return None


_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def _is_valid_email(email: str | None) -> bool:
    if not email:
        return False
    return bool(_EMAIL_RE.match(email))


async def create_contact(
    phone: str,
    name: str | None = None,
    email: str | None = None,
    access_token: str | None = None,
) -> str | None:
    """Create a HubSpot contact. Returns contact ID."""
    parts = (name or "").split(" ", 1)
    firstname = parts[0] if parts else ""
    lastname = parts[1] if len(parts) > 1 else ""

    properties: dict = {
        "phone": phone,
        "firstname": firstname,
        "lastname": lastname,
    }
    # Only set email if it looks valid
    if _is_valid_email(email):
        properties["email"] = email

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{HUBSPOT_API}/crm/v3/objects/contacts",
            headers=_headers(access_token),
            json={"properties": properties},
            timeout=10,
        )
        if resp.status_code == 201:
            return resp.json().get("id")
        # 409 = contact already exists (dedup by email/phone)
        if resp.status_code == 409:
            existing_id = resp.json().get("message", "")
            if "Existing ID:" in existing_id:
                return existing_id.split("Existing ID:")[-1].strip()
        # 400 with email validation error — retry without email
        if resp.status_code == 400 and "INVALID_EMAIL" in resp.text and "email" in properties:
            logger.info("Retrying HubSpot contact creation without invalid email: %s", email)
            del properties["email"]
            resp2 = await client.post(
                f"{HUBSPOT_API}/crm/v3/objects/contacts",
                headers=_headers(access_token),
                json={"properties": properties},
                timeout=10,
            )
            if resp2.status_code == 201:
                return resp2.json().get("id")
            if resp2.status_code == 409:
                existing_id = resp2.json().get("message", "")
                if "Existing ID:" in existing_id:
                    return existing_id.split("Existing ID:")[-1].strip()
            logger.warning("HubSpot retry failed: %s", resp2.text)
            return None
        logger.warning("HubSpot create contact failed: %s", resp.text)
        return None


async def create_engagement_note(
    contact_id: str,
    body: str,
    subject: str = "AI Voice Call",
    access_token: str | None = None,
) -> str | None:
    """Create an engagement note on a HubSpot contact."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{HUBSPOT_API}/crm/v3/objects/notes",
            headers=_headers(access_token),
            json={
                "properties": {
                    "hs_note_body": body,
                    "hs_timestamp": str(int(time.time() * 1000)),
                }
            },
            timeout=10,
        )
        if resp.status_code != 201:
            logger.warning("HubSpot create note failed: %s", resp.text)
            return None

        note_id = resp.json().get("id")

        # Associate note with contact
        await client.put(
            f"{HUBSPOT_API}/crm/v4/objects/notes/{note_id}/associations/contacts/{contact_id}",
            headers=_headers(access_token),
            json=[{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}],
            timeout=10,
        )
        return note_id


async def create_meeting(
    contact_id: str,
    title: str,
    start_ms: int,
    end_ms: int,
    body: str = "",
    access_token: str | None = None,
) -> str | None:
    """Create a HubSpot meeting and associate it with a contact."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{HUBSPOT_API}/crm/v3/objects/meetings",
            headers=_headers(access_token),
            json={
                "properties": {
                    "hs_meeting_title": title,
                    "hs_meeting_body": body,
                    "hs_meeting_start_time": str(start_ms),
                    "hs_meeting_end_time": str(end_ms),
                    "hs_meeting_outcome": "SCHEDULED",
                    "hs_timestamp": str(int(time.time() * 1000)),
                }
            },
            timeout=10,
        )
        if resp.status_code != 201:
            logger.warning("HubSpot create meeting failed: %s", resp.text)
            return None

        meeting_id = resp.json().get("id")

        # Associate meeting with contact
        if meeting_id and contact_id:
            await client.put(
                f"{HUBSPOT_API}/crm/v4/objects/meetings/{meeting_id}/associations/contacts/{contact_id}",
                headers=_headers(access_token),
                json=[{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 200}],
                timeout=10,
            )

        logger.info("HubSpot meeting created: %s for contact %s", meeting_id, contact_id)
        return meeting_id


async def sync_call(
    phone: str,
    name: str | None = None,
    email: str | None = None,
    summary: str = "",
    session_id: str = "",
    meeting_data: dict | None = None,
    access_token: str | None = None,
) -> dict:
    """Full HubSpot sync: find/create contact + engagement note + optional meeting.

    Args:
        meeting_data: If provided, creates a meeting. Expected keys:
            meeting_datetime (ISO 8601), meeting_duration_minutes (int),
            calendar_subject (str), calendar_notes (str), caller_name (str)
        access_token: Per-tenant HubSpot token; falls back to the global env var.

    Returns {"contact_id": str, "note_id": str, "meeting_id": str} or empty dict.
    """
    token = access_token or get_settings().hubspot_access_token
    if not token:
        return {}

    try:
        contact = await search_contact(phone, token)
        contact_id = (
            contact["id"] if contact else await create_contact(phone, name, email, token)
        )

        if not contact_id:
            return {}

        # Create engagement note
        note_body = (
            f"<strong>AI Voice Call</strong><br>"
            f"Phone: {phone}<br>"
            f"Session: {session_id}<br><br>"
            f"{summary}"
        )
        note_id = await create_engagement_note(contact_id, note_body, access_token=token)

        # Create meeting if requested
        meeting_id = None
        if meeting_data and meeting_data.get("meeting_datetime"):
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(meeting_data["meeting_datetime"])
                start_ms = int(dt.timestamp() * 1000)
                duration = meeting_data.get("meeting_duration_minutes", 30)
                end_ms = start_ms + (duration * 60 * 1000)
                caller = meeting_data.get("caller_name", name or "Caller")
                subject = meeting_data.get("calendar_subject", f"Consultation with {caller}")
                notes = meeting_data.get("calendar_notes", "")

                body = (
                    f"Auto-scheduled Meeting\n\n"
                    f"Subject: {subject}\n"
                    f"Notes: {notes}\n"
                    f"Caller: {caller} ({phone})\n"
                    f"Session: {session_id}"
                )
                meeting_id = await create_meeting(
                    contact_id, subject, start_ms, end_ms, body, access_token=token
                )
            except Exception:
                logger.exception("Failed to create HubSpot meeting")

        return {"contact_id": contact_id, "note_id": note_id, "meeting_id": meeting_id}

    except Exception:
        logger.exception("HubSpot sync failed for %s", phone)
        return {}
