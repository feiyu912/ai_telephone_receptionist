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
    parts = (name or "").split(" ", 1)
    firstname = parts[0] if parts else ""
    lastname = parts[1] if len(parts) > 1 else ""

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{HUBSPOT_API}/crm/v3/objects/contacts",
            headers=_headers(),
            json={
                "properties": {
                    "phone": phone,
                    "firstname": firstname,
                    "lastname": lastname,
                    "email": email or "",
                }
            },
            timeout=10,
        )
        if resp.status_code == 201:
            return resp.json().get("id")
        logger.warning("HubSpot create contact failed: %s", resp.text)
        return None


async def create_engagement_note(
    contact_id: str,
    body: str,
    subject: str = "AI Voice Call",
) -> str | None:
    """Create an engagement note on a HubSpot contact."""
    async with httpx.AsyncClient() as client:
        # Create the note
        resp = await client.post(
            f"{HUBSPOT_API}/crm/v3/objects/notes",
            headers=_headers(),
            json={
                "properties": {
                    "hs_note_body": body,
                    "hs_timestamp": "",
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


async def sync_call(
    phone: str,
    name: str | None = None,
    email: str | None = None,
    summary: str = "",
    session_id: str = "",
) -> dict:
    """Full HubSpot sync: find/create contact + create engagement note.

    Returns {"contact_id": str, "note_id": str} or empty dict on failure.
    """
    if not get_settings().hubspot_access_token:
        return {}

    try:
        # Search for existing contact
        contact = await search_contact(phone)
        if contact:
            contact_id = contact["id"]
        else:
            contact_id = await create_contact(phone, name, email)

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

        return {"contact_id": contact_id, "note_id": note_id}

    except Exception:
        logger.exception("HubSpot sync failed for %s", phone)
        return {}
