# AI Telephone Receptionist — Dashboard

Multi-tenant admin dashboard for the AI Telephone Receptionist voice receptionist platform.

| Environment | URL | Notes |
|---|---|---|
| Production | https://app.your-domain.com | Hostinger VPS, Docker Compose. Same-site cookie with the API at `api.your-domain.com`. |
| Staging | http://localhost:3000 → https://ai-voice-receptionist-36vr.onrender.com | Local Next.js dev server pointed at the Render staging API. **Cross-origin** — needs `COOKIE_SAMESITE=none` on the API. |

## Stack

- **Framework**: Next.js 16 (App Router) + React 19
- **Styling**: TailwindCSS v4 with NextAdmin / TailAdmin design tokens (ported via `@theme` in `globals.css`); shadcn/ui primitives still used for Tabs / Select / Dialog / Switch / Card / Input where the NextAdmin components don't exist
- **Charts**: Recharts (brand-tinted)
- **Icons**: lucide-react
- **State**: React context (`useAuth`, `useTenant`)
- **Build**: `output: standalone` Next.js build → multi-stage Dockerfile (~150MB image)

## Roles

| Role | What they see |
|---|---|
| **Admin** | All tenants + admin pages (System Health, All Tenants) + tenant switcher in the header |
| **Client** | Scoped to their own tenant only — no switcher, limited settings |

Role is read from the `dashboard_users.role` column in Supabase (not inferred from email). Seed users via `scripts/seed_dashboard_users.py`. Passwords are bcrypt-hashed; login is rate-limited per IP and backed by HMAC-signed session cookies. Set `AUTH_SECRET` + `COOKIE_SECURE=true` in production. For cross-origin staging set `COOKIE_SAMESITE=none` on the API.

## Pages

| Path | Role | Purpose |
|---|---|---|
| `/login` | Public | Sign in (full-screen split layout: form left, hero illustration right) |
| `/overview` | Both | Per-tenant analytics — 4 OverviewCards + event pie chart + Quick Stats |
| `/calls` | Both | Call history (from `voice_sessions`), status pills (active/closed/voicemail/transferred) |
| `/customers` | Both | Customer list with initials avatars |
| `/faq` | Both | FAQ CRUD with category pills + edit dialog |
| `/settings` | Both | 5-tab tenant config (General / Voice & Greetings / Hours / Integrations / Advanced) — admin sees `tier` field |
| `/integrations` | Both | Service-status cards: HubSpot + Microsoft (live OAuth) + Twilio + OpenAI + Cartesia + Supabase |
| `/tenants` | Admin only | All-tenants OverviewCard aggregate + per-tenant table; click row to switch tenant |
| `/system` | Admin only | API + Supabase health checks + service endpoint table |

## Project Structure

```
dashboard/src/
├── app/
│   ├── (auth)/
│   │   ├── layout.tsx                  # Pass-through wrapper
│   │   └── login/page.tsx              # Split layout login + SVG illustration
│   ├── (dashboard)/
│   │   ├── layout.tsx                  # SidebarProvider + TenantProvider + Sidebar + Header
│   │   ├── overview/page.tsx
│   │   ├── calls/page.tsx
│   │   ├── customers/page.tsx
│   │   ├── faq/page.tsx
│   │   ├── settings/page.tsx
│   │   ├── integrations/page.tsx
│   │   ├── tenants/page.tsx            # Admin only (gated client-side)
│   │   └── system/page.tsx             # Admin only (gated client-side)
│   ├── globals.css                     # NextAdmin @theme tokens + shadcn bridge
│   ├── layout.tsx                      # Root layout (theme + auth providers)
│   └── page.tsx                        # Redirects to /login or /overview
├── components/
│   ├── Layouts/
│   │   ├── sidebar/
│   │   │   ├── index.tsx               # Aside with profile + sign-out + nav groups
│   │   │   ├── sidebar-context.tsx     # SidebarProvider, useSidebarContext
│   │   │   ├── menu-item.tsx           # cva-styled menu link/button
│   │   │   ├── icons.tsx               # ChevronUp + ArrowLeftIcon
│   │   │   └── data/index.ts           # NAV_DATA (sections + items, adminOnly flag)
│   │   └── header/
│   │       ├── index.tsx               # Sticky bar: title + search + theme/bell/user
│   │       ├── icons.tsx               # MenuIcon + SearchIcon + ChevronUpIcon
│   │       ├── theme-toggle.tsx        # NextAdmin pill toggle
│   │       ├── notification.tsx        # Bell + dropdown
│   │       ├── tenant-switcher.tsx     # Admin-only Building2 dropdown
│   │       └── user-info.tsx           # Avatar + user dropdown (Profile / Integrations / Logout)
│   ├── Auth/
│   │   └── login-illustration.tsx      # Inline SVG — phone + sound waves + 4 mock cards
│   ├── dashboard/
│   │   ├── overview-card.tsx           # NextAdmin-style icon + value + growth-rate KPI card
│   │   ├── error-card.tsx              # Branded error block with retry
│   │   └── loading.tsx                 # PageSpinner + PanelCard helpers
│   ├── layout/
│   │   └── theme-provider.tsx          # next-themes wrapper (singleton)
│   ├── logo.tsx                        # AI Telephone Receptionist brand mark
│   └── ui/                             # shadcn primitives (Card, Dialog, Tabs, Switch, Select, …)
│       └── dropdown.tsx                # NextAdmin-style Dropdown (used by Header pieces)
├── hooks/
│   ├── use-mobile.ts                   # useSyncExternalStore matchMedia(<850px)
│   └── use-click-outside.ts            # Generic outside-click handler
└── lib/
    ├── api.ts                          # API client (uses NEXT_PUBLIC_API_URL or your-domain.com)
    ├── auth.tsx                        # AuthProvider + useAuth (admin/client roles)
    ├── tenant.tsx                      # TenantProvider + useTenant + useTenantId
    └── utils.ts                        # cn() Tailwind class merger
```

## Local Development

```bash
npm install
npm run dev
# → http://localhost:3000
```

By default the dashboard talks to **production** API at `https://api.your-domain.com`. To point at staging or a local API, create `dashboard/.env.local`:

```bash
# .env.local — gitignored, per-developer

# Render staging API
NEXT_PUBLIC_API_URL=https://ai-voice-receptionist-36vr.onrender.com

# OR local FastAPI
# NEXT_PUBLIC_API_URL=http://localhost:8000
```

Restart `npm run dev` after editing — Next.js only reads `.env.local` at startup.

### Cross-origin login (staging)

When `localhost:3000` talks to `*.onrender.com`, the browser treats it as cross-origin and **drops the session cookie unless** the API responds with `Set-Cookie: …; SameSite=None; Secure`. On the Render service set:

```
COOKIE_SECURE=true          # always on Render (HTTPS)
COOKIE_SAMESITE=none        # required for cross-origin; default is "lax"
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

Hostinger production keeps the default `COOKIE_SAMESITE=lax` because dashboard + API share the `your-domain.com` parent domain (same-site).

After login fails with 401: open DevTools → Application → Cookies → delete the API origin's cookies, hard-refresh, retry. Old `SameSite=Lax` cookies cached before the env change are silently dropped.

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
4. Add an entry to `src/components/Layouts/sidebar/data/index.ts` (in the right `NavSection`; set `adminOnly: true` on the section if it should be admin-gated)
5. For admin-only pages, also gate at the page level with a `useAuth()` role check + redirect (defense in depth)

## Notes

- This Next.js version has breaking changes from training data — see `AGENTS.md` and check `node_modules/next/dist/docs/` for current APIs.
- Use `React.SubmitEvent<HTMLFormElement>` for form handlers — `React.FormEvent` is deprecated in this build.
- Effects that legitimately call setState (e.g. data-fetching `useEffect(load, [load])`) carry an inline `// eslint-disable-next-line react-hooks/set-state-in-effect`. The `useIsMobile` hook is built on `useSyncExternalStore` to avoid the rule entirely.
