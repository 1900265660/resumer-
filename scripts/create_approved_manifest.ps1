<#
将已审阅草案冻结为不可变批准清单。仅在用户在对话中明确批准具体公司、岗位和当前附件后运行。
默认 Dry Run，只验证，不写入 jobs/approved。
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$DraftPath,
  [Parameter(Mandatory)][string]$ApprovalStatement,
  [switch]$Commit
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'approval_manifest_common.ps1')

if ($ApprovalStatement.Trim().Length -lt 8) { throw '批准说明过短；需要记录用户对具体岗位和当前附件的明确批准。' }
$draftFile = Get-Item -LiteralPath $DraftPath
$validation = Test-ApplicationDraft $draftFile
$draft = $validation.draft
$root = $validation.project_root
$rootPrefix = $root.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
if (-not $draftFile.FullName.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) { throw '草案路径不在项目目录内。' }
$relativeDraftPath = $draftFile.FullName.Substring($rootPrefix.Length) -replace '\\','/'
$approvedRunId = if ($validation.content_provenance.Contains('approved_run_id')) { $validation.content_provenance['approved_run_id'] } else { $null }

$approved = [ordered]@{
  schema_version = 2
  status = 'approved'
  approved_at = (Get-Date).ToString('o')
  approval_statement = $ApprovalStatement
  source_draft_path = $relativeDraftPath
  source_draft_sha256 = (Get-FileHash -LiteralPath $draftFile.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
  content_provenance = $validation.content_provenance
  manifest = $draft
}
$slug = (($draft.company + '-' + $draft.job_title) -replace '[^\p{L}\p{N}\-]+','-').Trim('-').ToLowerInvariant()
if ([string]::IsNullOrWhiteSpace($slug)) { $slug = 'application' }
$targetDir = Join-Path $root 'jobs\approved'
$target = Join-Path $targetDir ("{0}-{1}.json" -f $slug, (Get-Date -Format 'yyyyMMddHHmmssfff'))

if (-not $Commit) {
  [pscustomobject]@{
    status = 'dry_run_pass'
    target = $target
    company = $draft.company
    job_title = $draft.job_title
    content_pipeline = $validation.content_provenance.content_pipeline
    approved_run_id = $approvedRunId
    resume_sha256 = $validation.artifacts.resume.sha256
    jd_sha256 = $validation.artifacts.jd.sha256
  } | ConvertTo-Json -Compress
  return
}
New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
if (Test-Path -LiteralPath $target) { throw '批准清单目标已存在；拒绝覆盖不可变清单。' }
$approved | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $target -Encoding utf8NoBOM -NoNewline
[pscustomobject]@{
  status = 'approved'
  path = $target
  content_pipeline = $validation.content_provenance.content_pipeline
  approved_run_id = $approvedRunId
  resume_sha256 = $validation.artifacts.resume.sha256
  jd_sha256 = $validation.artifacts.jd.sha256
} | ConvertTo-Json -Compress
