$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw 'uv not found in Windows PATH' }
if (-not (Test-Path (Join-Path $root '.env'))) { throw 'Create .env from .env.example first' }
Set-Location (Join-Path $root 'backend')
uv sync --frozen --no-dev
if ($LASTEXITCODE -ne 0) { throw 'uv sync failed' }
uv run --frozen --no-dev --env-file ../.env uvicorn app.main:app --host 127.0.0.1 --port 8100
if ($LASTEXITCODE -ne 0) { throw 'FastAPI exited with an error' }
