#!/usr/bin/env bash
# Deploy ResolveLoop to the Hostinger VPS as a sibling of the AllergyLens API.
# Usage: bash deploy/deploy_vps.sh            (first run creates venv, unit and .env; later runs sync + restart)
set -euo pipefail
HOST=${VPS_HOST:-root@72.62.33.46}
DIR=/root/resolveloop
HERE=$(cd "$(dirname "$0")/.." && pwd)

rsync -az --delete --exclude .venv --exclude '*.db*' --exclude .git --exclude .env --exclude evidence --exclude .pytest_cache \
  "$HERE/" "$HOST:$DIR/"

ssh "$HOST" bash -s <<'REMOTE'
set -euo pipefail
cd /root/resolveloop
if [ ! -d .venv ]; then python3 -m venv .venv; fi
.venv/bin/pip install -q -U pip fastapi "uvicorn[standard]" pydantic httpx
if [ ! -f .env ]; then
  cp deploy/env.example .env
  sed -i "s/change-me/$(openssl rand -hex 24)/" .env
  echo "Created .env with a fresh API key:"; grep API_KEY .env
fi
cp deploy/resolveloop.service /etc/systemd/system/resolveloop.service
systemctl daemon-reload
systemctl enable --now resolveloop
systemctl restart resolveloop
sleep 1
curl -fsS http://127.0.0.1:8790/health && echo
if ! grep -q "location /resolveloop/" /etc/nginx/conf.d/allergylens.conf; then
  echo "NOTE: add deploy/nginx-resolveloop.conf inside the 443 server block of /etc/nginx/conf.d/allergylens.conf, then: nginx -t && systemctl reload nginx"
fi
REMOTE
