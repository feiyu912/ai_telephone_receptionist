#!/usr/bin/env bash
# POD6 Voice Agent — One-shot VPS installer for Ubuntu 22.04 / 24.04
#
# Prereqs:
#   - Fresh Ubuntu VPS with root or sudo access
#   - DNS A records for api.your-domain.com + app.your-domain.com pointing to this VPS IP
#   - .env file filled in (copy from .env.example)
#
# Usage (on the VPS, after cloning the repo):
#   cd AI-voice-receptionist/deploy
#   cp ../.env.example .env  # then fill it in with real values
#   sudo ./install.sh

set -euo pipefail

DOMAIN_API="api.your-domain.com"
DOMAIN_APP="app.your-domain.com"
LETSENCRYPT_EMAIL="emilio@360dmmc.com"

# ── 0. Ensure we're root ────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    echo "Please run as root (sudo ./install.sh)"
    exit 1
fi

# ── 1. System update + essentials ────────────────────────────────────
echo "[1/6] Updating system packages..."
apt-get update
apt-get upgrade -y
apt-get install -y \
    ca-certificates curl gnupg lsb-release \
    git ufw

# ── 2. Install Docker + Compose plugin ─────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "[2/6] Installing Docker..."
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
         https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
else
    echo "[2/6] Docker already installed, skipping."
fi

# ── 3. Firewall ────────────────────────────────────────────────────
echo "[3/6] Configuring firewall..."
ufw allow 22/tcp   # SSH
ufw allow 80/tcp   # HTTP (for Let's Encrypt challenge)
ufw allow 443/tcp  # HTTPS
ufw --force enable

# ── 4. Prepare certbot directories ─────────────────────────────────
echo "[4/6] Preparing certificate directories..."
mkdir -p ./certbot/conf ./certbot/www

# ── 5. Issue SSL certificates (first time only) ────────────────────
if [[ ! -d "./certbot/conf/live/${DOMAIN_API}" ]]; then
    echo "[5/6] Issuing SSL certificates via Let's Encrypt..."
    # Start a temporary nginx without SSL to handle the ACME challenge
    cat > /tmp/nginx-init.conf <<EOF
server {
    listen 80;
    server_name ${DOMAIN_API} ${DOMAIN_APP};
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 200 'OK'; }
}
EOF
    docker run --rm -d \
        --name nginx-init \
        -p 80:80 \
        -v /tmp/nginx-init.conf:/etc/nginx/conf.d/default.conf:ro \
        -v "$(pwd)/certbot/www:/var/www/certbot" \
        nginx:alpine

    sleep 3

    docker run --rm \
        -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
        -v "$(pwd)/certbot/www:/var/www/certbot" \
        certbot/certbot certonly --webroot -w /var/www/certbot \
        --email "${LETSENCRYPT_EMAIL}" --agree-tos --no-eff-email \
        -d "${DOMAIN_API}" -d "${DOMAIN_APP}"

    docker stop nginx-init || true
    rm -f /tmp/nginx-init.conf
else
    echo "[5/6] SSL certificates already exist, skipping issuance."
fi

# ── 6. Start the stack ─────────────────────────────────────────────
echo "[6/6] Starting services..."
docker compose up -d --build

echo ""
echo "================================================================"
echo "Deployment complete!"
echo ""
echo "  Voice API:   https://${DOMAIN_API}/health"
echo "  Dashboard:   https://${DOMAIN_APP}"
echo ""
echo "Check status:  docker compose ps"
echo "View logs:     docker compose logs -f api"
echo ""
echo "Remember to update Twilio webhooks to:"
echo "  Voice:           https://${DOMAIN_API}/voice/incoming-call"
echo "  Status Callback: https://${DOMAIN_API}/voice/status-callback"
echo "  SMS:             https://${DOMAIN_API}/sms/inbound"
echo "  WhatsApp:        https://${DOMAIN_API}/whatsapp/inbound"
echo "================================================================"
