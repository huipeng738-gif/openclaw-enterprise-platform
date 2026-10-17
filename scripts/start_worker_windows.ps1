
$ErrorActionPreference = 'Stop'

# 1. 获取项目根目录
$root = Split-Path -Parent $PSScriptRoot

# 2. 检查 uv 是否已安装
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'uv not found in Windows PATH'
}

# 3. 检查 .env 配置文件
if (-not (Test-Path (Join-Path $root '.env'))) {
    throw 'Create .env from .env.example first'
}

# 4. 进入 backend 目录
Set-Location (Join-Path $root 'backend')

# 5. 创建 Gateway 设备身份文件目录
New-Item -ItemType Directory -Force .data | Out-Null

# 6. 配置 Gateway 设备身份文件路径
$env:GATEWAY_IDENTITY_PATH = Join-Path (Get-Location) '.data/gateway-device.pem'

# 7. 同步 Python 依赖
uv sync --frozen --no-dev
if ($LASTEXITCODE -ne 0) {
    throw 'uv sync failed'
}

# 8. 启动 Python Worker，读取 .env
uv run --frozen --no-dev `
    --env-file ../.env `
    python -m app.worker

if ($LASTEXITCODE -ne 0) {
    throw 'Worker exited with an error'
}
