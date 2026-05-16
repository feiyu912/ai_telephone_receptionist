"""Idempotent migration: add call recording columns to account_settings."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import create_async_engine
from app.config import get_settings

settings = get_settings()

MIGRATION_SQL = """
ALTER TABLE account_settings
ADD COLUMN IF NOT EXISTS call_recording_enabled boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS recording_disclosure_message text DEFAULT 'This call may be recorded for quality assurance purposes.';
"""


async def main():
    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.execute(MIGRATION_SQL)
    print("Migration applied: call_recording_enabled + recording_disclosure_message")


if __name__ == "__main__":
    asyncio.run(main())
