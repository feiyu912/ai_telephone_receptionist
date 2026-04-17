"""Seed the dashboard_users table in Supabase.

Creates the table (idempotent) and upserts the three initial users:
  admin@360dmmc.com           / admin360   (admin, YourCompany)
  emilio@360dmmc.com          / 360group   (client, YourCompany)
  support@tenantb.com   / aplus2026  (client, TenantB)

Passwords are bcrypt-hashed. Safe to re-run: the upsert will refresh
password_hash/role/tenant_id for an existing email.

Usage:
    python scripts/seed_dashboard_users.py
"""

from __future__ import annotations

import asyncio
import os
import ssl
import sys

import asyncpg
import bcrypt
from dotenv import load_dotenv


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS dashboard_users (
    email         text PRIMARY KEY,
    password_hash text NOT NULL,
    role          text NOT NULL CHECK (role IN ('admin', 'client')),
    tenant_id     uuid NOT NULL REFERENCES account_settings(tenant_id),
    tenant_name   text NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS dashboard_users_tenant_idx
    ON dashboard_users (tenant_id);

ALTER TABLE dashboard_users
    ADD COLUMN IF NOT EXISTS tenant_name text;

UPDATE dashboard_users SET tenant_name = '' WHERE tenant_name IS NULL;

ALTER TABLE dashboard_users
    ALTER COLUMN tenant_name SET NOT NULL;
"""

UPSERT_USER_SQL = """
INSERT INTO dashboard_users (email, password_hash, role, tenant_id, tenant_name)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (email) DO UPDATE SET
    password_hash = EXCLUDED.password_hash,
    role          = EXCLUDED.role,
    tenant_id     = EXCLUDED.tenant_id,
    tenant_name   = EXCLUDED.tenant_name,
    updated_at    = now();
"""

SEED_USERS = [
    ("admin@360dmmc.com",         "admin360",  "admin",  "11111111-1111-1111-1111-111111111111", "YourCompany"),
    ("emilio@360dmmc.com",        "360group",  "client", "11111111-1111-1111-1111-111111111111", "YourCompany"),
    ("support@tenantb.com", "aplus2026", "client", "22222222-2222-2222-2222-222222222222", "TenantB"),
]


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


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
        await conn.execute(CREATE_TABLE_SQL)
        print("dashboard_users table ready")

        for email, password, role, tenant_id, tenant_name in SEED_USERS:
            await conn.execute(
                UPSERT_USER_SQL, email, _hash(password), role, tenant_id, tenant_name
            )
            print(f"  upserted {email} ({role}, {tenant_name})")
    finally:
        await conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
