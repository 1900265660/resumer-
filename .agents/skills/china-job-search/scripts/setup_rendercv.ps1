[CmdletBinding()]
param(
  [string]$VenvPath = '.tmp/rendercv-2.8',
  [string]$Python = 'python'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillDir = Split-Path -Parent $scriptDir
$requirements = Join-Path $skillDir 'requirements-rendercv.txt'
$resolvedVenv = [System.IO.Path]::GetFullPath($VenvPath)
$taskTemp = Join-Path (Split-Path -Parent $resolvedVenv) 'rendercv-install-temp'
$pipCache = Join-Path (Split-Path -Parent $resolvedVenv) 'rendercv-pip-cache'
New-Item -ItemType Directory -Force -Path $taskTemp, $pipCache | Out-Null
$env:TEMP = $taskTemp
$env:TMP = $taskTemp
$env:PIP_CACHE_DIR = $pipCache

if (-not (Test-Path -LiteralPath (Join-Path $resolvedVenv 'Scripts/python.exe') -PathType Leaf)) {
  & $Python -m venv $resolvedVenv
  if ($LASTEXITCODE -ne 0) { throw 'Failed to create the RenderCV virtual environment.' }
}
$venvPython = Join-Path $resolvedVenv 'Scripts/python.exe'
& $venvPython -m pip install --disable-pip-version-check -r $requirements
if ($LASTEXITCODE -ne 0) { throw 'Failed to install pinned RenderCV dependencies.' }
& (Join-Path $resolvedVenv 'Scripts/rendercv.exe') --version
if ($LASTEXITCODE -ne 0) { throw 'RenderCV version verification failed.' }
