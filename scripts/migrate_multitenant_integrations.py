"""Add per-tenant integration columns to account_settings.

Before this migration all tenants shared a single Outlook mailbox
(MS_SENDER_EMAIL / MS_CALENDAR_EMAIL), a single HubSpot private-app
token (HUBSPOT_ACCESS_TOKEN), and a single Twilio account
(TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN). That worked while the only
live tenant was YourCompany; it breaks as soon as a second tenant wants
its own branding / CRM / carrier credentials.

New columns (all nullable — NULL means "fall back to the global env"):
  sender_email        — From: address for outbound mail
  calendar_email      — mailbox whose calendar bookings land on
  hubspot_access_token — per-tenant HubSpot private-app token or OAuth token
  twilio_account_sid  — per-tenant Twilio (sub)account SID
  twilio_auth_token   — matching auth token (used for signature validation
                        + outbound SMS)

Idempotent: uses IF NOT EXISTS everywhere. Safe to re-run.

Usage:
    python scripts/migrate_multitenant_integrations.py
"""

from __future__ import annotations

import asyncio
import os
import ssl
import sys

import asyncpg
from dotenv import load_dotenv

MIGRATION_SQL = """
ALTER TABLE account_settings
    ADD COLUMN IF NOT EXISTS sender_email           text,
    ADD COLUMN IF NOT EXISTS calendar_email         text,
    ADD COLUMN IF NOT EXISTS hubspot_access_token   text,
    ADD COLUMN IF NOT EXISTS twilio_account_sid     text,
    ADD COLUMN IF NOT EXISTS twilio_auth_token      text,
    ADD COLUMN IF NOT EXISTS twilio_api_key_sid     text,
    ADD COLUMN IF NOT EXISTS twilio_api_key_secret  text,
    ADD COLUMN IF NOT EXISTS twilio_twiml_app_sid   text;
"""


def _asyncpg_url(url: str) -> str:
    return (
        url.replace("postgresql+asyncpg://", "postgresql://")
           .replace("postgresql+psycopg://", "postgresql://")
    )


async def main() -> int:
    load_dotenv()
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 1

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    conn = await asyncpg.connect(_asyncpg_url(url), ssl=ssl_ctx)
    try:
        await conn.execute(MIGRATION_SQL)
        print("account_settings — added per-tenant integration columns")

        # Report current state
        rows = await conn.fetch(
            """
            SELECT company_name,
                   sender_email IS NOT NULL         AS has_sender,
                   calendar_email IS NOT NULL       AS has_calendar,
                   hubspot_access_token IS NOT NULL AS has_hubspot,
                   twilio_account_sid IS NOT NULL   AS has_twilio
            FROM account_settings ORDER BY company_name
            """
        )
        print()
        print(f"  {'tenant':25} {'sender':7} {'cal':5} {'hs':4} {'tw':4}")
        for r in rows:
            print(
                f"  {r['company_name']:25} "
                f"{'yes' if r['has_sender'] else 'no':7} "
                f"{'yes' if r['has_calendar'] else 'no':5} "
                f"{'yes' if r['has_hubspot'] else 'no':4} "
                f"{'yes' if r['has_twilio'] else 'no':4}"
            )
        print()
        print("NULL values fall back to the global env vars.")
    finally:
        await conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
