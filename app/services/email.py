"""Email notifications via Microsoft Graph (Outlook).

Replaces the old SMTP-based implementation. Uses the same Azure app
credentials as Outlook Calendar, with the Mail.Send permission.

Sender mailbox is configured via MS_SENDER_EMAIL.
"""

from __future__ import annotations
import logging
import httpx
from app.config import get_settings
from app.services.calendar import _get_access_token  # reuse the same auth helper

logger = logging.getLogger(__name__)

GRAPH_API = "https://graph.microsoft.com/v1.0"


async def _send_via_graph(
    sender: str,
    to_email: str,
    subject: str,
    html_body: str,
) -> bool:
    """Send an HTML email via Microsoft Graph as `sender`."""
    token = await _get_access_token()
    if not token:
        logger.info("Skipping email (Microsoft Graph not configured)")
        return False

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GRAPH_API}/users/{sender}/sendMail",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "message": {
                    "subject": subject,
                    "body": {"contentType": "HTML", "content": html_body},
                    "toRecipients": [{"emailAddress": {"address": to_email}}],
                },
                "saveToSentItems": True,
            },
            timeout=15,
        )
        if resp.status_code in (200, 202):
            logger.info("Email sent: from=%s to=%s subject=%s", sender, to_email, subject)
            return True
        logger.warning("Graph sendMail failed (%s): %s", resp.status_code, resp.text[:300])
        return False


async def send_voicemail_alert(
    to_email: str,
    caller_phone: str,
    recording_url: str | None = None,
    transcript: str | None = None,
    company_name: str = "",
) -> bool:
    """Notify the team that a voicemail was left."""
    settings = get_settings()
    sender = settings.ms_sender_email
    if not sender or not to_email:
        logger.info("Skipping voicemail email (sender or recipient missing)")
        return False

    subject = f"New Voicemail from {caller_phone} — {company_name}"
    body_parts = [
        "<h2>New Voicemail Received</h2>",
        f"<p><strong>Caller:</strong> {caller_phone}</p>",
    ]
    if recording_url:
        body_parts.append(
            f'<p><strong>Recording:</strong> <a href="{recording_url}">Listen here</a></p>'
        )
    if transcript:
        body_parts.append(f"<p><strong>Transcript:</strong> {transcript}</p>")
    body_parts.append(f"<hr><p><em>POD6 AI Voice Agent — {company_name}</em></p>")

    return await _send_via_graph(sender, to_email, subject, "".join(body_parts))


async def send_followup_email(
    to_email: str,
    caller_name: str,
    summary: str,
    company_name: str = "",
) -> bool:
    """Send post-call follow-up email to the caller."""
    settings = get_settings()
    sender = settings.ms_sender_email
    if not sender or not to_email:
        logger.info("Skipping follow-up email (sender or recipient missing)")
        return False

    subject = f"Following up on your call — {company_name}"
    body = (
        f"<p>Hi {caller_name},</p>"
        f"<p>Thank you for calling {company_name}! Here's a quick summary of our conversation:</p>"
        f"<p><em>{summary}</em></p>"
        f"<p>If you have any questions, just reply to this email or give us a call.</p>"
        f"<p>Best regards,<br>{company_name} Team</p>"
    )
    return await _send_via_graph(sender, to_email, subject, body)


async def send_booking_confirmation(
    to_email: str,
    caller_name: str,
    meeting_datetime: str,
    company_name: str = "",
    meeting_link: str = "",
) -> bool:
    """Send booking confirmation email to the caller."""
    settings = get_settings()
    sender = settings.ms_sender_email
    if not sender or not to_email:
        return False

    subject = f"Your meeting with {company_name} is confirmed"
    body_parts = [
        f"<p>Hi {caller_name},</p>",
        f"<p>Your meeting with <strong>{company_name}</strong> is confirmed for <strong>{meeting_datetime}</strong>.</p>",
    ]
    if meeting_link:
        body_parts.append(f'<p>Meeting link: <a href="{meeting_link}">{meeting_link}</a></p>')
    body_parts.append("<p>We look forward to speaking with you!</p>")
    body_parts.append(f"<p>Best regards,<br>{company_name} Team</p>")

    return await _send_via_graph(sender, to_email, subject, "".join(body_parts))
