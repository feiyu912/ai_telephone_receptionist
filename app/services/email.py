"""Email notifications via SMTP (voicemail alerts, follow-ups).

Uses simple SMTP instead of Microsoft Graph for Phase 1.
Outlook/Graph integration planned for Phase 2 booking.
"""

from __future__ import annotations
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import get_settings

logger = logging.getLogger(__name__)


async def send_voicemail_alert(
    to_email: str,
    caller_phone: str,
    recording_url: str | None = None,
    transcript: str | None = None,
    company_name: str = "",
) -> bool:
    """Send voicemail notification email. Returns True on success."""
    settings = get_settings()
    if not settings.smtp_host or not to_email:
        logger.info("Skipping voicemail email (SMTP not configured or no recipient)")
        return False

    subject = f"New Voicemail from {caller_phone} — {company_name}"
    body = f"""
    <h2>New Voicemail Received</h2>
    <p><strong>Caller:</strong> {caller_phone}</p>
    {'<p><strong>Recording:</strong> <a href="' + recording_url + '">Listen</a></p>' if recording_url else ''}
    {'<p><strong>Transcript:</strong> ' + transcript + '</p>' if transcript else ''}
    <hr>
    <p><em>POD6 AI Voice Agent — {company_name}</em></p>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from or settings.smtp_user
        msg["To"] = to_email
        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)

        logger.info("Voicemail email sent to %s", to_email)
        return True
    except Exception:
        logger.exception("Failed to send voicemail email to %s", to_email)
        return False


async def send_followup_email(
    to_email: str,
    caller_name: str,
    summary: str,
    company_name: str = "",
) -> bool:
    """Send post-call follow-up email."""
    settings = get_settings()
    if not settings.smtp_host or not to_email:
        return False

    subject = f"Following up on your call — {company_name}"
    body = f"""
    <p>Hi {caller_name},</p>
    <p>Thank you for calling {company_name}! Here's a quick summary of our conversation:</p>
    <p>{summary}</p>
    <p>If you have any questions, don't hesitate to call us back.</p>
    <p>Best regards,<br>{company_name} Team</p>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from or settings.smtp_user
        msg["To"] = to_email
        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)

        logger.info("Follow-up email sent to %s", to_email)
        return True
    except Exception:
        logger.exception("Failed to send follow-up email to %s", to_email)
        return False
