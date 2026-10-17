
$ErrorActionPreference = 'Stop'

# 1. 获取脚本绝对路径
$scriptPath = $PSCommandPath

if ([string]::IsNullOrWhiteSpace($scriptPath)) {
    $scriptPath = $MyInvocation.MyCommand.Path
}

if ([string]::IsNullOrWhiteSpace($scriptPath)) {
    throw 'Cannot resolve the current script path'
}

# 2. 获取项目根目录
$scriptDir = Split-Path -Path $scriptPath -Parent
$root = Split-Path -Path $scriptDir -Parent

if ([string]::IsNullOrWhiteSpace($root) -or
    -not (Test-Path -LiteralPath $root -PathType Container)) {
    throw "Invalid project root: $root"
}

# 3. 检查 backend 目录
$backendDir = Join-Path $root 'backend'

if (-not (Test-Path -LiteralPath $backendDir -PathType Container)) {
    throw "Backend directory not found: $backendDir"
}

# 4. 检查 .env 配置
$envFile = Join-Path $root '.env'

if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
    throw "Missing .env file: $envFile"
}

# 5. 检查 uv 命令
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'uv not found in Windows PATH'
}

Write-Host "Project root: $root"
Write-Host "Backend directory: $backendDir"

# 6. 进入 backend 目录
Push-Location -LiteralPath $backendDir

try {
    # 7. 同步 Python 依赖
    uv sync --frozen --no-dev

    if ($LASTEXITCODE -ne 0) {
        throw "uv sync failed: $LASTEXITCODE"
    }

    # 8. 启动 FastAPI（启用热重载）
    uv run --frozen --no-dev `
        --env-file $envFile `
        uvicorn app.main:app `
        --host 127.0.0.1 `
        --port 8100 `
        --reload

    if ($LASTEXITCODE -ne 0) {
        throw "FastAPI exited with an error: $LASTEXITCODE"
    }
}
finally {
    # 9. 恢复原来的工作目录
    Pop-Location
}
