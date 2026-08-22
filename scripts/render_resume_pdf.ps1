<#
生成定制简历 PDF，并进行基础 ATS / 渲染自检。
示例：
.\scripts\render_resume_pdf.ps1 -SourceHtml <html> -OutputPdf <pdf> -ExpectedText '<name>','<phone>','<email>' -MaxPages 1
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$SourceHtml,
  [Parameter(Mandatory)][string]$OutputPdf,
  [Parameter(Mandatory)][string[]]$ExpectedText,
  [ValidateRange(1, 2)][int]$MaxPages = 2,
  [string]$RenderDirectory
)

$ErrorActionPreference = 'Stop'
$source = (Resolve-Path -LiteralPath $SourceHtml).Path
$output = [System.IO.Path]::GetFullPath($OutputPdf)
$outputParent = Split-Path -Parent $output
New-Item -ItemType Directory -Path $outputParent -Force | Out-Null

$chromeCandidates = @(
  'C:\Program Files\Google\Chrome\Application\chrome.exe',
  'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'
)
$chrome = $chromeCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $chrome) { throw '未发现 Google Chrome，无法生成 PDF。请安装 Chrome 或传入可用环境。' }

$poppler = 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin'
$pdfInfo = Join-Path $poppler 'pdfinfo.exe'
$pdfToPpm = Join-Path $poppler 'pdftoppm.exe'
if (-not (Test-Path -LiteralPath $pdfInfo) -or -not (Test-Path -LiteralPath $pdfToPpm)) {
  throw '未发现 Poppler（pdfinfo/pdftoppm），无法完成 PDF 验收。'
}

$fileUri = ([System.Uri]::new($source)).AbsoluteUri
$renderProfile = Join-Path $outputParent '.pdf-render-chrome-profile'
New-Item -ItemType Directory -Path $renderProfile -Force | Out-Null
$renderStartedAt = [DateTime]::UtcNow
& $chrome --headless=new --disable-gpu --no-pdf-header-footer "--user-data-dir=$renderProfile" "--print-to-pdf=$output" $fileUri
 $deadline = [DateTime]::UtcNow.AddSeconds(30)
 $pdfItem = $null
 do {
  if (Test-Path -LiteralPath $output) {
    $pdfItem = Get-Item -LiteralPath $output
    if ($pdfItem.LastWriteTimeUtc -ge $renderStartedAt.AddSeconds(-2)) { break }
  }
  Start-Sleep -Milliseconds 250
 } while ([DateTime]::UtcNow -lt $deadline)
if (-not $pdfItem -or $pdfItem.LastWriteTimeUtc -lt $renderStartedAt.AddSeconds(-2)) {
  throw "PDF 未在 30 秒内完成本次渲染：$output。拒绝复用旧附件。"
}

$info = & $pdfInfo $output
$pagesMatch = ($info | Select-String '^Pages:\s+(\d+)')
if (-not $pagesMatch) { throw '无法从 pdfinfo 读取页数。' }
$pages = [int]$pagesMatch.Matches[0].Groups[1].Value
if ($pages -gt $MaxPages) { throw "PDF 共 $pages 页，超过允许的 $MaxPages 页。" }

$python = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Source
if (-not $python) { throw '未发现 Python，无法检查 PDF 文本层。' }
$check = @'
from pypdf import PdfReader
import sys
reader = PdfReader(sys.argv[1])
text = "\n".join(page.extract_text() or "" for page in reader.pages)
missing = [item for item in sys.argv[2:] if item not in text]
if missing:
    raise SystemExit("PDF 文本层缺少：" + ", ".join(missing))
print("ATS_TEXT_OK")
'@
& $python -c $check $output @ExpectedText
if ($LASTEXITCODE -ne 0) { throw 'PDF 文本层校验失败。' }

if (-not $RenderDirectory) {
  $RenderDirectory = Join-Path $outputParent 'rendered'
}
New-Item -ItemType Directory -Path $RenderDirectory -Force | Out-Null
& $pdfToPpm -png -r 150 $output (Join-Path $RenderDirectory 'page')
if ($LASTEXITCODE -ne 0) { throw 'PDF 页面渲染失败。' }

[pscustomobject]@{
  status = 'pass'
  pdf = $output
  pages = $pages
  sha256 = (Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash
  renders = $RenderDirectory
} | ConvertTo-Json -Compress
