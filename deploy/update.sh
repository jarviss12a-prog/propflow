#!/usr/bin/env bash
# Pull the latest code and restart. Your data/ folder and .env are untouched.
#   cd ~/propflow && bash deploy/update.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
.venv/bin/python manage.py backup >/dev/null && echo "Backed up before updating."
git pull --ff-only
.venv/bin/pip install -q -r requirements.txt
sudo systemctl restart propflow
sleep 2
PORT="$(grep -E '^PORT=' .env | cut -d= -f2)"
curl -fsS "http://127.0.0.1:${PORT:-8050}/health" >/dev/null && echo "Updated and running."
