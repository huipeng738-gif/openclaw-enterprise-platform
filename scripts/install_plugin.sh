#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN_DIR="$ROOT/plugin"
command -v openclaw >/dev/null || { echo "openclaw command not found"; exit 1; }
command -v npm >/dev/null || { echo "npm command not found"; exit 1; }
if grep -q "示例入口" "$PLUGIN_DIR/src/index.ts"; then
  echo "Replace placeholder plugin/src/index.ts with your original plugin before install" >&2
  exit 2
fi
cd "$PLUGIN_DIR"
npm install
openclaw plugins build --root "$PLUGIN_DIR"
openclaw plugins validate --root "$PLUGIN_DIR"
openclaw plugins install --link "$PLUGIN_DIR" --force
openclaw config set plugins.entries.enterprise-data-tools.config.knowledgeUrl "http://127.0.0.1:8100/knowledge/search"
openclaw config set plugins.entries.enterprise-data-tools.config.metricsUrl "http://127.0.0.1:8100/metrics/query"
openclaw config set plugins.entries.enterprise-data-tools.config.timeoutMs 15000
openclaw plugins enable enterprise-data-tools || true
openclaw plugins inspect enterprise-data-tools --runtime || true
