$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw 'uv not found in Windows PATH' }
if (-not (Test-Path (Join-Path $root '.env'))) { throw 'Create .env from .env.example first' }
Set-Location (Join-Path $root 'backend')
New-Item -ItemType Directory -Force .data | Out-Null
$env:GATEWAY_IDENTITY_PATH = Join-Path (Get-Location) '.data/gateway-device.pem'
uv sync --frozen --no-dev
if ($LASTEXITCODE -ne 0) { throw 'uv sync failed' }
uv run --frozen --no-dev --env-file ../.env python -m app.worker
if ($LASTEXITCODE -ne 0) { throw 'Worker exited with an error' }
