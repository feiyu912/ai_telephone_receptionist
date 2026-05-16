"""Idempotent migration: add admin alert columns to account_settings."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import get_settings


async def main():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True)

    async with engine.begin() as conn:
        await conn.execute(text("""
            ALTER TABLE account_settings
                ADD COLUMN IF NOT EXISTS alert_email text,
                ADD COLUMN IF NOT EXISTS alert_slack_webhook text,
                ADD COLUMN IF NOT EXISTS alert_on_new_lead boolean DEFAULT true,
                ADD COLUMN IF NOT EXISTS alert_on_booking boolean DEFAULT true,
                ADD COLUMN IF NOT EXISTS alert_on_voicemail boolean DEFAULT true,
                ADD COLUMN IF NOT EXISTS alert_on_usage_threshold boolean DEFAULT true,
                ADD COLUMN IF NOT EXISTS alert_usage_threshold_minutes integer DEFAULT 500;
        """))

    print("Admin alert columns added to account_settings.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
