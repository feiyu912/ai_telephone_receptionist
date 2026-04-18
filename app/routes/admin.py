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
    hubspot_access_token: str | None = None


# Columns that must never leave the server as plaintext. GET replaces them
# with a `<field>_set: bool` marker; PATCH accepts them but treats an empty
# string as "no change" so an unedited dashboard form never wipes them.
_SECRET_FIELDS = ("twilio_auth_token", "hubspot_access_token")


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
