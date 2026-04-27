# AI Telephone Receptionist — Dashboard

Multi-tenant admin dashboard for the AI Telephone Receptionist voice receptionist platform.

- **Production:** [https://app.your-domain.com](https://app.your-domain.com)
- **API backend:** [https://api.your-domain.com](https://api.your-domain.com)

## Stack

- **Framework:** Next.js 16 (App Router) + React 19
- **Styling:** TailwindCSS + shadcn/ui
- **Charts:** Recharts
- **Icons:** lucide-react
- **State:** React context (auth + tenant)
- **Deployment:** Docker (multi-stage build with `output: standalone`)

## Roles

| Role | What they see |
|---|---|
| **Admin** | All tenants + admin pages (System Health, All Tenants) + tenant switcher |
| **Client** | Scoped to their own tenant only — no switcher, limited settings |

Role is read from the `dashboard_users.role` column in Supabase (not inferred from email). Seed users via `scripts/seed_dashboard_users.py`. Passwords are bcrypt-hashed; login is rate-limited per IP and backed by HMAC-signed session cookies. Set `AUTH_SECRET` + `COOKIE_SECURE=true` in production.

## Pages

| Path | Role | Purpose |
|---|---|---|
| `/login` | Public | Sign in |
| `/overview` | Both | Per-tenant analytics summary |
| `/calls` | Both | Call history (from `voice_sessions`) |
| `/customers` | Both | Customer list |
| `/faq` | Both | FAQ CRUD |
| `/settings` | Both | Tenant config (admin sees more fields like `tier`) |
| `/integrations` | Both | Live OAuth status (HubSpot, Microsoft Graph, Twilio, OpenAI) |
| `/settings` (Integrations tab) | Both | Per-tenant credentials: Outlook mailbox, Twilio (SID + Auth Token + API Key + TwiML App), HubSpot token. Secret fields render as `••••` once saved and are server-redacted on GET. |
| `/tenants` | Admin only | All Tenants overview with aggregate stats |
| `/system` | Admin only | System Health (API, DB, Twilio, OpenAI) |

## Project Structure

```
src/
├── app/
│   ├── (auth)/login/         # Login page
│   ├── (dashboard)/
│   │   ├── overview/
│   │   ├── calls/
│   │   ├── customers/
│   │   ├── faq/
│   │   ├── settings/
│   │   ├── integrations/
│   │   ├── tenants/          # Admin only
│   │   ├── system/           # Admin only
│   │   └── layout.tsx        # Wraps everything in TenantProvider
│   ├── layout.tsx            # Root layout (theme + auth)
│   └── page.tsx              # Redirects to /login or /overview
├── components/
│   ├── layout/
│   │   ├── sidebar.tsx       # Navigation (admin sees extra items)
│   │   ├── topbar.tsx        # Tenant switcher (admin) or current tenant label (client)
│   │   └── right-panel.tsx   # Recent calls + customers
│   ├── dashboard/
│   │   └── stat-card.tsx
│   └── ui/                   # shadcn/ui primitives
└── lib/
    ├── api.ts                # API client + helper functions
    ├── auth.tsx              # AuthProvider + useAuth
    ├── tenant.tsx            # TenantProvider + useTenant + useTenantId
    └── utils.ts              # Tailwind class merging
```

## Local Development

```bash
npm install
npm run dev
# → http://localhost:3000
```

By default the dashboard talks to production API at `https://api.your-domain.com`.

To point at a local API:

```bash
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Production Build

```bash
npm run build
npm start
```

The Dockerfile uses `output: standalone` from `next.config.ts` to produce a minimal runtime image (~150MB).

## Deployment

The dashboard is deployed via Docker Compose alongside the API on the Hostinger VPS. See [`../deploy/DEPLOY.md`](../deploy/DEPLOY.md) for details.

To update production:

```bash
# On the VPS:
cd /opt/AI-voice-receptionist
git pull
cd deploy
docker compose up -d --build dashboard
```

## Adding a New Page

1. Create `src/app/(dashboard)/yourpage/page.tsx`
2. Use `useTenantId()` to get the current tenant context
3. Call API helpers from `@/lib/api` (e.g., `getCalls(tenantId)`)
4. Add to `src/components/layout/sidebar.tsx` navigation
5. For admin-only pages, gate with `useAuth()` role check + redirect

## Notes

- This Next.js version has breaking changes from training data — see `AGENTS.md` and check `node_modules/next/dist/docs/` for current APIs.
- Use `React.SubmitEvent<HTMLFormElement>` not the deprecated `React.FormEvent` for form handlers.
