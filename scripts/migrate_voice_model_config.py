"""Add per-tenant model selection + ai_models allowlist table.

Idempotent: uses IF NOT EXISTS / ON CONFLICT everywhere. Safe to re-run.

Usage:
    python scripts/migrate_voice_model_config.py
"""

from __future__ import annotations

import asyncio
import os
import ssl
import sys

import asyncpg
from dotenv import load_dotenv

MIGRATION_SQL = """
-- Per-tenant model selection (Realtime path only)
ALTER TABLE account_settings
    ADD COLUMN IF NOT EXISTS selected_model text DEFAULT 'gpt-realtime-mini';

-- Capture which model a call actually used (analytics / debugging)
ALTER TABLE voice_sessions
    ADD COLUMN IF NOT EXISTS selected_model text;

-- Allowlist of AI models. Dashboard reads from here; admin sync populates it.
CREATE TABLE IF NOT EXISTS ai_models (
    id uuid primary key default gen_random_uuid(),
    provider text not null,
    model_id text not null,
    display_name text not null,
    category text not null,
    tier text not null default 'starter',
    supports_audio_input boolean not null default false,
    supports_audio_output boolean not null default false,
    supports_text_input boolean not null default true,
    supports_text_output boolean not null default true,
    supports_reasoning boolean not null default false,
    enabled boolean not null default true,
    recommended boolean not null default false,
    sort_order int not null default 100,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(provider, model_id)
);

-- Seed baseline OpenAI realtime models (enabled by default for existing tenants)
INSERT INTO ai_models
    (provider, model_id, display_name, category, tier,
     supports_audio_input, supports_audio_output, supports_reasoning,
     enabled, recommended, sort_order)
VALUES
    ('openai', 'gpt-realtime-mini', 'GPT Realtime Mini', 'realtime', 'starter',
     true, true, false, true, true, 1),
    ('openai', 'gpt-realtime', 'GPT Realtime', 'realtime', 'growth',
     true, true, false, true, false, 2),
    ('openai', 'gpt-realtime-2', 'GPT Realtime 2', 'realtime', 'growth',
     true, true, true, true, false, 3)
ON CONFLICT (provider, model_id) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    category = EXCLUDED.category,
    tier = EXCLUDED.tier,
    supports_audio_input = EXCLUDED.supports_audio_input,
    supports_audio_output = EXCLUDED.supports_audio_output,
    supports_reasoning = EXCLUDED.supports_reasoning,
    enabled = EXCLUDED.enabled,
    recommended = EXCLUDED.recommended,
    sort_order = EXCLUDED.sort_order,
    updated_at = NOW();
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
        print("Migration applied: selected_model columns + ai_models table")

        rows = await conn.fetch(
            "SELECT model_id, display_name, tier, enabled, recommended FROM ai_models ORDER BY sort_order"
        )
        print()
        print(f"  {'model_id':25} {'display_name':25} {'tier':10} {'enabled':8} {'recommended':12}")
        for r in rows:
            print(
                f"  {r['model_id']:25} {r['display_name']:25} {r['tier']:10} "
                f"{'yes' if r['enabled'] else 'no':8} {'yes' if r['recommended'] else 'no':12}"
            )
        print()
        print("Run `POST /admin/models/sync` to discover new OpenAI models (inserted disabled by default).")
    finally:
        await conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
