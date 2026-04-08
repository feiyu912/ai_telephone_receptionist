"""HubSpot CRM integration — contact sync and engagement notes."""

from __future__ import annotations
import logging
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)

HUBSPOT_API = "https://api.hubapi.com"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {get_settings().hubspot_access_token}",
        "Content-Type": "application/json",
    }


async def search_contact(phone: str) -> dict | None:
    """Search HubSpot for a contact by phone number."""
    # Skip browser SDK callers
    if phone.startswith("client:"):
        return None
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{HUBSPOT_API}/crm/v3/objects/contacts/search",
            headers=_headers(),
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


async def create_contact(
    phone: str,
    name: str | None = None,
    email: str | None = None,
) -> str | None:
    """Create a HubSpot contact. Returns contact ID."""
    # Skip browser SDK callers (not real phone numbers)
    if phone.startswith("client:"):
        logger.info("Skipping HubSpot contact for browser caller: %s", phone)
        return None

    parts = (name or "").split(" ", 1)
    firstname = parts[0] if parts else ""
    lastname = parts[1] if len(parts) > 1 else ""

    properties: dict = {
        "phone": phone,
        "firstname": firstname,
        "lastname": lastname,
    }
    # Only set email if actually provided (empty string causes dedup issues)
    if email:
        properties["email"] = email

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{HUBSPOT_API}/crm/v3/objects/contacts",
            headers=_headers(),
            json={"properties": properties},
            timeout=10,
        )
        if resp.status_code == 201:
            return resp.json().get("id")
        # 409 = contact already exists (dedup by email/phone)
        if resp.status_code == 409:
            existing_id = resp.json().get("message", "")
            # Extract ID from "Contact already exists. Existing ID: 12345"
            if "Existing ID:" in existing_id:
                return existing_id.split("Existing ID:")[-1].strip()
        logger.warning("HubSpot create contact failed: %s", resp.text)
        return None


async def create_engagement_note(
    contact_id: str,
    body: str,
    subject: str = "AI Voice Call",
) -> str | None:
    """Create an engagement note on a HubSpot contact."""
    import time
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{HUBSPOT_API}/crm/v3/objects/notes",
            headers=_headers(),
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
            headers=_headers(),
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
) -> str | None:
    """Create a HubSpot meeting and associate it with a contact."""
    import time
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{HUBSPOT_API}/crm/v3/objects/meetings",
            headers=_headers(),
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
                headers=_headers(),
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
) -> dict:
    """Full HubSpot sync: find/create contact + engagement note + optional meeting.

    Args:
        meeting_data: If provided, creates a meeting. Expected keys:
            meeting_datetime (ISO 8601), meeting_duration_minutes (int),
            calendar_subject (str), calendar_notes (str), caller_name (str)

    Returns {"contact_id": str, "note_id": str, "meeting_id": str} or empty dict.
    """
    if not get_settings().hubspot_access_token:
        return {}

    try:
        contact = await search_contact(phone)
        contact_id = contact["id"] if contact else await create_contact(phone, name, email)

        if not contact_id:
            return {}

        # Create engagement note
        note_body = (
            f"<strong>AI Voice Call</strong><br>"
            f"Phone: {phone}<br>"
            f"Session: {session_id}<br><br>"
            f"{summary}"
        )
        note_id = await create_engagement_note(contact_id, note_body)

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
                meeting_id = await create_meeting(contact_id, subject, start_ms, end_ms, body)
            except Exception:
                logger.exception("Failed to create HubSpot meeting")

        return {"contact_id": contact_id, "note_id": note_id, "meeting_id": meeting_id}

    except Exception:
        logger.exception("HubSpot sync failed for %s", phone)
        return {}
