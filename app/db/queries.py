"""Raw SQL queries for Supabase PostgreSQL. All multi-tenant with tenant_id.

Note: Uses CAST(x AS jsonb) instead of x::jsonb because asyncpg interprets
the :: syntax as named parameters.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.schemas import TenantConfig, CallerMemory, VoiceSession
from typing import Optional
import json


def _parse_tenant_row(row) -> TenantConfig:
    """Convert a DB row to TenantConfig, handling UUID and JSONB fields."""
    data = dict(row)
    if "tenant_id" in data and not isinstance(data["tenant_id"], str):
        data["tenant_id"] = str(data["tenant_id"])
    for field in ("hunt_group_numbers", "business_hours_days"):
        if isinstance(data.get(field), str):
            data[field] = json.loads(data[field])
    return TenantConfig(**data)


# ── Tenant Resolution ──────────────────────────────────────────────

async def get_tenant_by_phone(db: AsyncSession, phone: str) -> Optional[TenantConfig]:
    """Resolve a Twilio To number to tenant config."""
    result = await db.execute(
        text("SELECT * FROM account_settings WHERE phone_number = :phone AND is_active = true"),
        {"phone": phone},
    )
    row = result.mappings().first()
    return _parse_tenant_row(row) if row else None


async def get_tenant_by_id(db: AsyncSession, tenant_id: str) -> Optional[TenantConfig]:
    """Load tenant config by tenant_id."""
    result = await db.execute(
        text("SELECT * FROM account_settings WHERE tenant_id = :tid AND is_active = true"),
        {"tid": tenant_id},
    )
    row = result.mappings().first()
    return _parse_tenant_row(row) if row else None


# ── Caller Memory ──────────────────────────────────────────────────

async def lookup_caller_memory(
    db: AsyncSession, tenant_id: str, phone: str
) -> list[CallerMemory]:
    """Load non-expired memory for a caller, respecting forget-me requests."""
    result = await db.execute(
        text("""
            SELECT memory_key, memory_value, privacy_tier
            FROM caller_memory
            WHERE tenant_id = :tid AND caller_phone = :phone
              AND (expires_at IS NULL OR expires_at > NOW())
              AND caller_phone NOT IN (
                SELECT caller_phone FROM caller_consent
                WHERE tenant_id = :tid AND forget_requested = true
                  AND forget_completed_at IS NULL
              )
        """),
        {"tid": tenant_id, "phone": phone},
    )
    return [CallerMemory(**dict(r)) for r in result.mappings().all()]


async def save_caller_memory(
    db: AsyncSession,
    tenant_id: str,
    phone: str,
    key: str,
    value: str,
    channel: str = "voice",
    session_id: str | None = None,
) -> None:
    """Upsert a memory fact with privacy tier classification and 90-day expiry."""
    safe_keys = {
        "service_interest", "communication_preference", "call_count",
        "last_call_date", "last_topic", "sentiment", "intent", "outcome",
        "preferred_language", "referral_source",
    }
    privacy_tier = "safe" if key in safe_keys else "protected"

    await db.execute(
        text("""
            INSERT INTO caller_memory
                (tenant_id, caller_phone, memory_key, memory_value,
                 privacy_tier, source_channel, source_session,
                 expires_at, created_at, updated_at)
            VALUES
                (:tid, :phone, :key, :value,
                 :tier, :channel, :session,
                 NOW() + INTERVAL '90 days', NOW(), NOW())
            ON CONFLICT (tenant_id, caller_phone, memory_key)
            DO UPDATE SET
                memory_value = EXCLUDED.memory_value,
                privacy_tier = EXCLUDED.privacy_tier,
                source_channel = EXCLUDED.source_channel,
                source_session = EXCLUDED.source_session,
                expires_at = NOW() + INTERVAL '90 days',
                updated_at = NOW()
        """),
        {
            "tid": tenant_id, "phone": phone, "key": key,
            "value": value, "tier": privacy_tier,
            "channel": channel, "session": session_id,
        },
    )
    await db.commit()


async def forget_caller(db: AsyncSession, tenant_id: str, phone: str) -> None:
    """GDPR right-to-be-forgotten: flag consent + delete all memory."""
    await db.execute(
        text("""
            INSERT INTO caller_consent (tenant_id, caller_phone, forget_requested, forget_requested_at, created_at, updated_at)
            VALUES (:tid, :phone, true, NOW(), NOW(), NOW())
            ON CONFLICT (tenant_id, caller_phone)
            DO UPDATE SET forget_requested = true, forget_requested_at = NOW(), updated_at = NOW()
        """),
        {"tid": tenant_id, "phone": phone},
    )
    await db.execute(
        text("DELETE FROM caller_memory WHERE tenant_id = :tid AND caller_phone = :phone"),
        {"tid": tenant_id, "phone": phone},
    )
    await db.commit()


async def get_caller_consent(
    db: AsyncSession, tenant_id: str, phone: str
) -> dict | None:
    result = await db.execute(
        text("SELECT * FROM caller_consent WHERE tenant_id = :tid AND caller_phone = :phone"),
        {"tid": tenant_id, "phone": phone},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def save_caller_consent(
    db: AsyncSession, tenant_id: str, phone: str, consent: bool, channel: str = "voice"
) -> None:
    await db.execute(
        text("""
            INSERT INTO caller_consent
                (tenant_id, caller_phone, memory_consent, consent_given_at, consent_channel, created_at, updated_at)
            VALUES (:tid, :phone, :consent, NOW(), :channel, NOW(), NOW())
            ON CONFLICT (tenant_id, caller_phone)
            DO UPDATE SET memory_consent = :consent, consent_given_at = NOW(), consent_channel = :channel, updated_at = NOW()
        """),
        {"tid": tenant_id, "phone": phone, "consent": consent, "channel": channel},
    )
    await db.commit()


# ── Voice Sessions ─────────────────────────────────────────────────

async def create_voice_session(db: AsyncSession, session: VoiceSession) -> None:
    await db.execute(
        text("""
            INSERT INTO voice_sessions
                (call_sid, caller_phone, called_number, tenant_id, tier, selected_voice,
                 conversation_history, session_metadata, status, started_at, last_activity_at, created_at)
            VALUES
                (:call_sid, :caller_phone, :called_number, :tid, :tier, :voice,
                 CAST(:history AS jsonb), CAST(:metadata AS jsonb), 'active', NOW(), NOW(), NOW())
            ON CONFLICT (call_sid) DO NOTHING
        """),
        {
            "call_sid": session.call_sid,
            "caller_phone": session.caller_phone,
            "called_number": session.called_number,
            "tid": session.tenant_id,
            "tier": session.tier,
            "voice": session.selected_voice,
            "history": json.dumps(session.conversation_history),
            "metadata": json.dumps(session.session_metadata),
        },
    )
    await db.commit()


async def get_voice_session(db: AsyncSession, call_sid: str) -> dict | None:
    result = await db.execute(
        text("SELECT * FROM voice_sessions WHERE call_sid = :sid"),
        {"sid": call_sid},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def update_voice_session(
    db: AsyncSession,
    call_sid: str,
    conversation_history: list[dict] | None = None,
    session_metadata: dict | None = None,
    status: str | None = None,
    booking_context: dict | None = None,
) -> None:
    sets = ["last_activity_at = NOW()"]
    params: dict = {"sid": call_sid}

    if conversation_history is not None:
        sets.append("conversation_history = CAST(:history AS jsonb)")
        params["history"] = json.dumps(conversation_history)
    if session_metadata is not None:
        sets.append("session_metadata = CAST(:metadata AS jsonb)")
        params["metadata"] = json.dumps(session_metadata)
    if status is not None:
        sets.append("status = :status")
        params["status"] = status
    if booking_context is not None:
        sets.append("booking_context = CAST(:booking AS jsonb)")
        params["booking"] = json.dumps(booking_context)

    await db.execute(
        text(f"UPDATE voice_sessions SET {', '.join(sets)} WHERE call_sid = :sid"),
        params,
    )
    await db.commit()


# ── Customers ──────────────────────────────────────────────────────

async def upsert_customer(
    db: AsyncSession, tenant_id: str, phone: str,
    name: str | None = None, email: str | None = None,
    key_facts: dict | None = None,
) -> str:
    """Create or update customer, return customer_id."""
    result = await db.execute(
        text("""
            INSERT INTO customers (tenant_id, phone, name, email, key_facts, created_at, updated_at)
            VALUES (:tid, :phone, COALESCE(:name, 'Guest'), :email, COALESCE(CAST(:facts AS jsonb), CAST('{}' AS jsonb)), NOW(), NOW())
            ON CONFLICT (tenant_id, phone)
            DO UPDATE SET
                name = COALESCE(NULLIF(EXCLUDED.name, 'Guest'), customers.name),
                email = COALESCE(EXCLUDED.email, customers.email),
                key_facts = customers.key_facts || COALESCE(EXCLUDED.key_facts, CAST('{}' AS jsonb)),
                updated_at = NOW()
            RETURNING customer_id
        """),
        {"tid": tenant_id, "phone": phone, "name": name, "email": email, "facts": json.dumps(key_facts or {})},
    )
    row = result.fetchone()
    await db.commit()
    return str(row[0]) if row else ""


# ── Conversations ──────────────────────────────────────────────────

async def create_conversation(
    db: AsyncSession,
    tenant_id: str,
    customer_id: str | None,
    channel: str,
    external_id: str,
    summary: str | None = None,
    intent: str | None = None,
    outcome: str | None = None,
    sentiment: str | None = None,
) -> str:
    result = await db.execute(
        text("""
            INSERT INTO conversations
                (tenant_id, customer_id, channel, external_id, summary, intent, outcome, sentiment,
                 status, started_at, ended_at, created_at)
            VALUES
                (:tid, :cid, :channel, :eid, :summary, :intent, :outcome, :sentiment,
                 'completed', NOW(), NOW(), NOW())
            ON CONFLICT (external_id) DO UPDATE SET
                summary = COALESCE(EXCLUDED.summary, conversations.summary),
                intent = COALESCE(EXCLUDED.intent, conversations.intent),
                outcome = COALESCE(EXCLUDED.outcome, conversations.outcome),
                sentiment = COALESCE(EXCLUDED.sentiment, conversations.sentiment),
                ended_at = NOW()
            RETURNING conversation_id
        """),
        {
            "tid": tenant_id, "cid": customer_id, "channel": channel,
            "eid": external_id, "summary": summary, "intent": intent,
            "outcome": outcome, "sentiment": sentiment,
        },
    )
    row = result.fetchone()
    await db.commit()
    return str(row[0]) if row else ""


# ── FAQ ────────────────────────────────────────────────────────────

async def get_faq_entries(db: AsyncSession, tenant_id: str) -> list[dict]:
    result = await db.execute(
        text("SELECT id, category, question, answer FROM faq_entries WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )
    return [dict(r) for r in result.mappings().all()]


# ── Analytics ──────────────────────────────────────────────────────

async def log_analytics_event(
    db: AsyncSession,
    tenant_id: str,
    event_type: str,
    channel: str,
    phone: str | None = None,
    session_id: str | None = None,
    event_data: dict | None = None,
) -> None:
    await db.execute(
        text("""
            INSERT INTO analytics_events
                (tenant_id, event_type, channel, customer_phone, session_id, event_data, created_at)
            VALUES (:tid, :etype, :channel, :phone, :sid, CAST(:data AS jsonb), NOW())
        """),
        {
            "tid": tenant_id, "etype": event_type, "channel": channel,
            "phone": phone, "sid": session_id,
            "data": json.dumps(event_data or {}),
        },
    )
    await db.commit()
