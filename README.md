# POD6 AI Voice Agent

Multi-tenant AI voice receptionist built with Python FastAPI, replacing 14 n8n workflows. Handles inbound phone calls with real-time speech-to-text, AI conversation, and text-to-speech — all streamed over WebSocket for sub-second latency.

## Stack

| Component | Technology |
|-----------|-----------|
| Web framework | FastAPI + uvicorn |
| Telephony | Twilio Media Streams (WebSocket) |
| Speech-to-Text | Cartesia Ink (WebSocket) |
| Text-to-Speech | Cartesia Sonic 3 (WebSocket) |
| AI Brain | GPT-4 Turbo (OpenAI) |
| Database | Supabase PostgreSQL (12 tables, multi-tenant) |
| Deployment | Railway (auto-deploy from GitHub) |

## Architecture

```
Inbound Call → Twilio
                 │
                 ▼
          ┌─────────────┐
          │  FastAPI     │
          │  /incoming   │
          └──────┬───────┘
                 │
        ┌────────┴────────┐
        ▼                 ▼
   Starter Tier      Growth/Pro Tier
   (HTTP path)       (WebSocket path)
        │                 │
   TwiML Gather      Twilio Media Stream
   + Say (Polly)          │
        │            ┌────┴────┐
        │            ▼         ▼
        │      Cartesia    Cartesia
        │      Ink (STT)   Sonic 3 (TTS)
        │            │         ▲
        │            ▼         │
        └──────► GPT-4 Turbo ─┘
                     │
                 Supabase DB
```

### Tier-Based Routing

- **Starter** — HTTP path using TwiML `<Gather>`/`<Say>` with Amazon Polly. No WebSocket cost.
- **Growth / Pro** — WebSocket path using Twilio `<Connect><Stream>` with Cartesia STT/TTS for real-time bidirectional audio.

## Features

- **Multi-tenant** — tenant resolved by phone number, all config loaded from `account_settings` table
- **Caller memory** — long-term memory with privacy tiers (safe/protected), 90-day expiry, GDPR forget-me
- **FAQ matching** — Dice bigram similarity checks FAQ table before calling GPT-4
- **Post-call processing** — GPT-4 fact extraction, customer upsert, conversation logging
- **Business hours** — per-tenant timezone and day-of-week configuration
- **PII masking** — SSN, credit cards, emails, account numbers redacted before DB writes
- **Action tags** — `[END_CALL]`, `[TRANSFER]`, `[BOOK]`, `[CONSENT_YES/NO]`, `[FORGET_ME]`
- **Analytics** — event logging on all call lifecycle events
- **Voicemail** — after-hours recording with email notification

## Project Structure

```
app/
├── main.py                  # FastAPI entry point + /health
├── config.py                # Environment settings (Pydantic)
├── db/
│   ├── client.py            # Async SQLAlchemy + asyncpg pool
│   └── queries.py           # All SQL queries (tenant-aware)
├── models/
│   └── schemas.py           # Pydantic models
├── services/
│   ├── llm.py               # GPT-4 Turbo (chat, streaming, extraction)
│   ├── tts.py               # Cartesia Sonic 3 TTS WebSocket
│   ├── stt.py               # Cartesia Ink STT WebSocket
│   ├── faq.py               # FAQ bigram matching
│   ├── pii.py               # PII masking
│   └── business_hours.py    # Timezone-aware hours check
├── routes/
│   ├── voice.py             # HTTP voice webhooks (Twilio)
│   └── websocket.py         # WebSocket media stream handler
└── prompts/
    └── system.py            # Dynamic system prompt builder
```

## Setup

### 1. Clone and install

```bash
git clone https://github.com/YourCompany-AI-Marketing/AI-voice-receptionist.git
cd AI-voice-receptionist
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 3. Run locally

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Deploy to Railway

Push to `main` — Railway auto-deploys via Dockerfile.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/voice/incoming-call` | Twilio inbound call webhook |
| `POST` | `/voice/starter-gather` | Twilio Gather callback (Starter tier) |
| `POST` | `/voice/status-callback` | Post-call processing trigger |
| `POST` | `/voice/voicemail` | Voicemail recording handler |
| `WS` | `/ws/media-stream/{call_sid}` | Bidirectional audio stream (Growth/Pro) |

## Registered Tenants

| Tenant | Phone | Tier |
|--------|-------|------|
| 360 Group | +1-555-0100 | Starter |
| Aplus | +18665131132 | — |

## Migration Phases

- [x] **Phase 1** — Core voice loop (FastAPI, Twilio, Cartesia STT/TTS, GPT-4, multi-tenant)
- [ ] **Phase 2** — Post-call enhancements (booking, HubSpot sync, SMS/email follow-up)
- [ ] **Phase 3** — Booking + transfer (Google Calendar, hunt groups)
- [ ] **Phase 4** — SMS + WhatsApp channels
- [ ] **Phase 5** — Starter tier HTTP path polish

## License

Private — 360 Group / YourCompany. All rights reserved.
