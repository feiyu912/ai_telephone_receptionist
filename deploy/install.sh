#!/usr/bin/env bash
# AI Telephone Receptionist — idempotent one-shot VPS installer
#
# Handles every common failure mode you can hit on a real VPS:
#   - system nginx / apache holding port 80/443
#   - missing or stale .env
#   - missing SSL certs (chicken-and-egg with nginx)
#   - cert renewal cron
#   - re-running on an already-deployed VPS (no harm done)
#
# Prereqs:
#   1. Ubuntu / Debian VPS with root access
#   2. DNS A records for api.your-domain.com + app.your-domain.com → this VPS's public IP
#   3. A filled-in deploy/.env (copy from ../.env.example, fill secrets)
#
# Usage:
#   cd /opt/AI-voice-receptionist/deploy
#   sudo ./install.sh

set -euo pipefail

DOMAIN_API="api.your-domain.com"
DOMAIN_APP="app.your-domain.com"
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-admin@your-domain.com}"

STEP=0
step() { STEP=$((STEP + 1)); echo; echo "== [$STEP] $* =="; }
die()  { echo "ERROR: $*" >&2; exit 1; }

# ── 0. Pre-flight ──────────────────────────────────────────────────

[[ $EUID -eq 0 ]] || die "Run as root: sudo ./install.sh"

cd "$(dirname "$0")"  # Always execute relative to deploy/

[[ -f .env ]] || die ".env is missing in $(pwd). Copy ../.env.example, fill it, try again."

# Sanity-check a few required keys
for key in DATABASE_URL AUTH_SECRET BASE_URL; do
    grep -qE "^${key}=.+" .env || die "$key is missing or empty in .env"
done

# ── 1. System packages + Docker ────────────────────────────────────

step "Updating apt + installing Docker"
apt-get update -qq
apt-get install -y -qq ca-certificates curl gnupg lsb-release git ufw

if ! command -v docker &>/dev/null; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
         https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get install -y -qq \
        docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
fi

# ── 2. Clear port 80/443 conflicts ─────────────────────────────────

step "Freeing ports 80 and 443"
# System nginx / apache will fight our container nginx for these ports.
# If either is active, stop + disable them (idempotent).
for svc in nginx apache2; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        echo "Stopping system $svc (would conflict with container nginx)"
        systemctl stop "$svc"
        systemctl disable "$svc" 2>/dev/null || true
    fi
done

# ── 3. Firewall ────────────────────────────────────────────────────

step "Configuring UFW (allow 22/80/443, quiet logging)"
ufw allow 22/tcp  >/dev/null
ufw allow 80/tcp  >/dev/null
ufw allow 443/tcp >/dev/null
ufw logging off   >/dev/null  # avoid kernel-log spam in SSH
yes | ufw --force enable >/dev/null 2>&1 || true

# ── 4. SSL certificates (first-run only) ───────────────────────────

step "Ensuring Let's Encrypt certificates for $DOMAIN_API + $DOMAIN_APP"
mkdir -p ./certbot/conf ./certbot/www

if [[ -d "./certbot/conf/live/${DOMAIN_API}" ]]; then
    echo "Certificate already present — skipping issuance."
else
    # Chicken-and-egg: the real nginx.conf requires cert files that don't exist
    # yet. Spin up a throwaway HTTP-only nginx to serve the ACME webroot
    # challenge, then shut it down.
    TMP_CONF="$(mktemp /tmp/nginx-init.XXXX.conf)"
    cat > "$TMP_CONF" <<EOF
server {
    listen 80;
    server_name ${DOMAIN_API} ${DOMAIN_APP};
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 200 'bootstrap'; }
}
EOF
    docker rm -f nginx-init >/dev/null 2>&1 || true
    docker run --rm -d --name nginx-init \
        -p 80:80 \
        -v "$TMP_CONF:/etc/nginx/conf.d/default.conf:ro" \
        -v "$(pwd)/certbot/www:/var/www/certbot" \
        nginx:alpine >/dev/null
    sleep 2

    if ! docker run --rm \
        -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
        -v "$(pwd)/certbot/www:/var/www/certbot" \
        certbot/certbot certonly --webroot -w /var/www/certbot \
        --email "$LETSENCRYPT_EMAIL" --agree-tos --no-eff-email -n \
        -d "$DOMAIN_API" -d "$DOMAIN_APP"; then
        docker stop nginx-init >/dev/null 2>&1 || true
        rm -f "$TMP_CONF"
        die "certbot failed — check DNS is pointing at this VPS, then re-run."
    fi

    docker stop nginx-init >/dev/null 2>&1 || true
    rm -f "$TMP_CONF"
fi

# ── 5. Cert auto-renewal ───────────────────────────────────────────

step "Installing weekly cert-renewal cron"
CRON_LINE="0 3 * * 1 cd $(pwd) && docker compose run --rm certbot renew --quiet && docker compose restart nginx"
( crontab -l 2>/dev/null | grep -Fv "docker compose run --rm certbot renew"
  echo "$CRON_LINE"
) | crontab -

# ── 6. Bring up the stack ──────────────────────────────────────────

step "Starting services (docker compose up -d --build)"
# Ensure we start from a clean slate so nginx picks up the fresh cert files.
docker compose down --remove-orphans >/dev/null 2>&1 || true
docker compose up -d --build

# ── 7. Smoke test ──────────────────────────────────────────────────

step "Smoke test"
sleep 5
if docker compose exec -T api curl -fs http://localhost:8000/health >/dev/null; then
    echo "API healthy (inside container)."
else
    echo "WARN: api /health failed inside container — check:  docker compose logs api"
fi

if curl -fs -k "https://${DOMAIN_API}/health" >/dev/null; then
    echo "HTTPS terminated by nginx ok."
else
    echo "WARN: https://${DOMAIN_API}/health did not respond — check:  docker compose logs nginx"
fi

cat <<EOF

================================================================
Deployment complete.

  Voice API:   https://${DOMAIN_API}/health
  Dashboard:   https://${DOMAIN_APP}

Ops:
  docker compose ps
  docker compose logs -f api
  docker compose logs -f nginx

Twilio webhooks should point at:
  Voice:           https://${DOMAIN_API}/voice/incoming-call
  Status callback: https://${DOMAIN_API}/voice/status-callback
  SMS:             https://${DOMAIN_API}/sms/inbound
  WhatsApp:        https://${DOMAIN_API}/whatsapp/inbound

Cert auto-renew cron installed: weekly (Monday 03:00).
================================================================
EOF
