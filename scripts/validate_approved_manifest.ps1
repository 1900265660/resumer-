<#
在打开网申页面前复验不可变批准清单及其当前内容、JD、答案、review 和附件来源。
#>
[CmdletBinding()]
param([Parameter(Mandatory)][string]$ApprovedPath)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'approval_manifest_common.ps1')

$approvedFile = Get-Item -LiteralPath $ApprovedPath
$approvedDir = $approvedFile.DirectoryName
$jobsDir = Split-Path -Parent $approvedDir
$root = Split-Path -Parent $jobsDir
if ((Split-Path -Leaf $approvedDir) -ne 'approved' -or (Split-Path -Leaf $jobsDir) -ne 'jobs') { throw '批准清单必须位于 jobs/approved/。' }
$approved = Get-Content -LiteralPath $approvedFile.FullName -Raw | ConvertFrom-Json
if ($approved.schema_version -ne 2 -or $approved.status -ne 'approved') { throw '批准清单 Schema 或状态无效；必须重新创建批准清单。' }
$relativeDraftPath = Get-RequiredString $approved 'source_draft_path' '批准清单'
if ([System.IO.Path]::IsPathRooted($relativeDraftPath)) { throw '批准清单的 source_draft_path 必须是项目相对路径。' }
$rootFull = [System.IO.Path]::GetFullPath($root).TrimEnd('\', '/')
$draftPath = [System.IO.Path]::GetFullPath((Join-Path $rootFull $relativeDraftPath))
$rootPrefix = $rootFull + [System.IO.Path]::DirectorySeparatorChar
if (-not $draftPath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) { throw '批准清单的源草案路径越出项目目录。' }
if (-not (Test-Path -LiteralPath $draftPath -PathType Leaf)) { throw "批准清单的源草案不存在：$draftPath" }
$actualDraftHash = (Get-FileHash -LiteralPath $draftPath -Algorithm SHA256).Hash.ToLowerInvariant()
$expectedDraftHash = (Get-RequiredString $approved 'source_draft_sha256' '批准清单').ToLowerInvariant()
if ($actualDraftHash -ne $expectedDraftHash) { throw '源草案哈希已变化；批准清单失效。' }

$draftFile = Get-Item -LiteralPath $draftPath
$validation = Test-ApplicationDraft $draftFile
$freshManifest = $validation.draft | ConvertTo-Json -Depth 20 -Compress
$frozenManifest = $approved.manifest | ConvertTo-Json -Depth 20 -Compress
if ($freshManifest -ne $frozenManifest) { throw '批准清单内嵌 manifest 与源草案不一致。' }
Assert-ContentProvenanceMatch $approved.content_provenance $validation.content_provenance
$approvedRunProperty = $approved.content_provenance.PSObject.Properties['approved_run_id']
$approvedRunId = if ($approvedRunProperty) { $approvedRunProperty.Value } else { $null }

[pscustomobject]@{
  status = 'validation_pass'
  approved_path = $approvedFile.FullName
  company = $approved.manifest.company
  job_title = $approved.manifest.job_title
  content_pipeline = $approved.content_provenance.content_pipeline
  approved_run_id = $approvedRunId
  resume_sha256 = $validation.artifacts.resume.sha256
} | ConvertTo-Json -Compress
