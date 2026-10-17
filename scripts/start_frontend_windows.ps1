
$ErrorActionPreference = 'Stop'

# 1. 获取项目根目录
$root = Split-Path -Parent $PSScriptRoot

# 2. 检查 Node.js 和 npm
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw 'Node.js not found in Windows PATH'
}

if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw 'npm.cmd not found in Windows PATH'
}

# 3. 进入前端目录
Set-Location (Join-Path $root 'frontend')

# 4. 检查并安装依赖
if (-not (Test-Path 'node_modules')) {
    Write-Host 'Installing frontend dependencies...'
    npm.cmd ci

    if ($LASTEXITCODE -ne 0) {
        throw 'npm ci failed'
    }
}

# 5. 启动 Vite 本地开发服务器
Write-Host 'Starting Vue frontend...'

npm.cmd run dev -- --host 127.0.0.1

if ($LASTEXITCODE -ne 0) {
    throw 'Frontend exited with an error'
}
