"""POD6 AI Voice Agent — FastAPI entry point.

Multi-tenant voice receptionist replacing 14 n8n workflows.
Handles both HTTP (Starter tier) and WebSocket (Growth/Pro tier) paths.
"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.client import shutdown_db
from app.routes import voice, websocket

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("POD6 Voice Agent starting — base_url=%s", settings.base_url)
    yield
    logger.info("Shutting down…")
    await shutdown_db()


app = FastAPI(
    title="POD6 AI Voice Agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ─────────────────────────────────────────────────────────

app.include_router(voice.router)
app.include_router(websocket.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "pod6-voice-agent"}
