"""Idempotent migration: add industry_playbook column to account_settings."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import create_async_engine
from app.config import get_settings

settings = get_settings()

MIGRATION_SQL = """
ALTER TABLE account_settings
ADD COLUMN IF NOT EXISTS industry_playbook text;
"""


async def main():
    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.execute(MIGRATION_SQL)
    print("Migration applied: industry_playbook")


if __name__ == "__main__":
    asyncio.run(main())
