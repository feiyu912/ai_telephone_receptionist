"""Memory cleanup — 90-day expiry + forget-me request processing.

Runs as a background task on server startup (every 24 hours).
Replicates the n8n Memory Cleanup cron workflow.
"""

from __future__ import annotations
import asyncio
import logging
from sqlalchemy import text
from app.db.client import get_session_factory

logger = logging.getLogger(__name__)


async def run_cleanup():
    """Delete expired memories and process forget-me requests."""
    factory = get_session_factory()
    async with factory() as db:
        # 1. Delete expired memory entries (90-day expiry)
        result = await db.execute(
            text("DELETE FROM caller_memory WHERE expires_at IS NOT NULL AND expires_at < NOW()")
        )
        expired_count = result.rowcount
        await db.commit()

        # 2. Process forget-me requests
        result = await db.execute(
            text("""
                DELETE FROM caller_memory
                WHERE caller_phone IN (
                    SELECT caller_phone FROM caller_consent
                    WHERE forget_requested = true AND forget_completed_at IS NULL
                )
            """)
        )
        forget_count = result.rowcount
        await db.commit()

        # 3. Mark forget requests as completed
        await db.execute(
            text("""
                UPDATE caller_consent
                SET forget_completed_at = NOW()
                WHERE forget_requested = true AND forget_completed_at IS NULL
            """)
        )
        await db.commit()

        # 4. Log cleanup event (no tenant_id — system-wide event)
        import json
        await db.execute(
            text("""
                INSERT INTO analytics_events
                    (tenant_id, event_type, channel, event_data, created_at)
                VALUES (NULL, 'memory_cleanup', 'system',
                    CAST(:data AS jsonb), NOW())
            """),
            {"data": json.dumps({"expired_deleted": expired_count, "forget_me_deleted": forget_count})},
        )
        await db.commit()

        logger.info(
            "Memory cleanup: expired=%d, forget-me=%d",
            expired_count, forget_count,
        )


async def cleanup_loop():
    """Run cleanup every 24 hours."""
    while True:
        try:
            await run_cleanup()
        except Exception:
            logger.exception("Memory cleanup failed")
        await asyncio.sleep(86400)  # 24 hours
