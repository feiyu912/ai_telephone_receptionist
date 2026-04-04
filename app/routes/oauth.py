"""OAuth flows for tenant credential management.

Handles OAuth2 authorization code flow for:
- HubSpot CRM
- Microsoft Outlook (Graph API)

Each tenant connects their own accounts through these endpoints.
Tokens are stored encrypted in the tenant_credentials table.
"""

from __future__ import annotations
import json
import logging
import secrets
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, JSONResponse
import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.client import get_db
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/oauth", tags=["oauth"])


# ── HubSpot OAuth ──────────────────────────────────────────────────

@router.get("/hubspot/authorize/{tenant_id}")
async def hubspot_authorize(tenant_id: str):
    """Redirect tenant to HubSpot OAuth consent screen."""
    settings = get_settings()
    state = f"{tenant_id}:{secrets.token_hex(16)}"
    url = (
        f"https://app.hubspot.com/oauth/authorize"
        f"?client_id={settings.hubspot_client_id}"
        f"&redirect_uri={settings.base_url}/oauth/hubspot/callback"
        f"&scope=crm.objects.contacts.read%20crm.objects.contacts.write"
        f"&state={state}"
    )
    return RedirectResponse(url)


@router.get("/hubspot/callback")
async def hubspot_callback(
    code: str = "", state: str = "", error: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Handle HubSpot OAuth callback — exchange code for tokens."""
    if error:
        return JSONResponse({"error": error}, status_code=400)

    tenant_id = state.split(":")[0] if ":" in state else ""
    if not tenant_id:
        return JSONResponse({"error": "Invalid state"}, status_code=400)

    settings = get_settings()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.hubapi.com/oauth/v1/token",
            data={
                "grant_type": "authorization_code",
                "client_id": settings.hubspot_client_id,
                "client_secret": settings.hubspot_client_secret,
                "redirect_uri": f"{settings.base_url}/oauth/hubspot/callback",
                "code": code,
            },
        )

    if resp.status_code != 200:
        return JSONResponse({"error": "Token exchange failed", "detail": resp.text}, status_code=400)

    tokens = resp.json()
    await _save_credential(db, tenant_id, "hubspot", {
        "access_token": tokens.get("access_token"),
        "refresh_token": tokens.get("refresh_token"),
        "expires_in": tokens.get("expires_in"),
    })

    return JSONResponse({"status": "connected", "service": "hubspot", "tenant_id": tenant_id})


# ── Microsoft OAuth (Outlook Calendar) ─────────────────────────────

@router.get("/microsoft/authorize/{tenant_id}")
async def microsoft_authorize(tenant_id: str):
    """Redirect tenant to Microsoft OAuth consent screen."""
    settings = get_settings()
    state = f"{tenant_id}:{secrets.token_hex(16)}"
    url = (
        f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
        f"?client_id={settings.ms_client_id}"
        f"&response_type=code"
        f"&redirect_uri={settings.base_url}/oauth/microsoft/callback"
        f"&scope=Calendars.ReadWrite%20offline_access"
        f"&state={state}"
    )
    return RedirectResponse(url)


@router.get("/microsoft/callback")
async def microsoft_callback(
    code: str = "", state: str = "", error: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Handle Microsoft OAuth callback."""
    if error:
        return JSONResponse({"error": error}, status_code=400)

    tenant_id = state.split(":")[0] if ":" in state else ""
    if not tenant_id:
        return JSONResponse({"error": "Invalid state"}, status_code=400)

    settings = get_settings()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            data={
                "grant_type": "authorization_code",
                "client_id": settings.ms_client_id,
                "client_secret": settings.ms_client_secret,
                "redirect_uri": f"{settings.base_url}/oauth/microsoft/callback",
                "code": code,
                "scope": "Calendars.ReadWrite offline_access",
            },
        )

    if resp.status_code != 200:
        return JSONResponse({"error": "Token exchange failed", "detail": resp.text}, status_code=400)

    tokens = resp.json()
    await _save_credential(db, tenant_id, "microsoft", {
        "access_token": tokens.get("access_token"),
        "refresh_token": tokens.get("refresh_token"),
        "expires_in": tokens.get("expires_in"),
    })

    return JSONResponse({"status": "connected", "service": "microsoft", "tenant_id": tenant_id})


# ── Credential Storage ─────────────────────────────────────────────

async def _save_credential(db: AsyncSession, tenant_id: str, service: str, tokens: dict):
    """Save or update OAuth credentials for a tenant."""
    await db.execute(
        text("""
            INSERT INTO tenant_credentials (tenant_id, service, credentials, created_at, updated_at)
            VALUES (:tid, :service, CAST(:creds AS jsonb), NOW(), NOW())
            ON CONFLICT (tenant_id, service)
            DO UPDATE SET credentials = CAST(:creds AS jsonb), updated_at = NOW()
        """),
        {"tid": tenant_id, "service": service, "creds": json.dumps(tokens)},
    )
    await db.commit()


async def get_credential(db: AsyncSession, tenant_id: str, service: str) -> dict | None:
    """Load OAuth credentials for a tenant."""
    result = await db.execute(
        text("SELECT credentials FROM tenant_credentials WHERE tenant_id = :tid AND service = :service"),
        {"tid": tenant_id, "service": service},
    )
    row = result.scalar()
    return row if isinstance(row, dict) else None


# ── Credential status endpoint ─────────────────────────────────────

@router.get("/status/{tenant_id}")
async def credential_status(tenant_id: str, db: AsyncSession = Depends(get_db)):
    """Check which services a tenant has connected."""
    result = await db.execute(
        text("SELECT service, updated_at FROM tenant_credentials WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )
    services = {}
    for row in result.mappings().all():
        services[row["service"]] = {"connected": True, "updated_at": str(row["updated_at"])}

    for svc in ["hubspot", "microsoft"]:
        if svc not in services:
            services[svc] = {"connected": False}

    return services
