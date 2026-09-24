#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/backend"
command -v uv >/dev/null || { echo 'uv command not found' >&2; exit 1; }
uv sync --frozen --no-dev
[ -f "$ROOT/.env" ] && set -a && . "$ROOT/.env" && set +a
export GATEWAY_IDENTITY_PATH="${GATEWAY_IDENTITY_PATH:-$ROOT/backend/.data/gateway-device.pem}"
exec uv run --frozen --no-dev python -m app.worker
