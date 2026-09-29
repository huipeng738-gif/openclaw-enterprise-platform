#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN_DIR="$ROOT/plugin"
KNOWLEDGE_URL="${KNOWLEDGE_URL:-http://127.0.0.1:8100/knowledge/search}"
command -v openclaw >/dev/null || { echo "openclaw command not found"; exit 1; }
cd "$PLUGIN_DIR"
# WSL mounts can expose Windows files as world-writable; OpenClaw rejects them.
PLUGIN_MODE="$(stat -c '%a' "$PLUGIN_DIR")"
if (( (8#$PLUGIN_MODE & 2) != 0 )); then
  PLUGIN_INSTALL_DIR="${PLUGIN_INSTALL_DIR:-$HOME/.openclaw/local-plugins/platform-enterprise-data-tools}"
  mkdir -p "$PLUGIN_INSTALL_DIR"
  cp -R "$PLUGIN_DIR/." "$PLUGIN_INSTALL_DIR/"
  chmod -R go-w "$PLUGIN_INSTALL_DIR"
  PLUGIN_DIR="$PLUGIN_INSTALL_DIR"
fi
openclaw plugins install --link "$PLUGIN_DIR" --force --accept-capabilities
openclaw config set plugins.entries.enterprise-data-tools.config.knowledgeUrl "$KNOWLEDGE_URL"
openclaw config set plugins.entries.enterprise-data-tools.config.metricsUrl "http://127.0.0.1:8100/metrics/query"
openclaw config set plugins.entries.enterprise-data-tools.config.timeoutMs 15000
openclaw plugins enable enterprise-data-tools
openclaw plugins inspect enterprise-data-tools --runtime
