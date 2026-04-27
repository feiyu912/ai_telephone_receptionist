# AI Telephone Receptionist — Test Plan

This document tells a tester (QA / new team member) **what to test, how, what to expect, and what's NOT covered**. Read all of section 1 before running any test.

---

## 1. Prerequisites

### 1.1 Two environments

| Environment | URL | Purpose | Twilio webhook target |
|---|---|---|---|
| **Staging** (Render) | `https://ai-voice-receptionist-36vr.onrender.com` | Daily testing — safe to break | TwiML App `APb3b9320…` |
| **Production** (Hostinger) | `https://api.your-domain.com` | Real customer calls | Phone-number webhooks for +1 844 491 3441 (YourCompany) and +1 844 722 2763 (Aplus) |

> ⚠️ Staging uses the **same Supabase database** as prod (same `account_settings`, same FAQ, same `caller_memory`). Test calls will create real rows. Use a test caller name / email that's clearly fake (`testqa-<your-name>@…`) so we can clean up later.

### 1.2 Two ways to make a test call

| Method | Goes to | Pros | Cons |
|---|---|---|---|
| **Real phone** (you dial +1-555-0100 or +1-555-0101) | **Production** | end-to-end real | requires a working prod (Hostinger) |
| **Browser test page** (whatever HTML the team is using with Twilio Voice SDK) | **Staging** (because the TwiML App is pointed there) | fast, no real cost | echo if no headphones; `caller_phone` is `client:user_<timestamp>` — memory won't persist between attempts |

**Use a headset** for browser testing. Laptop speaker + mic creates an echo loop that triggers false barge-ins.

### 1.3 What to keep open during testing

- **Render Logs** — `Render dashboard → ai-voice-receptionist → Logs`. Ctrl+F for keywords below.
- **Supabase Table Editor** — open `voice_sessions`, `caller_memory`, `analytics_events`, `bookings`. Watch new rows appear after each call.
- **Outlook calendar** (`ai-agent@your-domain.com`) — see booking events show up.
- **HubSpot YourCompany portal** — see contact + engagement note + meeting created.

### 1.4 Known limitations (don't file as bugs)

- Browser-test caller identity (`client:user_<timestamp>`) is **regenerated every session**, so the system cannot recognize them as a returning caller. Memory and identity-verification flows must be tested with a **real phone number**.
- Real Aplus tenant (`+1-555-0101`) currently shares YourCompany's HubSpot/Outlook fallback — until Aplus's own credentials are filled in Supabase.
- `MS_CALENDAR_EMAIL` recipient may render the booking time in the recipient's local timezone or UTC; this is the recipient's mail client behavior, not a bug. The actual stored event is in `America/Chicago` for YourCompany.
- OpenAI Realtime API costs apply to every test call (~$0.06/min input + $0.24/min output). Don't leave a call connected for 20 minutes.

---

## 2. Functional test cases

### TC-001 — Inbound greeting (new caller)

**Setup**: Use a phone number that has never called before (or with no `caller_memory` rows in Supabase).

**Steps**:
1. Dial +1-555-0100.
2. Listen.

**Expected**:
- AI answers within 1 second.
- Says: `"Thank you for calling 3 6 0 dmmc. How can I help you today?"` (or the configured `greeting_new`).
- "360" is pronounced **three-six-zero**, not "three sixty".

**Verify**:
- `voice_sessions` has a new row with `status='active'` and `tier='growth'`.
- `analytics_events` has `event_type='call_started'`.

---

### TC-002 — FAQ answering

**Steps**:
1. From the greeting, ask: `"What services do you offer?"`
2. Then: `"Do you offer marketing automation?"`

**Expected**:
- AI answers using the configured FAQs from `faq_entries` (currently 121 for YourCompany).
- AI does **not** invent capabilities not in the FAQ.

**Edge case**:
- Ask: `"What's your refund policy?"` — there is no FAQ for this. AI should say it's not sure and offer to take a message or transfer, **not** make up a policy.

---

### TC-003 — Memory consent + save

**Steps**:
1. Say: `"My name is QA-Test-Alex"`.
2. AI should ask whether to remember.
3. Reply: `"Yes, please remember"`.
4. Say: `"My email is qa-test@example.com"`.
5. AI should read the email back letter-by-letter for confirmation.
6. Reply `"yes that's right"`.
7. Say `"Goodbye"`.

**Verify in Supabase**:
- `caller_consent` row with `forget_requested=false`.
- `caller_memory` rows: `name=QA-Test-Alex`, `email=qa-test@example.com`.
- After call: `analytics_events` has `email_confirmation_sent`.
- **Your phone receives an SMS**: "Hi! This is YourCompany. We have your email as qa-test@example.com. Reply YES to confirm…"
- Reply `YES` to that SMS — memory should now be confirmed.

---

### TC-004 — Returning caller + identity verification

**Setup**: Call from the same phone you used in TC-003.

**Steps**:
1. AI greets generically and asks if you want to continue from previous info.
2. Say `"Yes please"`.
3. AI asks for your name. Say `"QA-Test-Alex"`.
4. AI asks for your email. Say `"qa-test@example.com"`.
5. AI should call the `verify_identity` tool internally → log shows `identity_verified` event.

**Expected**:
- After successful verification, AI may reference your stored email naturally (`"I have your email as qa-test@example.com — should we use that?"`).
- If you give the **wrong** email or name, AI must **not** read back stored values; it should treat you as a new person.

**Failure path test**:
1. Same setup, but give a wrong email like `"alex@wrong.com"`.
2. AI should apologize and start fresh, not reveal what's actually stored.

**Verify**:
- `analytics_events` has `event_type='identity_verified'` only on success.

---

### TC-005 — Appointment booking

**Steps**:
1. Say `"I'd like to book a meeting"`.
2. AI asks when. Say `"Next Tuesday at 3 PM"`.
3. AI should confirm timezone explicitly: **"Just to confirm, that's 3 PM Central Time, correct?"**
4. Say `"Yes"`.
5. AI provides email if not already known, confirms it letter-by-letter.
6. AI books and confirms: `"Booked for [date] at 3 PM Central Time."`

**Verify**:
- `bookings` row in Supabase.
- Outlook calendar (`ai-agent@your-domain.com`) has a new event at 3 PM Central on the requested date.
- HubSpot YourCompany portal: contact has a new **meeting** in its activity timeline.
- Caller email receives an Outlook calendar invite.
- Render logs: `Calendar event created: <id>`, `HubSpot meeting created: <id>`.

**Edge case — slot conflict**:
- Book a time that's already taken. AI should offer alternative slots, all with timezone label.

---

### TC-006 — Transfer to human

**Setup**: Make sure the test phone (yours) is **not** in YourCompany's hunt group, otherwise you'll hear yourself ring.

**Steps**:
1. Say `"I need to talk to a real person"`.
2. AI says something like `"Connecting you now"`, then the call should redirect.
3. The hunt group rings sequentially: first **+1 773 200 5177 (Emilio)**, then **+216 26 387 319 (Aymen)**, with a 20-second timeout each.

**Expected**:
- Whoever picks up gets bridged to the caller.
- If nobody picks up within the timeout, AI says `"I'm sorry, no one was available. Please try again later."` and hangs up.

**Verify**:
- `voice_sessions.status='transferred'`.
- `analytics_events` has `event_type='transfer_requested'`.

---

### TC-007 — End call cleanly

**Steps**:
1. Say `"Goodbye, thank you"`.
2. AI says farewell.
3. Call should hang up automatically — you should hear the disconnect tone.

**Verify**:
- `voice_sessions.status='closed'`.
- Render logs: `tool_call: end_call` followed by `connection closed`.
- Caller email receives a follow-up email summarizing the conversation.

---

### TC-008 — Forget me (GDPR)

**Setup**: Use a phone with existing memory (run TC-003 first, then call again).

**Steps**:
1. Say `"Forget my data, please delete everything"`.
2. AI confirms and calls `forget_caller`.

**Verify in Supabase**:
- `caller_consent` row updated: `forget_requested=true`, `forget_requested_at=NOW`.
- All `caller_memory` rows for this phone are deleted.

---

### TC-009 — Barge-in (interruption)

**Steps**:
1. Ask AI a question that triggers a long answer.
2. While AI is mid-sentence, **start talking** (in a normal voice, not a whisper).
3. AI should **stop speaking** within ~500 ms and listen.

**Expected**:
- AI doesn't continue talking over you.
- Your interruption gets processed and AI responds to it, not to its own truncated response.

> **Note**: false-barge-in from speaker echo is the most common false-positive. Use a headset.

---

### TC-010 — Voicemail (no answer in human transfer)

**Setup**: Temporarily empty the hunt group (or set it to a number that won't pick up).

**Steps**:
1. Ask to be transferred.
2. Wait for the timeouts.
3. AI plays the no-one-available message and hangs up.

**Expected**:
- `voicemail_email` recipient (`emilio@360dmmc.com`) receives an email titled "New Voicemail from <caller> — 3 6 0 dmmc".

---

## 3. Multi-tenant test cases

Same as section 2 but using **+1-555-0101 (Aplus)** as the inbound number. The differences to verify:

- Greeting matches Aplus's `greeting_new` (medical-supplies wording, not YourCompany).
- FAQ answers come from Aplus's 31 FAQs (PPE, DME, returns, etc.) — not YourCompany's marketing FAQs.
- Booking lands on Aplus's calendar (or, until Aplus has its own M365 mailbox set up, on the platform fallback).
- HubSpot writes go to Aplus's HubSpot portal (or platform fallback if not yet configured).
- Twilio signature validation uses Aplus's auth token (look for `tenant_token=yes` in Render logs vs `fallback`).

If any of those fall back to YourCompany instead of Aplus, file as a bug.

---

## 4. Where to look when something breaks

| Symptom | First place to look |
|---|---|
| Call connects, AI silent | Render logs → Ctrl+F `OpenAI error event` (look for `insufficient_quota`, model errors). |
| Twilio webhook 403 Forbidden | Render logs → `Invalid Twilio signature` — usually means `account_settings.twilio_auth_token` is missing or wrong for that tenant. |
| AI says wrong name / wrong tenant | `voice_sessions` row's `tenant_id` — should match the called number's tenant. |
| Booking made on wrong calendar | `account_settings.calendar_email` for that tenant. |
| FAQ answers feel wrong | `faq_entries` table — count rows for that tenant. |
| Email follow-up never arrives | Render logs → `Skipping … email`. Either `voicemail_email` empty or Microsoft Graph token denied. |
| SMS reply YES not processed | Twilio Console → that number → Messaging webhook should be `https://api.your-domain.com/sms/inbound`. |

---

## 5. Dashboard UI test cases

The dashboard was rebuilt on the NextAdmin / TailAdmin design system. These cases verify the new layout, components, and per-tenant scoping.

### 5.0 Pre-conditions

- A working dashboard URL (production: https://app.your-domain.com — staging: http://localhost:3000 with `NEXT_PUBLIC_API_URL` pointed at Render).
- An **admin** test account and a **client** test account in `dashboard_users`.
- For staging: `COOKIE_SECURE=true` + `COOKIE_SAMESITE=none` + `CORS_ORIGINS` includes `http://localhost:3000` on the API. Otherwise login lands at /overview with 401s.

### TC-D01 — Login flow (same-site, production)

1. Open https://app.your-domain.com/login in an incognito window.
2. Verify the split layout: left = sign-in form with mail icon, right = purple gradient hero with the SVG illustration (phone + 4 floating cards) and 4 bullets.
3. Submit valid credentials.
4. Expected: redirect to `/overview` with KPI cards populated.
5. Open DevTools → Application → Cookies. The session cookie should be `HttpOnly`, `Secure`, `SameSite=Lax`.

### TC-D02 — Login flow (cross-origin, staging)

1. Local `npm run dev` against Render API. Open http://localhost:3000/login.
2. Submit valid credentials.
3. Expected: redirect to `/overview` with data loaded.
4. DevTools → Cookies for `*.onrender.com`: cookie must be `HttpOnly`, `Secure`, **`SameSite=None`**. If `SameSite=Lax`, the API still has the old config — login will succeed once but no subsequent request carries the cookie (everything 401s).
5. Common fix: clear cookies for the API origin → hard-refresh → retry.

### TC-D03 — Failed login

1. Wrong password 5 times.
2. Expected: red error block on form ("Invalid email or password"); after 5 attempts the API begins rate-limiting with HTTP 429 (visible in Network tab).

### TC-D04 — Header pieces

1. After login, verify the sticky header shows: page title + subtitle (changes per route), search input (≥sm), theme toggle pill, notification bell with red dot, user avatar.
2. Click the user avatar → dropdown should show tenant name + email + Profile / Integrations / Log out.
3. Click theme toggle → entire dashboard should switch to dark mode (gray-dark backgrounds, light text). Refresh — preference persists (next-themes sets `class="dark"` on `<html>`).
4. Click bell → "Live" pill + "You're all caught up" placeholder. (Real notifications are not implemented yet — do not file as a bug.)

### TC-D05 — Sidebar + responsive

1. Verify three sidebar groups: MAIN MENU, CONFIGURATION, ADMIN. ADMIN is hidden for client users.
2. Click each item — the active row gets a primary-tinted background; the route changes; the page title in the header updates.
3. At the bottom of the sidebar: tenant initial bubble + tenant name + email + sign-out button.
4. Resize the browser below 850px. Sidebar collapses; a hamburger button appears in the header.
5. Click hamburger → sidebar slides in with a black overlay. Tap the overlay or any nav link → sidebar closes.
6. Resize back above 850px — sidebar re-expands automatically (the user-toggle override naturally clears at the breakpoint).

### TC-D06 — Tenant switcher (admin only)

1. Log in as **admin** with ≥2 tenants. The header shows a Building2 dropdown ("Acme Corp · GROWTH ▾") between the search and theme toggle.
2. Click → list of all tenants with phone + tier; current tenant has a checkmark.
3. Pick another tenant → page reloads to /overview with that tenant's data.
4. Refresh the page — selection persists (localStorage `pod6_admin_tenant_id`).
5. Log in as **client** — the switcher is replaced by a read-only label of their tenant only.

### TC-D07 — Overview page

1. `/overview` shows 4 OverviewCards in a row: Total Calls (purple), Active Customers (green), Memory Facts (blue), Event Types (amber).
2. Below: pie chart "Event Breakdown" (only when ≥1 event row in `analytics_events`) + "Quick Stats" panel.
3. Numbers should match a quick `SELECT count(*) FROM voice_sessions WHERE tenant_id = …` for the current tenant.

### TC-D08 — Calls + Customers tables

1. `/calls`: a panel card with "{N} calls" title, search box, and a table with status pills tinted by `STATUS_STYLES`.
2. `/customers`: same panel pattern with initials avatars in the first column.
3. Type into search box → rows filter live.
4. With no rows: a centered "No calls/customers found" empty state.

### TC-D09 — FAQ CRUD

1. `/faq`: category pills at top + Add FAQ button (right). Default pill = "All ({N})".
2. Click "Add FAQ" → modal dialog opens with Category / Question / Answer fields.
3. Fill in, click Save → modal closes, table refreshes with the new row visible.
4. Click the pencil icon on a row → modal pre-filled; edit, save, verify update.
5. Click the trash icon → browser `confirm()` → row deleted from table.
6. Switch tenant in the admin switcher (TC-D06) → FAQ table content changes (each tenant has its own `faq_entries`).

### TC-D10 — Settings tabs

1. `/settings` shows 5 tabs: General, Voice & Greetings, Business Hours, Integrations, Advanced.
2. Each tab has its own Save button.
3. Edit a value (e.g. `greeting_new`), Save → "Saved!" green note flashes briefly, then refresh page → value persists.
4. Admin sees a "Tier" select (starter/growth/pro) — client does not.
5. **Integrations tab** — verify the per-tenant credential UI:
   - Twilio: Account SID, Auth Token (masked when saved), API Key SID, API Key Secret (masked), TwiML App SID.
   - Outlook mailbox: Sender email + Calendar email (free text — for hot-reload OAuth use the "Connect Outlook" button on `/integrations`).
   - HubSpot: Access token (masked).
6. Saved secrets re-render as `••••••••` with a "(saved — leave blank to keep)" hint. Submitting the form blank-fielded must not wipe the stored value.

### TC-D11 — Integrations OAuth status

1. `/integrations` shows 6 service cards (HubSpot, Microsoft Outlook, Twilio, OpenAI, Cartesia, Supabase).
2. HubSpot + Outlook show "Connected" (green pill) only when `tenant_credentials` has a row for this tenant; otherwise "Not connected" + a Connect button.
3. Click "Connect Outlook" → browser opens Microsoft consent screen → callback writes to `tenant_credentials` with `service='microsoft'` → page reloads showing Connected.
4. Twilio, OpenAI, Cartesia, Supabase always render as "Connected" (they're platform-level, not OAuth) and the Connect button is disabled.

### TC-D12 — Admin pages

1. As admin, `/tenants` lists all tenants in a table with an aggregate row of OverviewCards on top.
2. Click any row → tenant switcher updates and you're redirected to `/overview` of that tenant.
3. As admin, `/system` shows two cards (Backend API + Supabase) with green/red status icons + an Endpoint table at the bottom.
4. Log in as **client** and try to navigate to `/tenants` or `/system` directly — the page should redirect to `/overview` (gated client-side by `useAuth().role`).

### TC-D13 — Logout

1. Click user avatar → Log out.
2. Expected: cookie deleted, redirected to `/login`.
3. Manually navigate to `/overview` → redirect back to `/login` (no flicker of dashboard content).

### TC-D14 — Error handling

1. Stop the API (or break `NEXT_PUBLIC_API_URL`).
2. Refresh `/overview`. Expected: a branded ErrorCard with "Couldn't load this page" + a Try again button. Click → retries the request.

---

## 6. Reporting bugs

Include in every report:
1. Environment (staging Render or production Hostinger).
2. Exact phone number used + identity (browser SDK identity if applicable).
3. Time of call (UTC and local) so the tester can find the call SID.
4. The CallSid from Twilio Console (Monitor → Logs → Calls).
5. The Render log block from when the call started to when it ended.
6. What you said vs what AI said vs what you expected.
7. Screenshots of any wrong data shown in dashboard / Outlook / HubSpot.

File in: <wherever the team tracks issues — Linear/Jira/GitHub Issues>.
