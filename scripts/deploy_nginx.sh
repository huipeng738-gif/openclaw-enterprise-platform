#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
"$ROOT/scripts/build_frontend.sh"
sudo mkdir -p /var/www/openclaw-enterprise
sudo rm -rf /var/www/openclaw-enterprise/dist
sudo cp -r "$ROOT/frontend/dist" /var/www/openclaw-enterprise/dist
sudo cp "$ROOT/nginx/openclaw-enterprise.conf" /etc/nginx/sites-available/openclaw-enterprise
sudo ln -sfn /etc/nginx/sites-available/openclaw-enterprise /etc/nginx/sites-enabled/openclaw-enterprise
sudo nginx -t
sudo systemctl reload nginx
