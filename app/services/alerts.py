"""Admin alert dispatcher — email (Microsoft Graph) + Slack webhook.

Triggered by post-call events: new lead, booking, voicemail, usage threshold.
Usage threshold is monthly cumulative minutes across all closed calls.
"""

from __future__ import annotations
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.services.email import _send_via_graph
from app.models.schemas import TenantConfig

logger = logging.getLogger(__name__)


async def send_admin_alert(
    tenant: TenantConfig,
    event_type: str,
    title: str,
    message: str,
    details: dict | None = None,
    db: AsyncSession | None = None,
) -> None:
    """Dispatch alert via email and/or Slack according to tenant config.

    Non-blocking: failures are logged but never raise.
    """
    if not tenant:
        return

    # Filter by per-event toggle
    toggle_map = {
        "new_lead": tenant.alert_on_new_lead,
        "booking": tenant.alert_on_booking,
        "voicemail": tenant.alert_on_voicemail,
        "usage_threshold": tenant.alert_on_usage_threshold,
    }
    if not toggle_map.get(event_type, True):
        return

    try:
        if tenant.alert_email:
            await _send_email_alert(tenant, title, message, details)
    except Exception:
        logger.exception("Admin email alert failed for %s", event_type)

    try:
        if tenant.alert_slack_webhook:
            await _send_slack_alert(tenant.alert_slack_webhook, title, message, details)
    except Exception:
        logger.exception("Admin Slack alert failed for %s", event_type)

    # For usage threshold, record that we sent the alert so we don't spam
    if event_type == "usage_threshold" and db is not None:
        try:
            await db.execute(
                text("""
                    INSERT INTO analytics_events
                        (tenant_id, event_type, channel, event_data, created_at)
                    VALUES (:tid, 'usage_threshold_alert_sent', 'system',
                            CAST(:data AS jsonb), NOW())
                """),
                {
                    "tid": tenant.tenant_id,
                    "data": "{}",
                },
            )
            await db.commit()
        except Exception:
            logger.exception("Failed to log usage threshold alert event")


async def _send_email_alert(
    tenant: TenantConfig,
    title: str,
    message: str,
    details: dict | None = None,
) -> bool:
    sender = tenant.sender_email or get_settings().ms_sender_email
    if not sender or not tenant.alert_email:
        return False

    html_parts = [f"<h2>{title}</h2>", f"<p>{message}</p>"]
    if details:
        html_parts.append("<ul>")
        for k, v in details.items():
            html_parts.append(f"<li><strong>{k}:</strong> {v}</li>")
        html_parts.append("</ul>")
    html_parts.append(f"<hr><p><em>AI Telephone Receptionist — {tenant.company_name or ''}</em></p>")

    return await _send_via_graph(
        sender=sender,
        to_email=tenant.alert_email,
        subject=title,
        html_body="".join(html_parts),
        tenant_id=tenant.tenant_id,
    )


async def _send_slack_alert(
    webhook_url: str,
    title: str,
    message: str,
    details: dict | None = None,
) -> bool:
    import httpx

    fields = []
    if details:
        for k, v in details.items():
            fields.append({"type": "mrkdwn", "text": f"*{k}*\n{v}"})

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": title}},
        {"type": "section", "text": {"type": "mrkdwn", "text": message}},
    ]
    if fields:
        blocks.append({"type": "section", "fields": fields})

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            webhook_url,
            json={"blocks": blocks},
            timeout=15,
        )
        if resp.status_code == 200:
            logger.info("Slack alert sent: %s", title)
            return True
        logger.warning("Slack alert failed (%s): %s", resp.status_code, resp.text[:300])
        return False


async def get_monthly_minutes(db: AsyncSession, tenant_id: str) -> float:
    """Return cumulative call minutes for the tenant in the current month."""
    result = await db.execute(
        text("""
            SELECT COALESCE(
                SUM(EXTRACT(EPOCH FROM (last_activity_at - started_at)) / 60), 0
            ) as total_minutes
            FROM voice_sessions
            WHERE tenant_id = :tid
              AND status = 'closed'
              AND started_at >= DATE_TRUNC('month', NOW())
        """),
        {"tid": tenant_id},
    )
    row = result.mappings().first()
    return float(row["total_minutes"]) if row else 0.0


async def already_alerted_this_month(db: AsyncSession, tenant_id: str) -> bool:
    """Check if a usage-threshold alert was already sent this month."""
    result = await db.execute(
        text("""
            SELECT 1 FROM analytics_events
            WHERE tenant_id = :tid
              AND event_type = 'usage_threshold_alert_sent'
              AND created_at >= DATE_TRUNC('month', NOW())
            LIMIT 1
        """),
        {"tid": tenant_id},
    )
    return result.fetchone() is not None
