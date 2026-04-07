# POD6 AI Voice Agent

Multi-tenant AI voice receptionist built with Python FastAPI, replacing 14 n8n workflows. Handles inbound phone calls with real-time AI conversation via OpenAI Realtime API for sub-second latency.

## Stack

| Component | Technology |
|-----------|-----------|
| Web framework | FastAPI + uvicorn |
| Telephony | Twilio Media Streams (WebSocket) |
| Voice AI (Growth/Pro) | OpenAI Realtime API (`gpt-realtime-mini`) — STT + LLM + TTS in one |
| Voice AI (Starter) | GPT-5-mini + Twilio Polly TTS (HTTP path) |
| Function calling | OpenAI tools (6 functions) |
| Database | Supabase PostgreSQL (18 tables, 11 views) |
| CRM | HubSpot API v3 |
| Calendar | Outlook Calendar via Microsoft Graph (planned) |
| Email | SMTP notifications |
| Deployment | Render (Docker) |

## Architecture

```
Inbound Call → Twilio
                 │
                 ▼
          ┌─────────────┐
          │   FastAPI    │
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
        │                 ▼
        │          OpenAI Realtime API
        │          (gpt-realtime-mini)
        │          ┌──────────────┐
        │          │ STT + LLM +  │
        │          │ TTS + VAD +  │
        │          │ Barge-in     │
        │          └──────────────┘
        │                 │
        └────────┬────────┘
                 ▼
            Supabase DB
```

### Tier-Based Routing

- **Starter** — HTTP path using TwiML `<Gather>`/`<Say>` with Amazon Polly. No WebSocket cost. Higher latency (~3-7s).
- **Growth / Pro** — WebSocket path using OpenAI Realtime API. Sub-second latency, built-in voice activity detection (VAD) and barge-in.

## Features

### Voice Agent
- **Multi-tenant** — tenant resolved by phone number, config loaded from `account_settings`
- **Sub-second latency** — OpenAI Realtime API handles STT + LLM + TTS in one connection
- **Barge-in** — caller can interrupt the AI mid-sentence (built into Realtime API)
- **Caller memory** — long-term memory with privacy tiers (safe/protected), 90-day expiry, GDPR forget-me
- **FAQ matching** — Dice bigram similarity checks FAQ table before AI response
- **Function calling** — 6 tools: `end_call`, `transfer_to_human`, `book_appointment`, `save_caller_memory`, `set_memory_consent`, `forget_caller`
- **Post-call processing** — GPT fact extraction, customer upsert, conversation logging
- **Hunt group transfer** — sequential dial to configured numbers
- **24/7 operation** — no business hours restriction

### Channels
- **Voice** — inbound calls via Twilio (Starter + Growth/Pro tiers)
- **SMS** — inbound SMS with TCPA compliance (STOP/HELP/START)
- **WhatsApp** — inbound WhatsApp with same compliance model

### Integrations
- **HubSpot CRM** — contact search/create + engagement notes per call
- **Email** — voicemail alerts and follow-up emails via SMTP
- **SMS follow-up** — post-call summary or booking confirmation via Twilio
- **Outlook Calendar** — appointment booking via Microsoft Graph (planned)

### Admin API
- `GET/PATCH /admin/settings/{tenant_id}` — tenant configuration
- `GET/POST/PATCH/DELETE /admin/faq/{tenant_id}` — FAQ management
- `GET /admin/customers/{tenant_id}` — customer list
- `GET /admin/calls/{tenant_id}` — call history
- `GET /admin/analytics/{tenant_id}` — analytics summary

### Background Tasks
- **Memory cleanup** — daily cron deletes expired memories (90-day) and processes GDPR forget-me requests
- **PII masking** — SSN, credit cards, emails, account numbers redacted before DB writes

## Project Structure

```
app/
├── main.py                    # FastAPI entry point + cleanup cron
├── config.py                  # Environment settings (Pydantic)
├── db/
│   ├── client.py              # Async SQLAlchemy + asyncpg pool
│   └── queries.py             # All SQL queries (tenant-aware)
├── models/
│   └── schemas.py             # Pydantic models
├── services/
│   ├── realtime.py            # OpenAI Realtime API bridge (Growth/Pro)
│   ├── llm.py                 # GPT-5-mini chat + function calling (Starter)
│   ├── tts.py                 # Cartesia TTS SDK (fallback)
│   ├── stt.py                 # Cartesia STT (fallback)
│   ├── sms.py                 # Twilio SMS sending
│   ├── hubspot.py             # HubSpot CRM sync
│   ├── email.py               # SMTP email notifications
│   ├── faq.py                 # FAQ bigram matching
│   ├── pii.py                 # PII masking
│   ├── business_hours.py      # Timezone-aware hours check
│   └── cleanup.py             # Memory expiry + forget-me cron
├── routes/
│   ├── voice.py               # HTTP voice webhooks (Twilio)
│   ├── websocket.py           # WebSocket media stream (OpenAI Realtime)
│   ├── token.py               # Twilio browser SDK token
│   ├── sms.py                 # SMS inbound + TCPA compliance
│   ├── whatsapp.py            # WhatsApp inbound + compliance
│   └── admin.py               # Tenant settings, FAQ, analytics API
└── prompts/
    └── system.py              # Dynamic system prompt builder
```

## Database Schema

### Tables (18)

| Table | Purpose | Used By |
|-------|---------|---------|
| `account_settings` | Tenant config (phone, tier, voice, prompts, hours) | Voice Agent |
| `active_handoffs` | WhatsApp agent handoff sessions | Web Chat |
| `analytics_daily` | Dashboard daily aggregates | Voice Agent (future) |
| `analytics_events` | Event logging (calls, SMS, actions) | Voice Agent |
| `bookings` | Appointment records | Voice Agent |
| `caller_consent` | Memory consent + GDPR forget-me tracking | Voice Agent |
| `caller_memory` | Long-term caller facts (privacy tiers, 90-day expiry) | Voice Agent |
| `conversation_messages` | Individual messages per conversation | Web Chat |
| `conversations` | Conversation logs (intent, outcome, sentiment) | Both |
| `customers` | Customer records (phone, name, email, key_facts) | Voice Agent |
| `faq_entries` | FAQ knowledge base (per tenant, 121 entries) | Both |
| `leads` | Lead capture and qualification | Web Chat |
| `opt_outs` | SMS/WhatsApp TCPA opt-out tracking | Voice Agent |
| `quiet_hours_config` | Quiet hours configuration | Reserved |
| `tenant_credentials` | Per-tenant OAuth tokens (Outlook, HubSpot) | Voice Agent (future) |
| `voice_config` | TTS voice options for preview | Voice Agent |
| `voice_sessions` | Call sessions + conversation history (JSONB) | Voice Agent |
| `widget_tenant_config` | Chat widget configuration | Web Chat |

### Views (11)

| View | Purpose |
|------|---------|
| `caller_memory_summary` | Per-caller fact summary |
| `v_avg_call_duration` | Average call length |
| `v_booking_stats` | Booking counts by status |
| `v_call_volume_daily` | Calls per day by channel |
| `v_call_volume_hourly` | Peak hours heatmap |
| `v_caller_memory_with_consent` | Memory + consent (privacy queries) |
| `v_intent_distribution` | Intent breakdown (inquiry/booking/support) |
| `v_memory_utilization` | Memory usage stats |
| `v_outcome_breakdown` | Call outcomes (contained/escalated/converted) |
| `v_return_caller_rate` | Returning caller percentage |
| `v_sentiment_weekly` | Weekly sentiment trend |

## Registered Tenants

| Tenant | Phone | Tier |
|--------|-------|------|
| 360 Group | +1-555-0100 | Growth |
| Aplus | +1-555-0101 | Starter |

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

### 4. Deploy to Render

Push to `main` — Render auto-deploys via Dockerfile.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Health check |
| `GET` | `/health` | Health check |
| `POST` | `/voice/incoming-call` | Twilio inbound call webhook |
| `POST` | `/voice/starter-gather` | Twilio Gather callback (Starter tier) |
| `POST` | `/voice/status-callback` | Post-call processing trigger |
| `POST` | `/voice/voicemail` | Voicemail recording handler |
| `GET/POST` | `/voice/twilio-token` | Browser SDK token for test dialer |
| `WS` | `/ws/media-stream/{call_sid}` | OpenAI Realtime audio bridge (Growth/Pro) |
| `POST` | `/sms/inbound` | SMS inbound + TCPA compliance |
| `POST` | `/whatsapp/inbound` | WhatsApp inbound + compliance |
| `GET/PATCH` | `/admin/settings/{tenant_id}` | Tenant settings |
| `GET/POST/PATCH/DELETE` | `/admin/faq/{tenant_id}` | FAQ management |
| `GET` | `/admin/customers/{tenant_id}` | Customer list |
| `GET` | `/admin/calls/{tenant_id}` | Call history |
| `GET` | `/admin/analytics/{tenant_id}` | Analytics summary |

## Migration Status (from n8n)

### Completed
- [x] Core voice loop (Starter + Growth tiers)
- [x] OpenAI Realtime API integration (sub-second latency)
- [x] Multi-tenant resolution + config loading
- [x] Caller memory (privacy tiers, expiry, GDPR)
- [x] FAQ matching (Dice bigram similarity)
- [x] Function calling (6 tools)
- [x] Post-call fact extraction + customer upsert
- [x] SMS inbound channel + TCPA compliance
- [x] WhatsApp inbound channel + compliance
- [x] HubSpot CRM sync (contact + engagement notes)
- [x] Email notifications (voicemail, follow-up)
- [x] SMS follow-up sending
- [x] Memory cleanup cron (90-day expiry + forget-me)
- [x] Admin API (settings, FAQ CRUD, analytics)
- [x] PII masking
- [x] Hunt group transfer

### Remaining
- [ ] Outlook Calendar booking (Microsoft Graph API)
- [ ] Per-tenant OAuth credential management
- [ ] Voice preview endpoint
- [ ] HubSpot meeting creation

## License

Private — 360 Group / YourCompany. All rights reserved.
