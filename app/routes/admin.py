"""Admin API for tenant management — settings, FAQs, customers.

Provides CRUD endpoints for the tenant dashboard.
"""

from __future__ import annotations
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.client import get_db
from app.services.auth import AuthUser, require_admin, require_tenant_access

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


# ── Tenant list ───────────────────────────────────────────────────

@router.get("/tenants")
async def list_tenants(
    _user: AuthUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all active tenants for dashboard switcher."""
    result = await db.execute(
        text(
            "SELECT tenant_id, company_name, slug, phone_number, tier "
            "FROM account_settings WHERE is_active = true ORDER BY company_name"
        )
    )
    return [
        {
            "tenant_id": str(r["tenant_id"]),
            "company_name": r["company_name"],
            "slug": r["slug"],
            "phone_number": r["phone_number"],
            "tier": r["tier"],
        }
        for r in result.mappings().all()
    ]


# ── Pydantic models ───────────────────────────────────────────────

class SettingsUpdate(BaseModel):
    company_name: str | None = None
    system_prompt: str | None = None
    system_prompt_growth: str | None = None
    greeting_new: str | None = None
    greeting_returning: str | None = None
    after_hours_message: str | None = None
    voicemail_email: str | None = None
    selected_voice: str | None = None
    selected_model: str | None = None
    tier: str | None = None
    business_hours_start: int | None = None
    business_hours_end: int | None = None
    business_hours_timezone: str | None = None
    business_hours_days: list[int] | None = None
    hunt_group_numbers: list[str] | None = None
    transfer_timeout: int | None = None
    booking_enabled: bool | None = None
    booking_duration_minutes: int | None = None
    booking_buffer_minutes: int | None = None
    booking_advance_days: int | None = None
    memory_expiry_days: int | None = None
    hubspot_booking_link: str | None = None
    # Per-tenant integration credentials (multi-tenant overhaul)
    sender_email: str | None = None
    calendar_email: str | None = None
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_api_key_sid: str | None = None
    twilio_api_key_secret: str | None = None
    twilio_twiml_app_sid: str | None = None
    hubspot_access_token: str | None = None
    call_recording_enabled: bool | None = None
    recording_disclosure_message: str | None = None
    # Admin alerts
    alert_email: str | None = None
    alert_slack_webhook: str | None = None
    alert_on_new_lead: bool | None = None
    alert_on_booking: bool | None = None
    alert_on_voicemail: bool | None = None
    alert_on_usage_threshold: bool | None = None
    alert_usage_threshold_minutes: int | None = None


# Columns that must never leave the server as plaintext. GET replaces them
# with a `<field>_set: bool` marker; PATCH accepts them but treats an empty
# string as "no change" so an unedited dashboard form never wipes them.
_SECRET_FIELDS = (
    "twilio_auth_token",
    "twilio_api_key_secret",
    "hubspot_access_token",
)


class FAQCreate(BaseModel):
    category: str
    question: str
    answer: str
    is_coming_soon: bool = False


class FAQUpdate(BaseModel):
    category: str | None = None
    question: str | None = None
    answer: str | None = None
    is_coming_soon: bool | None = None


# ── Settings ───────────────────────────────────────────────────────

@router.get("/settings/{tenant_id}")
async def get_settings(
    tenant_id: str,
    _user: AuthUser = Depends(require_tenant_access),
    db: AsyncSession = Depends(get_db),
):
    """Get tenant settings. Secret fields are redacted to boolean markers so
    they never round-trip through the browser."""
    result = await db.execute(
        text("SELECT * FROM account_settings WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Tenant not found")
    data = dict(row)
    if "tenant_id" in data:
        data["tenant_id"] = str(data["tenant_id"])
    for field in _SECRET_FIELDS:
        data[f"{field}_set"] = bool(data.get(field))
        data.pop(field, None)
    return data


@router.patch("/settings/{tenant_id}")
async def update_settings(
    tenant_id: str,
    updates: SettingsUpdate,
    _user: AuthUser = Depends(require_tenant_access),
    db: AsyncSession = Depends(get_db),
):
    """Update tenant settings (partial update). Empty strings on secret
    fields are treated as 'no change' — so re-submitting the form after
    editing only the non-secret tabs doesn't wipe Twilio/HubSpot tokens."""
    fields = updates.model_dump(exclude_none=True)
    for field in _SECRET_FIELDS:
        if fields.get(field) == "":
            fields.pop(field)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    import json
    sets = []
    params = {"tid": tenant_id}
    for key, value in fields.items():
        if isinstance(value, (list, dict)):
            sets.append(f"{key} = CAST(:{key} AS jsonb)")
            params[key] = json.dumps(value)
        else:
            sets.append(f"{key} = :{key}")
            params[key] = value

    await db.execute(
        text(f"UPDATE account_settings SET {', '.join(sets)} WHERE tenant_id = :tid"),
        params,
    )
    await db.commit()

    # Sync Twilio phone number recording when the toggle changes
    if "call_recording_enabled" in fields:
        import asyncio
        from app.services.recording import update_phone_recording

        tenant_row = await db.execute(
            text("SELECT phone_number, twilio_account_sid, twilio_auth_token FROM account_settings WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        )
        row = tenant_row.mappings().first()
        if row:
            await asyncio.to_thread(
                update_phone_recording,
                phone_number=row["phone_number"],
                enabled=bool(fields["call_recording_enabled"]),
                account_sid=row["twilio_account_sid"] or None,
                auth_token=row["twilio_auth_token"] or None,
            )

    return {"status": "updated", "fields": list(fields.keys())}


# ── FAQ Management ─────────────────────────────────────────────────

@router.get("/faq/{tenant_id}")
async def list_faqs(
    tenant_id: str,
    _user: AuthUser = Depends(require_tenant_access),
    db: AsyncSession = Depends(get_db),
):
    """List all FAQs for a tenant."""
    result = await db.execute(
        text("SELECT id, category, question, answer, is_coming_soon FROM faq_entries WHERE tenant_id = :tid ORDER BY category, id"),
        {"tid": tenant_id},
    )
    return [dict(r) for r in result.mappings().all()]


@router.post("/faq/{tenant_id}")
async def create_faq(
    tenant_id: str,
    faq: FAQCreate,
    _user: AuthUser = Depends(require_tenant_access),
    db: AsyncSession = Depends(get_db),
):
    """Create a new FAQ entry."""
    result = await db.execute(
        text("""
            INSERT INTO faq_entries (tenant_id, category, question, answer, is_coming_soon, created_at)
            VALUES (:tid, :category, :question, :answer, :coming_soon, NOW())
            RETURNING id
        """),
        {
            "tid": tenant_id, "category": faq.category,
            "question": faq.question, "answer": faq.answer,
            "coming_soon": faq.is_coming_soon,
        },
    )
    row = result.fetchone()
    await db.commit()
    return {"id": row[0] if row else None, "status": "created"}


@router.patch("/faq/{tenant_id}/{faq_id}")
async def update_faq(
    tenant_id: str,
    faq_id: int,
    faq: FAQUpdate,
    _user: AuthUser = Depends(require_tenant_access),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing FAQ entry."""
    fields = faq.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    sets = []
    params = {"tid": tenant_id, "fid": faq_id}
    for key, value in fields.items():
        param_name = f"v_{key}"
        sets.append(f"{key} = :{param_name}")
        params[param_name] = value

    await db.execute(
        text(f"UPDATE faq_entries SET {', '.join(sets)} WHERE tenant_id = :tid AND id = :fid"),
        params,
    )
    await db.commit()
    return {"status": "updated"}


@router.delete("/faq/{tenant_id}/{faq_id}")
async def delete_faq(
    tenant_id: str,
    faq_id: int,
    _user: AuthUser = Depends(require_tenant_access),
    db: AsyncSession = Depends(get_db),
):
    """Delete a FAQ entry."""
    await db.execute(
        text("DELETE FROM faq_entries WHERE tenant_id = :tid AND id = :fid"),
        {"tid": tenant_id, "fid": faq_id},
    )
    await db.commit()
    return {"status": "deleted"}


# ── Customers ──────────────────────────────────────────────────────

@router.get("/customers/{tenant_id}")
async def list_customers(
    tenant_id: str,
    _user: AuthUser = Depends(require_tenant_access),
    db: AsyncSession = Depends(get_db),
):
    """List customers for a tenant."""
    result = await db.execute(
        text("""
            SELECT customer_id, phone, name, email, tier, key_facts, created_at, updated_at
            FROM customers WHERE tenant_id = :tid ORDER BY updated_at DESC LIMIT 100
        """),
        {"tid": tenant_id},
    )
    rows = []
    for r in result.mappings().all():
        d = dict(r)
        d["customer_id"] = str(d["customer_id"])
        rows.append(d)
    return rows


# ── Call History ───────────────────────────────────────────────────

@router.get("/calls/{tenant_id}")
async def list_calls(
    tenant_id: str,
    _user: AuthUser = Depends(require_tenant_access),
    db: AsyncSession = Depends(get_db),
):
    """List recent voice sessions for a tenant."""
    result = await db.execute(
        text("""
            SELECT call_sid, caller_phone, called_number, tier, status,
                   started_at, last_activity_at
            FROM voice_sessions WHERE tenant_id = :tid
            ORDER BY started_at DESC LIMIT 50
        """),
        {"tid": tenant_id},
    )
    return [dict(r) for r in result.mappings().all()]


# ── Analytics Summary ──────────────────────────────────────────────

@router.get("/analytics/{tenant_id}")
async def analytics_summary(
    tenant_id: str,
    _user: AuthUser = Depends(require_tenant_access),
    db: AsyncSession = Depends(get_db),
):
    """Get analytics summary for a tenant."""
    # Total calls
    calls = await db.execute(
        text("SELECT COUNT(*) FROM voice_sessions WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )
    total_calls = calls.scalar()

    # Total customers
    customers = await db.execute(
        text("SELECT COUNT(*) FROM customers WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )
    total_customers = customers.scalar()

    # Memory facts
    memories = await db.execute(
        text("SELECT COUNT(*) FROM caller_memory WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )
    total_memories = memories.scalar()

    # Recent events
    events = await db.execute(
        text("""
            SELECT event_type, COUNT(*) as cnt
            FROM analytics_events WHERE tenant_id = :tid
            GROUP BY event_type ORDER BY cnt DESC LIMIT 10
        """),
        {"tid": tenant_id},
    )

    return {
        "total_calls": total_calls,
        "total_customers": total_customers,
        "total_memory_facts": total_memories,
        "event_breakdown": [dict(r) for r in events.mappings().all()],
    }


# ── AI Models (allowlist) ──────────────────────────────────────────

@router.get("/models")
async def list_ai_models(
    tier: str = "starter",
    category: str = "realtime",
    _user: AuthUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Return enabled AI models for the given tier + category.

    Used by the dashboard to populate the model dropdown.
    """
    result = await db.execute(
        text("""
            SELECT id, provider, model_id, display_name, category, tier,
                   supports_audio_input, supports_audio_output, supports_reasoning,
                   recommended, sort_order
            FROM ai_models
            WHERE category = :category AND enabled = true
              AND (
                  tier = :tier
                  OR tier = 'starter'
                  OR (:tier = 'pro' AND tier = 'growth')
              )
            ORDER BY sort_order, display_name
        """),
        {"tier": tier, "category": category},
    )
    return [dict(r) for r in result.mappings().all()]


@router.post("/models/sync")
async def sync_ai_models(
    _user: AuthUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin-only: sync available models from OpenAI and upsert into ai_models.

    New models are inserted with enabled=false so they must be manually
    reviewed and enabled before appearing in customer dashboards.
    """
    from openai import AsyncOpenAI
    from app.config import get_settings

    # Known mapping of realtime model IDs to friendly names / tiers.
    # OpenAI's models.list() does NOT reliably return realtime models,
    # so we seed/upsert the known ones directly and still scan the API
    # for any future unknown models.
    KNOWN = {
        "gpt-realtime-mini": {
            "display_name": "GPT Realtime Mini",
            "tier": "starter",
            "recommended": True,
            "sort_order": 1,
        },
        "gpt-realtime": {
            "display_name": "GPT Realtime",
            "tier": "growth",
            "recommended": False,
            "sort_order": 2,
        },
        "gpt-realtime-2": {
            "display_name": "GPT Realtime 2",
            "tier": "growth",
            "recommended": False,
            "sort_order": 3,
        },
    }

    inserted = 0

    # 1. Upsert KNOWN models (enabled by default)
    for model_id, info in KNOWN.items():
        result = await db.execute(
            text("""
                INSERT INTO ai_models
                    (provider, model_id, display_name, category, tier,
                     supports_audio_input, supports_audio_output,
                     supports_text_input, supports_text_output,
                     supports_reasoning, enabled, recommended, sort_order,
                     created_at, updated_at)
                VALUES
                    ('openai', :model_id, :display_name, 'realtime', :tier,
                     true, true, true, true,
                     :supports_reasoning, true, :recommended, :sort_order,
                     NOW(), NOW())
                ON CONFLICT (provider, model_id) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    tier = EXCLUDED.tier,
                    enabled = true,
                    recommended = EXCLUDED.recommended,
                    sort_order = EXCLUDED.sort_order,
                    updated_at = NOW()
            """),
            {
                "model_id": model_id,
                "display_name": info["display_name"],
                "tier": info["tier"],
                "supports_reasoning": model_id == "gpt-realtime-2",
                "recommended": info["recommended"],
                "sort_order": info["sort_order"],
            },
        )
        if result.rowcount:
            inserted += 1

    # 2. Also scan OpenAI API for any unknown future realtime models
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    try:
        openai_models = await client.models.list()
        realtime_ids = {m.id for m in openai_models.data if "realtime" in m.id}
    except Exception:
        realtime_ids = set()

    for model_id in realtime_ids:
        if model_id in KNOWN:
            continue  # already handled above
        result = await db.execute(
            text("""
                INSERT INTO ai_models
                    (provider, model_id, display_name, category, tier,
                     supports_audio_input, supports_audio_output,
                     supports_text_input, supports_text_output,
                     supports_reasoning, enabled, recommended, sort_order,
                     created_at, updated_at)
                VALUES
                    ('openai', :model_id, :display_name, 'realtime', :tier,
                     true, true, true, true,
                     :supports_reasoning, false, false, 100,
                     NOW(), NOW())
                ON CONFLICT (provider, model_id) DO NOTHING
            """),
            {
                "model_id": model_id,
                "display_name": model_id,
                "tier": "growth",
                "supports_reasoning": False,
            },
        )
        if result.rowcount:
            inserted += 1

    await db.commit()
    return {"status": "synced", "inserted": inserted, "total_openai_realtime": len(realtime_ids)}


# ── Industry Playbooks ───────────────────────────────────────────────

@router.get("/playbooks")
async def list_playbooks(
    _user: AuthUser = Depends(require_admin),
):
    """Return available industry playbooks."""
    from app.services.playbooks import PLAYBOOKS
    return [
        {"name": pb.name, "slug": pb.slug}
        for pb in PLAYBOOKS.values()
    ]


@router.post("/playbooks/{tenant_id}/apply")
async def apply_playbook_endpoint(
    tenant_id: str,
    body: dict,
    _user: AuthUser = Depends(require_tenant_access),
    db: AsyncSession = Depends(get_db),
):
    """Apply an industry playbook to a tenant."""
    from app.services.playbooks import apply_playbook
    slug = body.get("slug", "")
    if not slug:
        raise HTTPException(status_code=400, detail="Missing slug")
    try:
        result = await apply_playbook(db, tenant_id, slug)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
