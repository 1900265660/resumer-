[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$modulePath = Join-Path $projectRoot 'tools\browser-application'
$entry = Join-Path $modulePath 'dist\server.js'
if (-not (Test-Path -LiteralPath $entry)) { throw '请先执行 tools/browser-application 的安装和 setup。' }

# Codex 启动本地 MCP 时可能没有把 Node 放进 PATH；这里显式解析 node.exe，
# 避免依赖当前会话的 PATH 而导致“无法启动 job_application”。
$nodeCandidates = @(
    $env:CODEX_MCP_NODE_PATH,
    (Get-Command node -ErrorAction SilentlyContinue).Source,
    'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
)
$nodePath = $nodeCandidates |
    Where-Object { $_ -and (Test-Path -LiteralPath $_) } |
    Select-Object -First 1
if (-not $nodePath) { throw '未找到 node.exe；请确认已安装 Node.js 22+。' }

$env:CODEX_APPLICATION_ROOT = $projectRoot
$env:CODEX_APPLICATION_PWSH = (Get-Process -Id $PID).Path
& $nodePath $entry
exit $LASTEXITCODE
