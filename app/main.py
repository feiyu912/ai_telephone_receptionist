"""AI Telephone Receptionist — FastAPI entry point.

Multi-tenant AI voice receptionist.
Handles voice (HTTP + WebSocket), SMS, WhatsApp, and admin API.
"""

import asyncio
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.db.client import get_session_factory, shutdown_db
from app.routes import admin, auth, oauth, preview, sms, token, voice, websocket, whatsapp
from app.services.cleanup import cleanup_loop

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def _warmup_db() -> None:
    """Open a DB connection at startup so the first call doesn't pay
    TLS+pool+Supabase-resume cost inside Twilio's 15s webhook timeout."""
    try:
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(text("SELECT 1"))
        logger.info("DB warmup ok")
    except Exception as exc:
        logger.warning("DB warmup failed (will retry on first request): %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AI Telephone Receptionist starting — base_url=%s", settings.base_url)
    await _warmup_db()
    cleanup_task = asyncio.create_task(cleanup_loop())
    yield
    logger.info("Shutting down…")
    cleanup_task.cancel()
    await shutdown_db()


app = FastAPI(
    title="AI Telephone Receptionist",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ─────────────────────────────────────────────────────────

app.include_router(voice.router)
app.include_router(websocket.router)
app.include_router(token.router)
app.include_router(sms.router)
app.include_router(whatsapp.router)
app.include_router(admin.router)
app.include_router(preview.router)
app.include_router(oauth.router)
app.include_router(auth.router)


@app.get("/")
@app.head("/")
@app.get("/health")
async def health():
    return {"status": "ok", "service": "voz-alta-ai", "version": "0.2.0"}


@app.get("/health/deep")
async def health_deep():
    """DB-touching health check. Point an external uptime pinger here
    (e.g. UptimeRobot every 5 min) to keep the Supabase pool warm so the
    first voice call doesn't hit Twilio's 15s webhook timeout."""
    factory = get_session_factory()
    async with factory() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ok", "db": "ok"}
