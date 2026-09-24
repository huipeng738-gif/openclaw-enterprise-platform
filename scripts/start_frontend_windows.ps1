$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'npm.cmd not found in Windows PATH' }
Set-Location (Join-Path $root 'frontend')
if (-not (Test-Path node_modules)) {
  npm.cmd ci
  if ($LASTEXITCODE -ne 0) { throw 'npm ci failed' }
}
npm.cmd run dev -- --host 127.0.0.1
if ($LASTEXITCODE -ne 0) { throw 'Frontend exited with an error' }
