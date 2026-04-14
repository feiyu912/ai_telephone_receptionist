# AI Telephone Receptionist — Hostinger VPS Deployment Guide

This guide walks through deploying the AI Telephone Receptionist voice agent API + Next.js dashboard to a fresh Hostinger VPS.

**Target domain:** `your-domain.com`
- `api.your-domain.com` → FastAPI voice agent (Twilio webhooks, OpenAI Realtime)
- `app.your-domain.com` → Next.js admin dashboard

---

## 1. Prerequisites

Before running the installer you need:

- **Hostinger VPS** — KVM 2 or better (2 vCPU / 4 GB RAM), Ubuntu 22.04 or 24.04, US data center
- **VPS root access** — IP address and root password (or SSH key)
- **DNS records** on `your-domain.com`:
  - `A api.your-domain.com` → VPS IP
  - `A app.your-domain.com` → VPS IP
- **`.env` file** filled in with all credentials (copy from `.env.example`)
- **GitHub repo access** from the VPS (make it public temporarily, or set up an SSH deploy key)

---

## 2. Initial VPS Setup

SSH into the VPS:

```bash
ssh root@<VPS_IP>
```

Set a hostname (optional but nice):

```bash
hostnamectl set-hostname ai-receptionist-prod
```

Create a non-root user (recommended for production):

```bash
adduser vozalta
usermod -aG sudo vozalta
```

---

## 3. Clone the Repo

```bash
cd /opt
git clone https://github.com/YourCompany-AI-Marketing/AI-voice-receptionist.git
cd AI-voice-receptionist
```

If the repo is private, use an SSH deploy key or a GitHub personal access token:

```bash
git clone https://<TOKEN>@github.com/YourCompany-AI-Marketing/AI-voice-receptionist.git
```

---

## 4. Configure Environment Variables

```bash
cp .env.example .env
nano .env
```

Fill in all values. At minimum:

```
DATABASE_URL=postgresql+asyncpg://postgres.xxx:password@aws-0-us-west-2.pooler.supabase.com:5432/postgres
OPENAI_API_KEY=sk-proj-...
CARTESIA_API_KEY=sk_car_...
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_API_KEY_SID=SK...
TWILIO_API_KEY_SECRET=...
TWILIO_TWIML_APP_SID=AP...
HUBSPOT_ACCESS_TOKEN=pat-na2-...
MS_TENANT_ID=...
MS_CLIENT_ID=...
MS_CLIENT_SECRET=...
MS_CALENDAR_EMAIL=ai-agent@your-domain.com
MS_SENDER_EMAIL=ai-agent@your-domain.com
BASE_URL=https://api.your-domain.com
LOG_LEVEL=info
```

Copy the `.env` into the `deploy/` folder too (docker-compose reads from there):

```bash
cp .env deploy/.env
```

---

## 5. Run the Installer

```bash
cd deploy
chmod +x install.sh
sudo ./install.sh
```

The installer will:
1. Update Ubuntu packages
2. Install Docker + Compose plugin
3. Configure UFW firewall (22, 80, 443)
4. Issue Let's Encrypt SSL certificates for both domains
5. Build + start the Docker stack (api + dashboard + nginx)

Takes about 5-10 minutes total.

---

## 6. Verify Deployment

```bash
docker compose ps        # All services should be "running"
docker compose logs -f   # Tail the logs
curl https://api.your-domain.com/health
# Expected: {"status":"ok","service":"pod6-voice-agent","version":"0.2.0"}
```

Open `https://app.your-domain.com` in a browser — the dashboard login page should appear.

---

## 7. Point Twilio to the New URL

In the Twilio Console, update both phone numbers + the TwiML App:

**Phone: +1-555-0100 (360 Group)**
- Voice webhook: `https://api.your-domain.com/voice/incoming-call` (POST)
- Status callback: `https://api.your-domain.com/voice/status-callback` (POST)
- SMS webhook: `https://api.your-domain.com/sms/inbound` (POST)

**Phone: +1-555-0101 (Aplus)**
- Voice webhook: `https://api.your-domain.com/voice/incoming-call` (POST)
- Status callback: `https://api.your-domain.com/voice/status-callback` (POST)
- SMS webhook: `https://api.your-domain.com/sms/inbound` (POST)

**TwiML App `APb3b9320bbfb27bd08d2e50fe06cba233`:**
- Voice Request URL: `https://api.your-domain.com/voice/incoming-call`
- Status Callback URL: `https://api.your-domain.com/voice/status-callback`

---

## 8. Ongoing Operations

### Deploying updates

Push code to GitHub, then on the VPS:

```bash
cd /opt/AI-voice-receptionist
git pull
cd deploy
docker compose up -d --build
```

Auto-deploy (GitHub Actions → SSH + docker compose up) can be added later.

### Renewing SSL certificates

Let's Encrypt certs expire every 90 days. To renew:

```bash
cd /opt/AI-voice-receptionist/deploy
docker compose run --rm certbot renew
docker compose restart nginx
```

Add a cron job for automatic renewal:

```bash
sudo crontab -e
# Add this line:
0 3 * * 1 cd /opt/AI-voice-receptionist/deploy && docker compose run --rm certbot renew && docker compose restart nginx
```

### Viewing logs

```bash
docker compose logs -f api       # Voice agent logs
docker compose logs -f dashboard # Dashboard logs
docker compose logs -f nginx     # Nginx access/error logs
```

### Restarting a service

```bash
docker compose restart api
```

### Full reset

```bash
docker compose down
docker compose up -d --build
```

---

## 9. Troubleshooting

**"Connection refused" on https URLs**
- Check nginx is running: `docker compose ps`
- Check SSL certs exist: `ls deploy/certbot/conf/live/`
- Check DNS: `dig api.your-domain.com` should return VPS IP

**"502 Bad Gateway" from nginx**
- API or dashboard container is down
- `docker compose logs api` to see errors (usually missing env vars)

**Twilio returns "Application error"**
- Check `BASE_URL` in `.env` matches `https://api.your-domain.com`
- Check `docker compose logs api` for the actual exception

**WebSocket fails (Twilio Media Stream disconnects)**
- Confirm nginx config includes `Upgrade` headers (it does in `nginx.conf`)
- Check firewall isn't blocking — `sudo ufw status` should show 443 allowed

---

## 10. Post-Deploy Checklist

- [ ] `https://api.your-domain.com/health` returns 200
- [ ] `https://app.your-domain.com` loads the login page
- [ ] Twilio webhooks updated on both phone numbers + TwiML App
- [ ] Test call: dial +1-555-0100, verify AI answers and conversation works
- [ ] Test call hangup: say goodbye, verify call ends automatically
- [ ] Check Render instance is no longer receiving traffic (can be deleted to save $7/month)
- [ ] Update `BASE_URL` in GitHub README

---

*For questions, check the Teams main channel per team protocol (no DMs).*
