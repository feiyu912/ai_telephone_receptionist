"""Twilio call recording configuration.

Updates the Twilio phone number's voice_record setting when the dashboard
 toggles call recording on/off.  Falls back to global Twilio credentials.
"""

from __future__ import annotations
import logging
from twilio.rest import Client
from app.config import get_settings

logger = logging.getLogger(__name__)


def _get_client(account_sid: str | None, auth_token: str | None) -> Client | None:
    settings = get_settings()
    sid = account_sid or settings.twilio_account_sid
    token = auth_token or settings.twilio_auth_token
    if not sid or not token:
        logger.warning("No Twilio credentials for recording config")
        return None
    return Client(sid, token)


def update_phone_recording(
    phone_number: str,
    enabled: bool,
    account_sid: str | None = None,
    auth_token: str | None = None,
) -> bool:
    """Enable or disable recording on a Twilio phone number.

    Returns True on success, False on failure.
    """
    client = _get_client(account_sid, auth_token)
    if client is None:
        return False

    # Normalise E.164
    e164 = phone_number if phone_number.startswith("+") else f"+{phone_number}"

    try:
        numbers = client.incoming_phone_numbers.list(phone_number=e164)
        if not numbers:
            logger.warning("Twilio phone number not found: %s", e164)
            return False

        record_mode = "record-from-answer" if enabled else "do-not-record"
        numbers[0].update(voice_record=record_mode)
        logger.info(
            "Twilio recording %s for %s",
            "enabled" if enabled else "disabled",
            e164,
        )
        return True
    except Exception:
        logger.exception("Failed to update recording setting for %s", e164)
        return False
