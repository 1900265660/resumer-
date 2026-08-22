<#
将已审阅草案冻结为不可变批准清单。仅在用户在对话中明确批准具体公司、岗位和当前附件后运行。
默认 -DryRun，只验证，不写入 jobs/approved。
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$DraftPath,
  [Parameter(Mandatory)][string]$ApprovalStatement,
  [switch]$Commit
)

$ErrorActionPreference = 'Stop'
if ($ApprovalStatement.Trim().Length -lt 8) { throw '批准说明过短；需要记录用户对具体岗位和当前附件的明确批准。' }
$draftFile = Get-Item -LiteralPath $DraftPath
$draft = Get-Content -LiteralPath $draftFile.FullName -Raw | ConvertFrom-Json
if ($draft.status -ne 'ready_for_user_approval') { throw "草案状态不是 ready_for_user_approval：$($draft.status)" }
foreach ($field in 'company','job_title','normalized_url','application_url','mode') {
  if ([string]::IsNullOrWhiteSpace([string]$draft.$field)) { throw "草案缺少字段：$field" }
}

$base = $draftFile.DirectoryName
foreach ($artifactName in 'jd','resume') {
  $artifact = $draft.$artifactName
  if (-not $artifact -or [string]::IsNullOrWhiteSpace($artifact.path) -or [string]::IsNullOrWhiteSpace($artifact.sha256)) {
    throw "草案缺少 $artifactName 的路径或哈希。"
  }
  $artifactPath = Join-Path $base $artifact.path
  if (-not (Test-Path -LiteralPath $artifactPath)) { throw "未找到 $artifactName：$artifactPath" }
  $actualHash = (Get-FileHash -LiteralPath $artifactPath -Algorithm SHA256).Hash
  if ($actualHash -ne $artifact.sha256) { throw "$artifactName 哈希不一致；必须重新审阅并生成新草案。" }
}

$approved = [ordered]@{
  schema_version = 1
  status = 'approved'
  approved_at = (Get-Date).ToString('o')
  approval_statement = $ApprovalStatement
  source_draft_sha256 = (Get-FileHash -LiteralPath $draftFile.FullName -Algorithm SHA256).Hash
  manifest = $draft
}
$slug = (($draft.company + '-' + $draft.job_title) -replace '[^\p{L}\p{N}\-]+','-').Trim('-').ToLowerInvariant()
if ([string]::IsNullOrWhiteSpace($slug)) { $slug = 'application' }
$root = Split-Path -Parent (Split-Path -Parent $base)
$targetDir = Join-Path $root 'jobs\approved'
$target = Join-Path $targetDir ("{0}-{1}.json" -f $slug, (Get-Date -Format 'yyyyMMddHHmmss'))

if (-not $Commit) {
  [pscustomobject]@{ status='dry_run_pass'; target=$target; company=$draft.company; job_title=$draft.job_title; resume_sha256=$draft.resume.sha256; jd_sha256=$draft.jd.sha256 } | ConvertTo-Json -Compress
  return
}
New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
$approved | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $target -Encoding utf8NoBOM -NoNewline
[pscustomobject]@{ status='approved'; path=$target; resume_sha256=$draft.resume.sha256; jd_sha256=$draft.jd.sha256 } | ConvertTo-Json -Compress
