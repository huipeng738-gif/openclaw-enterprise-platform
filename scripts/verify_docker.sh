#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v docker >/dev/null || { echo 'Docker CLI missing' >&2; exit 1; }
docker info >/dev/null || { echo 'Docker daemon unavailable' >&2; exit 1; }
docker compose config --quiet
docker compose ps
python3 scripts/verify.py
