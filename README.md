# AI Telephone Receptionist

24/7 multi-tenant AI voice receptionist. Python FastAPI backend + Next.js dashboard, deployed on Hostinger VPS at `your-domain.com`.

- **API:** [https://api.your-domain.com](https://api.your-domain.com)
- **Dashboard:** [https://app.your-domain.com](https://app.your-domain.com)

## Stack

| Component | Technology |
|---|---|
| Web framework | Python FastAPI + uvicorn |
| Telephony | Twilio (Voice + SMS + WhatsApp + Media Streams) |
| Voice AI — Starter | GPT-5-mini + Twilio Polly TTS (HTTP TwiML path, ~3-5s latency) |
| Voice AI — Growth/Pro | **OpenAI Realtime (`gpt-realtime-mini`)** — STT + LLM + TTS in one, sub-second latency, built-in barge-in |
| Function calling | OpenAI tools (6 functions) |
| CRM | HubSpot (contact + engagement note + meeting; per-tenant `hubspot_access_token` with a global env fallback) |
| Calendar + Email | Microsoft Graph (per-tenant `calendar_email` / `sender_email` columns; falls back to the global `MS_CALENDAR_EMAIL` / `MS_SENDER_EMAIL` env vars when a tenant hasn't configured its own) |
| Database | Supabase PostgreSQL (19 tables, 11 views, multi-tenant via `tenant_id`) |
| Dashboard | Next.js 16 + React 19 + TailwindCSS v4 + NextAdmin/TailAdmin design tokens (`@theme`) + shadcn/ui primitives |
| Reverse proxy | Nginx (Docker, SSL via Let's Encrypt) |
| Deployment | Hostinger VPS (Docker Compose) |

## Architecture

```
                 Inbound Call → Twilio
                          │
                          ▼
                ┌──────────────────────┐
                │  Hostinger VPS        │
                │  api.your-domain.com    │
                │  ┌─────────────────┐  │
                │  │ Nginx (SSL)     │  │
                │  └────────┬────────┘  │
                │           │           │
                │  ┌────────▼────────┐  │
                │  │ FastAPI (api)   │──┼──→  Supabase
                │  │ /voice          │  │     PostgreSQL
                │  │ /sms            │  │
                │  │ /whatsapp       │  │
                │  │ /admin          │  │
                │  └────────┬────────┘  │
                │           │           │
                └───────────┼───────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
  Starter tier        Growth/Pro tier      Background tasks
  (TwiML Gather       (OpenAI Realtime     (memory cleanup
   + Polly Say        WebSocket bridge)     cron, post-call
   loop)                                    processing)
```

## Features

### Voice Agent
- **Multi-tenant** — tenant resolved by called phone number, full config from `account_settings`
- **Sub-second latency (Growth/Pro)** — OpenAI Realtime handles STT + LLM + TTS in one connection
- **Barge-in** — caller can interrupt mid-sentence (built into Realtime API)
- **Caller memory** — long-term facts with privacy tiers (safe/protected) + 90-day expiry + GDPR forget-me
- **Identity verification** — protected memory (email, full name, etc.) is locked behind a `verify_identity` tool that requires the caller to confirm BOTH name AND email; only on success does the AI get to reference stored details
- **Industry playbooks** — one-click HVAC, dental, legal, and plumbing templates that overwrite the system prompt, greetings, and bulk-insert preset FAQs
- **FAQ matching** — Dice bigram similarity + FAQ context injected into Realtime system prompt
- **Function calling** — 7 tools: `end_call`, `transfer_to_human`, `book_appointment`, `save_caller_memory`, `set_memory_consent`, `forget_caller`, `verify_identity`
- **Live transfer** — Growth/Pro calls hand off via Twilio REST API redirect to a hunt-group `<Dial>` TwiML; Starter calls return the TwiML inline
- **End call hangup** — when AI calls `end_call`, the call automatically terminates after the farewell
- **Call recording with compliance disclosure** — per-tenant toggle in Settings; when enabled, Twilio records the call and a customizable disclosure message is played before the greeting
- **Voicemail transcription** — when a caller leaves a voicemail (no user turns detected), the recording is downloaded, transcribed via OpenAI Whisper, and delivered by email with both the recording link and full text transcript
- **Email captured during calls** — confirmation SMS sent post-call so caller can correct typos
- **Booking info collection via SMS** — if a caller wants to book but doesn't provide name/email during the call, the system sends an SMS asking for the missing info, parses the reply, and automatically creates the Outlook Calendar event + HubSpot meeting
- **Post-call processing** — GPT fact extraction → customer upsert → HubSpot sync → optional SMS/email follow-up
- **Hunt group transfer** — sequential dial to configured numbers
- **24/7 operation** — no business hours restriction

### Channels
- **Voice** — inbound calls via Twilio (Starter HTTP path + Growth/Pro WebSocket path)
- **SMS** — inbound SMS with TCPA compliance (STOP/HELP/START + quiet hours 9pm-8am + 320 char cap)
- **WhatsApp** — inbound WhatsApp with same compliance model

### Integrations
- **HubSpot CRM** — contact search/create + engagement notes + meeting auto-creation. Per-tenant `hubspot_access_token`; falls back to the global env var.
- **Outlook Calendar** — appointment booking via Microsoft Graph (`Calendars.ReadWrite`). Per-tenant `calendar_email` column; falls back to `MS_CALENDAR_EMAIL`.
- **Outlook Email** — voicemail alerts, follow-up emails, booking confirmations (`Mail.Send`). Per-tenant `sender_email` column; falls back to `MS_SENDER_EMAIL`.
- **SMS follow-up** — post-call summary or booking link via Twilio. Per-tenant `twilio_account_sid` / `twilio_auth_token`; falls back to global `TWILIO_*`.

### Multi-tenant Dashboard (`app.your-domain.com`)

Roles are stored on each user row in the `dashboard_users` Supabase table
(`role = 'admin' | 'client'`), not inferred from email domain.

**Admin role:**
- All Tenants overview (aggregate stats)
- System Health monitoring
- Tenant switcher (browse/edit any tenant)

**Client role:**
- Scoped to their own tenant only
- Manage greetings, system prompt, FAQ, voice
- View their calls, customers, analytics

### Background Tasks
- **Memory cleanup cron** — daily delete of expired memories + GDPR forget-me processing
- **PII masking** — SSN, credit cards, emails, account numbers redacted before DB writes

## Project Structure

```
.
├── app/                          # Python FastAPI backend
│   ├── main.py                   # FastAPI entry + cleanup cron + route registration
│   ├── config.py                 # Pydantic settings (env vars)
│   ├── db/
│   │   ├── client.py             # Async SQLAlchemy + asyncpg pool
│   │   └── queries.py            # All SQL queries (tenant-aware)
│   ├── models/schemas.py         # Pydantic models
│   ├── services/
│   │   ├── llm.py                # GPT-5-mini chat + tools + fact extraction
│   │   ├── realtime.py           # OpenAI Realtime helper
│   │   ├── transcription.py      # OpenAI Whisper voicemail transcription
│   │   ├── tts.py                # Cartesia SDK (fallback)
│   │   ├── stt.py                # Cartesia SDK (fallback)
│   │   ├── sms.py                # Twilio SMS sending
│   │   ├── hubspot.py            # Contact + note + meeting
│   │   ├── calendar.py           # Outlook Calendar (Microsoft Graph)
│   │   ├── email.py              # Outlook email (Microsoft Graph)
│   │   ├── email_confirm.py      # SMS-based email spelling confirmation
│   │   ├── booking_collect.py    # SMS-based booking info collection (name/email)
│   │   ├── faq.py                # FAQ bigram matching
│   │   ├── pii.py                # PII masking
│   │   ├── business_hours.py     # Timezone-aware hours check
│   │   └── cleanup.py            # Memory expiry + forget-me cron
│   ├── routes/
│   │   ├── voice.py              # Voice webhooks (Starter HTTP + status callback)
│   │   ├── websocket.py          # OpenAI Realtime WebSocket bridge (Growth/Pro)
│   │   ├── token.py              # Twilio browser SDK access token
│   │   ├── sms.py                # SMS inbound + TCPA compliance + email-confirm replies
│   │   ├── whatsapp.py           # WhatsApp inbound + compliance
│   │   ├── admin.py              # /admin/{tenants,settings,faq,customers,calls,analytics}
│   │   ├── oauth.py              # /oauth/{hubspot,microsoft} placeholder routes
│   │   └── preview.py            # /voice/preview voice TTS sample
│   └── prompts/system.py         # Dynamic system prompt builder
│
├── dashboard/                    # Next.js 16 admin dashboard (NextAdmin design tokens)
│   ├── src/
│   │   ├── app/
│   │   │   ├── (auth)/login/                  # Split-layout login + SVG illustration
│   │   │   ├── (dashboard)/                   # Authenticated pages
│   │   │   │   ├── layout.tsx                 # SidebarProvider + TenantProvider
│   │   │   │   ├── overview/                  # KPI cards + event pie chart
│   │   │   │   ├── calls/                     # Call history table
│   │   │   │   ├── customers/                 # Customer list table
│   │   │   │   ├── faq/                       # FAQ CRUD
│   │   │   │   ├── settings/                  # Tenant config (5 tabs)
│   │   │   │   ├── integrations/              # Live OAuth status cards
│   │   │   │   ├── tenants/                   # Admin: all tenants
│   │   │   │   └── system/                    # Admin: system health
│   │   │   ├── globals.css                    # NextAdmin @theme + shadcn token bridge
│   │   │   └── layout.tsx                     # Root layout (theme + auth)
│   │   ├── components/
│   │   │   ├── Layouts/sidebar/               # Sidebar + nav data + context
│   │   │   ├── Layouts/header/                # Sticky header (search/theme/bell/tenant/user)
│   │   │   ├── Auth/login-illustration.tsx    # Inline SVG hero for login
│   │   │   ├── dashboard/                     # OverviewCard + PanelCard + ErrorCard
│   │   │   └── ui/                            # shadcn primitives + NextAdmin Dropdown
│   │   ├── hooks/                             # use-mobile (useSyncExternalStore) + use-click-outside
│   │   └── lib/
│   │       ├── api.ts                         # API client (NEXT_PUBLIC_API_URL)
│   │       ├── auth.tsx                       # Auth context (admin vs client role)
│   │       └── tenant.tsx                     # Tenant context (switcher for admin)
│   └── Dockerfile                             # Multi-stage Next.js standalone build
│
├── deploy/                       # Hostinger VPS deployment
│   ├── docker-compose.yml        # api + dashboard + nginx + certbot
│   ├── nginx.conf                # SSL termination + WebSocket proxy
│   ├── install.sh                # One-shot installer (Docker + UFW + SSL)
│   └── DEPLOY.md                 # Step-by-step guide
│
├── scripts/                      # One-off scripts + migrations
│   ├── setup_aplus.py            # TenantB tenant provisioning
│   ├── migrate_admin_alerts.py   # Add alert columns to account_settings
│   ├── migrate_tenant_360dmmc.py # Fix tenant_id split (old → new UUID)
│
├── docs/                         # Project documentation
│   ├── STATUS.md                 # Current build status (Python/FastAPI era)
│   ├── TIER_COMPARISON.md        # Sales-facing tier breakdown
│   └── *.docx                    # Legacy n8n-era docs (kept for reference)
│
├── .env.example                  # Template for environment variables
├── Dockerfile                    # FastAPI container
└── requirements.txt              # Python dependencies
```

## Database Schema (Supabase, 19 tables + 11 views)

### Tables actively used by this project (12)

| Table | Purpose |
|---|---|
| `account_settings` | Per-tenant config (phone, tier, voice, prompts, hours, hunt group) |
| `voice_sessions` | Call sessions + incremental conversation history (jsonb) |
| `caller_memory` | Long-term facts per caller (privacy_tier, expires_at, source_channel) |
| `caller_consent` | GDPR consent + forget-me request tracking |
| `customers` | Upserted after each call (phone, name, email, key_facts) |
| `conversations` | Post-call summary (intent, outcome, sentiment) |
| `analytics_events` | Every call/SMS/booking/sync event |
| `bookings` | Appointment records linked to call sessions |
| `opt_outs` | TCPA SMS/WhatsApp opt-out tracking |
| `tenant_credentials` | Per-tenant OAuth refresh tokens (Microsoft / HubSpot) — populated when a tenant clicks Connect Outlook in the dashboard |
| `dashboard_users` | Dashboard logins (email PK, bcrypt password_hash, role, tenant_id) |
| `voice_config` | TTS voice catalog for `/voice/preview` |
| `faq_entries` | FAQ knowledge base (152 total: 121 for YourCompany, 31 for Aplus) |

### Tables shared with other YourCompany products (6)

| Table | Used By |
|---|---|
| `conversation_messages` | Web chat |
| `active_handoffs` | Web chat agent handoff |
| `leads` | Web chat lead capture |
| `widget_tenant_config` | Web chat widget |
| `analytics_daily` | Cross-product daily aggregates |
| `quiet_hours_config` | Reserved (legacy) |

### Views (11)

| View | Purpose |
|---|---|
| `caller_memory_summary` | Per-caller fact summary |
| `v_avg_call_duration` | Average call length |
| `v_booking_stats` | Booking counts by status |
| `v_call_volume_daily` | Calls per day by channel |
| `v_call_volume_hourly` | Peak hours heatmap |
| `v_caller_memory_with_consent` | Memory + consent join (privacy queries) |
| `v_intent_distribution` | inquiry / booking / support / complaint breakdown |
| `v_memory_utilization` | Memory usage stats |
| `v_outcome_breakdown` | contained / escalated / converted / abandoned |
| `v_return_caller_rate` | Returning caller percentage |
| `v_sentiment_weekly` | Weekly sentiment trend |

## Registered Tenants

| Tenant | Phone | Tier | Tenant ID |
|---|---|---|---|
| **YourCompany** | +1-555-0100 | Growth (OpenAI Realtime) | `11111111-1111-1111-1111-111111111111` |
| **TenantB** | +1-555-0101 | Starter (TwiML + Polly) | `22222222-2222-2222-2222-222222222222` |

## Local Development

### 1. Install Python dependencies

```bash
git clone https://github.com/YourCompany-AI-Marketing/AI-voice-receptionist.git
cd AI-voice-receptionist
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with real credentials (see Setup section)
```

### 3. Run the API locally

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Run the dashboard locally

```bash
cd dashboard
npm install
npm run dev
# → http://localhost:3000
```

## Environments

| Environment | Where | Purpose |
|---|---|---|
| **Production** | Hostinger VPS at `api.your-domain.com` (Docker compose: api + dashboard + nginx + certbot) | Real customer calls to +1-555-0100 (YourCompany) and +1-555-0101 (Aplus) |
| **Staging** | Render at `ai-voice-receptionist-36vr.onrender.com` (auto-deploys on push to `main`, blueprint in `render.yaml`) | Browser-test calls via TwiML App `APb3b9320…`; safe for daily QA |

Real customer phone numbers route through Phone Number webhooks (prod). Browser test calls route through the TwiML App's Voice URL (staging). The two paths share the same Supabase but never collide.

## Multi-tenant credential model

Every per-tenant credential lives in Supabase `account_settings`, **not** in `.env`:

- Twilio (Account SID / Auth Token / API Key SID / API Key Secret / TwiML App SID) — used for signature validation, outbound SMS, browser Voice SDK tokens
- HubSpot (`hubspot_access_token`)
- Microsoft Graph (`sender_email` + `calendar_email` for what mailbox / calendar to use; `tenant_credentials` row holds the OAuth refresh token after a tenant clicks Connect Outlook)
- Hunt group numbers (`hunt_group_numbers` jsonb)

`.env` only holds platform-level identity:

- `DATABASE_URL` (bootstrap)
- `OPENAI_API_KEY`, `CARTESIA_API_KEY`
- `MS_CLIENT_ID` / `MS_CLIENT_SECRET` / `MS_TENANT_ID` (your Azure App publisher identity — every tenant OAuths through the same app)
- `AUTH_SECRET`, `COOKIE_SECURE`, `BASE_URL`, `DASHBOARD_URL`, `CORS_ORIGINS`, `HOST`, `PORT`, `LOG_LEVEL`

When a per-tenant column is NULL, the service falls back to the matching env var. Once all tenants populate their own values, the env-level Twilio / HubSpot / MS-mailbox vars can be deleted entirely.

## Production Deployment

The VPS deployment lives in `deploy/` and is managed by Docker Compose. Push to `main` and pull on the VPS to update.

```bash
# On the VPS:
cd /opt/AI-voice-receptionist
git pull
cd deploy
docker compose up -d --build
```

For first-time setup, use `deploy/install.sh` — it's idempotent and handles UFW, port conflicts, Let's Encrypt certificate issuance, and the cert-renewal cron.

## Testing

The QA test plan lives at [`docs/TEST_PLAN.md`](docs/TEST_PLAN.md). It covers every MVP feature with explicit caller scripts, expected logs, and where to verify in Supabase / Outlook / HubSpot.

For first-time deployment, see [`deploy/DEPLOY.md`](deploy/DEPLOY.md).

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/voice/incoming-call` | Twilio inbound call webhook |
| `POST` | `/voice/starter-gather` | Twilio `<Gather>` callback (Starter tier) |
| `POST` | `/voice/status-callback` | Post-call processing trigger |
| `POST` | `/voice/voicemail` | Voicemail recording handler |
| `GET/POST` | `/voice/twilio-token` | Twilio Voice SDK token (browser dialer) |
| `GET` | `/voice/preview` | Voice preview TwiML |
| `WS` | `/ws/media-stream/{call_sid}` | OpenAI Realtime audio bridge (Growth/Pro) |
| `POST` | `/sms/inbound` | SMS inbound + TCPA compliance + email-confirm replies |
| `POST` | `/whatsapp/inbound` | WhatsApp inbound + compliance |
| `GET` | `/admin/tenants` | List all tenants (for admin switcher) |
| `GET/PATCH` | `/admin/settings/{tenant_id}` | Tenant config |
| `GET/POST` | `/admin/faq/{tenant_id}` | FAQ list + create |
| `PATCH/DELETE` | `/admin/faq/{tenant_id}/{id}` | FAQ edit + delete |
| `GET` | `/admin/customers/{tenant_id}` | Customer list |
| `GET` | `/admin/calls/{tenant_id}` | Call history |
| `GET` | `/admin/analytics/{tenant_id}` | Analytics summary |
| `GET` | `/oauth/status/{tenant_id}` | OAuth integration status |

## Migration Status

### Phase 1 MVP — Done ✅

- [x] Core voice loop (Starter HTTP + Growth/Pro WebSocket via OpenAI Realtime)
- [x] Multi-tenant resolution + config loading
- [x] Caller memory (privacy tiers, 90-day expiry, GDPR forget-me)
- [x] FAQ matching + Realtime prompt injection
- [x] Function calling (6 tools, end_call hangup)
- [x] Post-call fact extraction + customer upsert
- [x] SMS inbound channel + TCPA compliance (quiet hours, length cap)
- [x] WhatsApp inbound channel + compliance
- [x] HubSpot contact sync + engagement note + meeting auto-creation
- [x] Microsoft Graph email (voicemail alerts, follow-up, booking confirmation)
- [x] Outlook Calendar booking via Microsoft Graph
- [x] Email confirmation SMS flow (post-call typo correction)
- [x] Booking info collection via SMS (missing name/email → auto-create calendar event + HubSpot meeting)
- [x] Memory cleanup cron (90-day expiry + forget-me)
- [x] Admin API + multi-tenant dashboard
- [x] Hostinger VPS deployment (Docker, nginx, Let's Encrypt)
- [x] Rebrand to **AI Telephone Receptionist**

### Phase 2 — Post-Launch Optimizations

- [x] Production auth (cookie-based session login, role-based access)
- [x] GitHub Actions auto-deploy on push to `main`
- [x] Booking time-parsing improvements (`dateparser` for "next Tuesday")
- [x] Booking timezone fix (Microsoft Graph returns UTC, treated as schedule timezone)
- [x] Per-tenant OAuth tokens (HubSpot + Outlook tied to each client's account)
- [x] Industry playbooks (HVAC, dental, legal, plumbing)
- [x] Call recording with compliance disclosure
- [x] Admin alerts (new lead, booking, voicemail, usage threshold)
- [x] Voicemail transcription (OpenAI Whisper) + email delivery with recording link
- [ ] Stripe billing + minute usage tracking

## License

Private — YourCompany. All rights reserved.
