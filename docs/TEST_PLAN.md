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

## 5. Reporting bugs

Include in every report:
1. Environment (staging Render or production Hostinger).
2. Exact phone number used + identity (browser SDK identity if applicable).
3. Time of call (UTC and local) so the tester can find the call SID.
4. The CallSid from Twilio Console (Monitor → Logs → Calls).
5. The Render log block from when the call started to when it ended.
6. What you said vs what AI said vs what you expected.
7. Screenshots of any wrong data shown in dashboard / Outlook / HubSpot.

File in: <wherever the team tracks issues — Linear/Jira/GitHub Issues>.
