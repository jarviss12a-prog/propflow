#!/usr/bin/env bash
# One-time install of PropFlow on an Ubuntu/Debian VPS, reachable only over Tailscale.
#
#   cd ~/propflow && bash deploy/setup.sh
#
# Safe to run again: it keeps your .env, database and password.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_USER="${SUDO_USER:-$USER}"
SERVICE=propflow
cd "$APP_DIR"

say() { printf '\n\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\n\033[1;33m!!\033[0m %s\n' "$*"; }

if [ "$(id -u)" -eq 0 ] && [ -z "${SUDO_USER:-}" ]; then
  warn "Run this as your normal user (it calls sudo when needed), not as root."
  exit 1
fi

say "Checking Python"
if ! python3 -c 'import venv, ensurepip' 2>/dev/null; then
  sudo apt-get update -qq && sudo apt-get install -y -qq python3-venv python3-pip
fi
python3 -c 'import sys; assert sys.version_info >= (3, 9), "Python 3.9+ needed"'

say "Installing Python packages into .venv"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

port_in_use() {
  python3 -c 'import socket, sys; s = socket.socket(); sys.exit(0 if s.connect_ex(("127.0.0.1", int(sys.argv[1]))) == 0 else 1)' "$1"
}

if [ ! -f .env ]; then
  say "Creating .env"
  PORT=8050
  while port_in_use "$PORT"; do PORT=$((PORT + 1)); done
  SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  sed -e "s|^PROPFLOW_SECRET_KEY=.*|PROPFLOW_SECRET_KEY=$SECRET|" -e "s|^PORT=.*|PORT=$PORT|" .env.example > .env
  chmod 600 .env
else
  say "Keeping existing .env"
fi
PORT="$(grep -E '^PORT=' .env | cut -d= -f2)"
PORT="${PORT:-8050}"
mkdir -p data
chmod 700 data

say "Database and password"
if .venv/bin/python -c "
from dotenv_lite import load_env; load_env('.env')
from app import create_app; from app.auth import password_is_set
app = create_app()
with app.app_context(): raise SystemExit(0 if password_is_set() else 1)"; then
  echo "Password already set (change it later in Settings, or: .venv/bin/python manage.py set-password)."
else
  .venv/bin/python manage.py set-password
fi

say "Installing the systemd service (runs as $RUN_USER on 127.0.0.1:$PORT)"
sudo tee /etc/systemd/system/$SERVICE.service >/dev/null <<UNIT
[Unit]
Description=PropFlow rental tracker
After=network-online.target
Wants=network-online.target

[Service]
User=$RUN_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/.venv/bin/gunicorn --workers 2 --bind 127.0.0.1:$PORT --access-logfile - wsgi:app
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now $SERVICE
sudo systemctl restart $SERVICE
sleep 2
if curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null; then
  echo "PropFlow is running."
else
  warn "PropFlow didn't answer. Check: sudo journalctl -u $SERVICE -n 50"
  exit 1
fi

say "Nightly backup at 3:15 (keeps the last 30 in data/backups)"
sudo tee /etc/cron.d/$SERVICE >/dev/null <<CRON
15 3 * * * $RUN_USER cd $APP_DIR && .venv/bin/python manage.py backup >> data/backup.log 2>&1
CRON

say "Tailscale"
if ! command -v tailscale >/dev/null; then
  warn "Tailscale isn't installed. Install it (curl -fsSL https://tailscale.com/install.sh | sh), run 'sudo tailscale up', then run this script again."
  exit 0
fi
DNS_NAME="$(tailscale status --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))' 2>/dev/null || true)"
# Use 443 if nothing else on this machine is served there; otherwise 8443 so your other apps keep working.
HTTPS_PORT="$(sudo tailscale serve status --json 2>/dev/null | python3 -c '
import json, sys
try:
    cfg = json.load(sys.stdin) or {}
except Exception:
    cfg = {}
used = set((cfg.get("TCP") or {}).keys())
for port in ("443", "8443", "9443", "10443"):
    if port not in used:
        print(port); break
' || echo 8443)"
if sudo tailscale serve --bg --https="$HTTPS_PORT" "http://127.0.0.1:$PORT" >/dev/null 2>&1; then
  URL="https://$DNS_NAME"; [ "$HTTPS_PORT" = "443" ] || URL="$URL:$HTTPS_PORT"
  say "Done. Open this on your phone (with Tailscale on):"
  echo "    $URL"
  echo
  echo "Tip: in Safari tap Share → Add to Home Screen to get an app icon."
else
  TS_IP="$(tailscale ip -4 | head -1)"
  warn "tailscale serve didn't work (HTTPS certificates may be off for your tailnet)."
  echo "Either turn on HTTPS in the Tailscale admin console (DNS → HTTPS Certificates) and re-run this script,"
  echo "or use plain Tailscale IP access:"
  echo "  1. In .env set PROPFLOW_SECURE_COOKIES=0"
  echo "  2. sudo sed -i 's|--bind 127.0.0.1:$PORT|--bind $TS_IP:$PORT|' /etc/systemd/system/$SERVICE.service"
  echo "  3. sudo systemctl daemon-reload && sudo systemctl restart $SERVICE"
  echo "  4. Open http://$TS_IP:$PORT"
fi
