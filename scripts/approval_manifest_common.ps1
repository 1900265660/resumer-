Set-StrictMode -Version Latest

function Get-RequiredString {
  param([Parameter(Mandatory)]$Object, [Parameter(Mandatory)][string]$Name, [Parameter(Mandatory)][string]$Context)
  if ($Object -is [System.Collections.IDictionary]) {
    if (-not $Object.Contains($Name) -or [string]::IsNullOrWhiteSpace([string]$Object[$Name])) { throw "$Context 缺少字段：$Name" }
    return [string]$Object[$Name]
  }
  $property = $Object.PSObject.Properties[$Name]
  if (-not $property -or [string]::IsNullOrWhiteSpace([string]$property.Value)) { throw "$Context 缺少字段：$Name" }
  return [string]$property.Value
}

function Get-ObjectValue {
  param($Object, [Parameter(Mandatory)][string]$Name)
  if ($null -eq $Object) { return $null }
  if ($Object -is [System.Collections.IDictionary]) {
    if ($Object.Contains($Name)) { return $Object[$Name] }
    return $null
  }
  $property = $Object.PSObject.Properties[$Name]
  if ($property) { return $property.Value }
  return $null
}

function Resolve-ApplicationPath {
  param([Parameter(Mandatory)][string]$Base, [Parameter(Mandatory)][string]$RelativePath, [Parameter(Mandatory)][string]$Label)
  if ([System.IO.Path]::IsPathRooted($RelativePath)) { throw "$Label 必须使用岗位目录内的相对路径。" }
  $baseFull = [System.IO.Path]::GetFullPath($Base).TrimEnd('\', '/')
  $candidate = [System.IO.Path]::GetFullPath((Join-Path $baseFull $RelativePath))
  $prefix = $baseFull + [System.IO.Path]::DirectorySeparatorChar
  if (-not $candidate.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) { throw "$Label 路径越出岗位目录：$RelativePath" }
  return $candidate
}

function Get-VerifiedArtifact {
  param([Parameter(Mandatory)]$Draft, [Parameter(Mandatory)][string]$Base, [Parameter(Mandatory)][string]$Name)
  $property = $Draft.PSObject.Properties[$Name]
  if (-not $property -or -not $property.Value) { throw "草案缺少 $Name。" }
  $artifact = $property.Value
  $relativePath = Get-RequiredString $artifact 'path' "$Name 记录"
  $expectedHash = (Get-RequiredString $artifact 'sha256' "$Name 记录").ToLowerInvariant()
  if ($expectedHash -notmatch '^[0-9a-f]{64}$') { throw "$Name SHA-256 格式无效。" }
  $artifactPath = Resolve-ApplicationPath $Base $relativePath $Name
  if (-not (Test-Path -LiteralPath $artifactPath -PathType Leaf)) { throw "未找到 $Name：$artifactPath" }
  $actualHash = (Get-FileHash -LiteralPath $artifactPath -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actualHash -ne $expectedHash) { throw "$Name 哈希不一致；必须重新审阅并生成新草案。" }
  return [ordered]@{ path = $relativePath; sha256 = $actualHash }
}

function Get-VerifiedProjectArtifact {
  param([Parameter(Mandatory)]$Record, [Parameter(Mandatory)][string]$Base, [Parameter(Mandatory)][string]$Name)
  $applicationsDir = Split-Path -Parent $Base
  $projectRoot = Split-Path -Parent $applicationsDir
  if ((Split-Path -Leaf $applicationsDir) -ne 'applications' -or -not (Test-Path -LiteralPath (Join-Path $projectRoot 'AGENTS.md') -PathType Leaf)) {
    throw 'fast-assemble 来源只能解析本工作区内的文件。'
  }
  $relativePath = Get-RequiredString $Record 'path' "fast_assemble.$Name"
  if ([System.IO.Path]::IsPathRooted($relativePath)) { throw "fast_assemble.$Name 必须使用项目相对路径。" }
  $rootFull = [System.IO.Path]::GetFullPath($projectRoot).TrimEnd('\', '/')
  $artifactPath = [System.IO.Path]::GetFullPath((Join-Path $rootFull $relativePath))
  $prefix = $rootFull + [System.IO.Path]::DirectorySeparatorChar
  if (-not $artifactPath.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) { throw "fast_assemble.$Name 路径越出项目目录。" }
  if (-not (Test-Path -LiteralPath $artifactPath -PathType Leaf)) { throw "未找到 fast_assemble.$Name：$artifactPath" }
  $expectedHash = (Get-RequiredString $Record 'sha256' "fast_assemble.$Name").ToLowerInvariant()
  if ($expectedHash -notmatch '^[0-9a-f]{64}$') { throw "fast_assemble.$Name SHA-256 格式无效。" }
  $actualHash = (Get-FileHash -LiteralPath $artifactPath -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actualHash -ne $expectedHash) { throw "fast_assemble.$Name 哈希不一致；必须重新执行快速装配与审查。" }
  return [ordered]@{ path = ($relativePath -replace '\\','/'); sha256 = $actualHash }
}

function Get-CanonicalJsonSha256 {
  param([Parameter(Mandatory)][string]$Path)
  $code = "import hashlib,json,sys; data=json.load(open(sys.argv[1],encoding='utf-8')); raw=json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8'); print(hashlib.sha256(raw).hexdigest())"
  $hash = & python -c $code $Path
  if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace([string]$hash) -or [string]$hash -notmatch '^[0-9a-f]{64}$') { throw "无法计算规范化 JSON 哈希：$Path" }
  return ([string]$hash).Trim().ToLowerInvariant()
}

function Assert-ResumeContentMatch {
  param([Parameter(Mandatory)]$Expected, [Parameter(Mandatory)]$Actual, [Parameter(Mandatory)][string]$Context)
  foreach ($field in 'status','approved_run_id','transaction_id') {
    $expectedValue = Get-RequiredString $Expected $field '草案 resume_content'
    $actualValue = Get-RequiredString $Actual $field $Context
    if ($expectedValue -ne $actualValue) { throw "$Context 与草案 resume_content 的 $field 不一致。" }
  }
  $actualPointerProperty = $Actual.PSObject.Properties['current_pointer']
  if ($actualPointerProperty) {
    $expectedPointer = Get-RequiredString $Expected 'current_pointer' '草案 resume_content'
    if ($expectedPointer -ne [string]$actualPointerProperty.Value) { throw "$Context 与草案 resume_content 的 current_pointer 不一致。" }
  }
  $expectedTime = [datetimeoffset](Get-RequiredString $Expected 'updated_at' '草案 resume_content')
  $actualTime = [datetimeoffset](Get-RequiredString $Actual 'updated_at' $Context)
  if ($expectedTime -ne $actualTime) { throw "$Context 与草案 resume_content 的 updated_at 不一致。" }
}

function Get-CustomResumeProvenance {
  param([Parameter(Mandatory)]$Draft, [Parameter(Mandatory)][string]$Base)
  $resumeContentProperty = $Draft.PSObject.Properties['resume_content']
  if (-not $resumeContentProperty -or -not $resumeContentProperty.Value) { throw 'custom-resume 定制草案缺少 resume_content 摘要。' }
  $resumeContent = $resumeContentProperty.Value
  if ((Get-RequiredString $resumeContent 'status' '草案 resume_content') -ne 'approved') { throw 'custom-resume 内容状态不是 approved。' }
  if ((Get-RequiredString $resumeContent 'current_pointer' '草案 resume_content') -ne 'resume-content/current.json') { throw 'custom-resume 当前指针路径无效。' }

  $pointerPath = Resolve-ApplicationPath $Base 'resume-content/current.json' '内容批准指针'
  $manifestPath = Resolve-ApplicationPath $Base 'manifest.json' '岗位 manifest'
  foreach ($requiredPath in $pointerPath, $manifestPath) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) { throw "未找到内容批准文件：$requiredPath" }
  }
  $pointer = Get-Content -LiteralPath $pointerPath -Raw | ConvertFrom-Json
  if ([string]$pointer.schema_version -ne '1.5') { throw '新批准只接受 Schema 1.5 内容指针。' }
  $userApprovalId = Get-RequiredString $pointer 'user_approval_id' '内容批准指针'
  $pointerContentHash = (Get-RequiredString $pointer 'content_sha256' '内容批准指针').ToLowerInvariant()
  $jobManifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
  $manifestSummaryProperty = $jobManifest.PSObject.Properties['resume_content']
  if (-not $manifestSummaryProperty -or -not $manifestSummaryProperty.Value) { throw '岗位 manifest 缺少 resume_content 摘要。' }
  Assert-ResumeContentMatch $resumeContent $pointer 'resume-content/current.json'
  Assert-ResumeContentMatch $resumeContent $manifestSummaryProperty.Value 'manifest.resume_content'
  if ((Get-RequiredString $pointer 'status' '内容批准指针') -ne 'approved') { throw '内容批准指针已失效或变为 stale。' }

  $runId = Get-RequiredString $pointer 'approved_run_id' '内容批准指针'
  if ($runId -notmatch '^cr_[0-9]{8}T[0-9]{6}_[a-z0-9]{6}$') { throw '批准运行 ID 格式无效。' }
  $runRelativePath = Get-RequiredString $pointer 'run_relative_path' '内容批准指针'
  $expectedRunPath = "resume-content/runs/$runId"
  if (($runRelativePath -replace '\\','/') -ne $expectedRunPath) { throw '内容批准指针未指向批准运行。' }
  $runDir = Resolve-ApplicationPath $Base $expectedRunPath '内容运行目录'
  $runManifestPath = Join-Path $runDir 'run.json'
  $contentPath = Join-Path $runDir 'content-master.md'
  foreach ($requiredPath in $runManifestPath, $contentPath) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) { throw "批准运行缺少文件：$requiredPath" }
  }
  $runManifest = Get-Content -LiteralPath $runManifestPath -Raw | ConvertFrom-Json
  if ((Get-RequiredString $runManifest 'run_id' '运行清单') -ne $runId) { throw '运行清单 run_id 与批准指针不一致。' }
  if ([string]$runManifest.schema_version -ne '1.5') { throw '新批准只接受 Schema 1.5 运行。' }
  if ((Get-RequiredString $runManifest 'producer' '运行清单') -ne 'official_coordinator') { throw '运行不是由官方协调器生成。' }
  if ((Get-RequiredString $runManifest 'state' '运行清单') -notin @('ready_for_user_review','approved')) { throw '运行尚未完成 Schema 1.5 用户审阅前门禁。' }
  $requiredRunFiles = @(
    'jd-analysis.json','capability-transfer-map.json','experience-selection.json',
    'selection-audit-pre.json','story-plan.json','selection-user-approval.json',
    'draft-writer.json','draft-asu.json','draft-quality-audit.json','fusion.json',
    'quality-gate.json','audit.json','agent-receipts.json','hr-review.json'
  )
  foreach ($requiredName in $requiredRunFiles) {
    $record = @($runManifest.artifacts | Where-Object { $_.relative_path -eq $requiredName })
    if ($record.Count -ne 1) { throw "运行清单缺少唯一的 $requiredName 记录。" }
    $artifactPath = Join-Path $runDir $requiredName
    if (-not (Test-Path -LiteralPath $artifactPath -PathType Leaf)) { throw "批准运行缺少 $requiredName。" }
    $expectedHash = (Get-RequiredString $record[0] 'sha256' "$requiredName 记录").ToLowerInvariant()
    $actualHash = (Get-FileHash -LiteralPath $artifactPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($expectedHash -ne $actualHash) { throw "$requiredName 与不可变运行清单的哈希不一致。" }
  }
  $qualityGate = Get-Content -LiteralPath (Join-Path $runDir 'quality-gate.json') -Raw | ConvertFrom-Json
  if ($qualityGate.passed -ne $true -or @($qualityGate.hard_failures).Count -ne 0) { throw '确定性质量门未通过。' }
  $selectionApproval = Get-Content -LiteralPath (Join-Path $runDir 'selection-user-approval.json') -Raw | ConvertFrom-Json
  [void](Get-RequiredString $selectionApproval 'experience_selection_sha256' '选材用户批准记录')
  $storyPlanHash = Get-CanonicalJsonSha256 (Join-Path $runDir 'story-plan.json')
  if ((Get-RequiredString $selectionApproval 'story_plan_sha256' '选材用户批准记录').ToLowerInvariant() -ne $storyPlanHash) { throw '选材用户批准记录未绑定当前故事计划。' }
  $fusionHash = Get-CanonicalJsonSha256 (Join-Path $runDir 'fusion.json')
  if ((Get-RequiredString $qualityGate 'candidate_sha256' '确定性质量门').ToLowerInvariant() -ne $fusionHash) { throw '确定性质量门未绑定当前 Fusion。' }
  if ((Get-RequiredString $qualityGate 'story_plan_sha256' '确定性质量门').ToLowerInvariant() -ne $storyPlanHash) { throw '确定性质量门未绑定当前故事计划。' }
  $receiptBundle = Get-Content -LiteralPath (Join-Path $runDir 'agent-receipts.json') -Raw | ConvertFrom-Json
  $stageFiles = [ordered]@{
    jd_analysis = @('jd-analysis.json','coordinator')
    capability_transfer = @('capability-transfer-map.json','coordinator')
    experience_selection = @('experience-selection.json','coordinator')
    selection_audit = @('selection-audit-pre.json','auditor')
    story_plan = @('story-plan.json','writer')
    writer = @('draft-writer.json','writer')
    asu_writer = @('draft-asu.json','asu_writer')
    draft_audit = @('draft-quality-audit.json','auditor')
    fusion = @('fusion.json','coordinator')
    post_fusion_audit = @('audit.json','auditor')
    hr_review = @('hr-review.json','hr_reviewer')
  }
  foreach ($stageName in $stageFiles.Keys) {
    $filename = $stageFiles[$stageName][0]
    $expectedRole = $stageFiles[$stageName][1]
    $outputHash = Get-CanonicalJsonSha256 (Join-Path $runDir $filename)
    $matchingReceipts = @($receiptBundle.receipts | Where-Object { [string]$_.stage -eq $stageName -and [string]$_.role -eq $expectedRole -and [string]$_.output_sha256 -eq $outputHash })
    if ($matchingReceipts.Count -eq 0) { throw "调用回执未覆盖当前产物：$stageName/$filename" }
  }
  $hrReview = Get-Content -LiteralPath (Join-Path $runDir 'hr-review.json') -Raw | ConvertFrom-Json
  if ($hrReview.passed -ne $true -or [string]$hrReview.recommendation -ne 'strong_push' -or [double]$hrReview.overall_score -lt 9.0) { throw 'HR 决策门未达到 Schema 1.5 标准。' }
  foreach ($dimensionName in 'role_fit','narrative_completeness','evidence_specificity','decision_readiness','credibility','content_fullness') {
    $dimension = $hrReview.PSObject.Properties[$dimensionName].Value
    if (-not $dimension -or [double]$dimension.score -lt 8.0 -or @($dimension.evidence_bullet_ids).Count -eq 0) { throw "HR 决策维度 $dimensionName 缺少达标分数或最终 bullet 证据。" }
  }
  foreach ($experienceReview in @($hrReview.experience_reviews)) {
    if (@($experienceReview.evidence_bullet_ids).Count -eq 0) { throw 'HR 逐经历判断缺少最终 bullet 证据。' }
  }
  $statusLedgerPath = Join-Path $Base 'resume-content/run-status.jsonl'
  if (-not (Test-Path -LiteralPath $statusLedgerPath -PathType Leaf)) { throw '缺少运行状态账本。' }
  $latestStatus = $null
  foreach ($line in Get-Content -LiteralPath $statusLedgerPath) {
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    $statusRecord = $line | ConvertFrom-Json
    if ([string]$statusRecord.run_id -eq $runId) { $latestStatus = $statusRecord }
  }
  if (-not $latestStatus -or [string]$latestStatus.status -ne 'approved') { throw "运行状态不是最终 approved：$([string]$latestStatus.status)。" }
  $contentRecord = @($runManifest.artifacts | Where-Object { $_.relative_path -eq 'content-master.md' })
  if ($contentRecord.Count -ne 1) { throw '运行清单必须且只能登记一个 content-master.md。' }
  $expectedContentHash = (Get-RequiredString $contentRecord[0] 'sha256' 'content-master.md 记录').ToLowerInvariant()
  $actualContentHash = (Get-FileHash -LiteralPath $contentPath -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actualContentHash -ne $expectedContentHash) { throw 'content-master.md 与不可变运行清单的哈希不一致。' }
  if ($actualContentHash -ne $pointerContentHash) { throw '内容批准指针未绑定当前 content-master.md。' }
  $approvalPath = Resolve-ApplicationPath $Base "resume-content/approvals/$userApprovalId.json" '用户批准记录'
  if (-not (Test-Path -LiteralPath $approvalPath -PathType Leaf)) { throw '缺少显式用户批准记录。' }
  $approval = Get-Content -LiteralPath $approvalPath -Raw | ConvertFrom-Json
  if ((Get-RequiredString $approval 'user_approval_id' '用户批准记录') -ne $userApprovalId -or (Get-RequiredString $approval 'run_id' '用户批准记录') -ne $runId -or (Get-RequiredString $approval 'content_sha256' '用户批准记录').ToLowerInvariant() -ne $actualContentHash) { throw '用户批准记录与最终内容不一致。' }

  return [ordered]@{
    content_pipeline = 'custom-resume'
    approved_run_id = $runId
    transaction_id = Get-RequiredString $pointer 'transaction_id' '内容批准指针'
    approved_at = ([datetimeoffset](Get-RequiredString $pointer 'approved_at' '内容批准指针')).ToString('o')
    user_approval_id = $userApprovalId
    content_master_path = "$expectedRunPath/content-master.md"
    content_master_sha256 = $actualContentHash
  }
}

function Get-FastAssembleProvenance {
  param([Parameter(Mandatory)]$Draft, [Parameter(Mandatory)][string]$Base)
  $property = $Draft.PSObject.Properties['fast_assemble']
  if (-not $property -or -not $property.Value) { throw 'fast-assemble 草案缺少 fast_assemble 来源记录。' }
  $source = $property.Value
  $required = @('facts','claims','jd','selection','content','hr_review','resume_yaml','pdf')
  $verified = [ordered]@{}
  foreach ($name in $required) {
    $recordProperty = $source.PSObject.Properties[$name]
    if (-not $recordProperty -or -not $recordProperty.Value) { throw "fast_assemble 缺少 $name 记录。" }
    $verified[$name] = Get-VerifiedProjectArtifact $recordProperty.Value $Base $name
  }

  $applicationsDir = Split-Path -Parent $Base
  $projectRoot = Split-Path -Parent $applicationsDir
  $hrPath = Join-Path $projectRoot $verified.hr_review.path
  $review = Get-Content -LiteralPath $hrPath -Raw | ConvertFrom-Json
  if ([string]$review.schema_version -ne '1.0' -or [string]$review.decision -ne 'pass' -or $review.requires_manual_review -ne $false -or @($review.exact_repairs).Count -ne 0) {
    throw 'fast-assemble 四项 HR 门禁尚未全部通过。'
  }
  $checksProperty = $review.PSObject.Properties['checks']
  if (-not $checksProperty -or -not $checksProperty.Value) { throw 'fast-assemble HR 审查缺少 checks。' }
  foreach ($gate in 'position_context','relevance','truth_and_contact','supported_capability_coverage') {
    $gateProperty = $checksProperty.Value.PSObject.Properties[$gate]
    if (-not $gateProperty -or $gateProperty.Value.passed -ne $true -or @($gateProperty.Value.findings).Count -ne 0) {
      throw "fast-assemble HR 门禁未通过：$gate"
    }
  }

  $contentPath = Join-Path $projectRoot $verified.content.path
  $content = Get-Content -LiteralPath $contentPath -Raw | ConvertFrom-Json
  if ([string]$content.content_pipeline -ne 'fast-assemble') { throw '快速内容文件的 content_pipeline 无效。' }
  if ([string]$content.company -ne [string]$Draft.company -or [string]$content.target_role -ne [string]$Draft.job_title) {
    throw '快速内容文件与草案公司或岗位名不一致。'
  }
  $draftResume = Get-VerifiedArtifact $Draft $Base 'resume'
  if ($verified.pdf.sha256 -ne $draftResume.sha256) { throw 'fast_assemble.pdf 与草案 resume 附件不是同一文件。' }

  return [ordered]@{
    content_pipeline = 'fast-assemble'
    generation_round = [int]$review.generation_round
    artifacts = $verified
  }
}

function Get-ContentProvenance {
  param([Parameter(Mandatory)]$Draft, [Parameter(Mandatory)][string]$Base)
  $mode = Get-RequiredString $Draft 'mode' '草案'
  $pipeline = Get-RequiredString $Draft 'content_pipeline' '草案'
  $isTailored = $mode -in @('定制', 'custom', 'tailored')
  if ($isTailored -and $pipeline -eq 'custom-resume') { return Get-CustomResumeProvenance $Draft $Base }
  if ($isTailored -and $pipeline -eq 'fast-assemble') { return Get-FastAssembleProvenance $Draft $Base }
  if ($isTailored -and $pipeline -eq 'legacy-explicit-fallback') {
    $fallbackProperty = $Draft.PSObject.Properties['legacy_fallback']
    if (-not $fallbackProperty -or -not $fallbackProperty.Value) { throw '旧版定制回退缺少 legacy_fallback 记录。' }
    $fallback = $fallbackProperty.Value
    if ($fallback.approved -ne $true) { throw '旧版定制回退未记录用户明确批准。' }
    $reason = Get-RequiredString $fallback 'reason' 'legacy_fallback'
    $statement = Get-RequiredString $fallback 'approval_statement' 'legacy_fallback'
    if ($statement.Trim().Length -lt 8) { throw '旧版定制回退批准说明过短。' }
    return [ordered]@{
      content_pipeline = 'legacy-explicit-fallback'
      reason = $reason
      approval_statement = $statement
      approved_at = ([datetimeoffset](Get-RequiredString $fallback 'approved_at' 'legacy_fallback')).ToString('o')
    }
  }
  if (-not $isTailored -and $pipeline -eq 'existing-material') { return [ordered]@{ content_pipeline = 'existing-material' } }
  throw "mode=$mode 不允许使用 content_pipeline=$pipeline。"
}

function Assert-ContentProvenanceMatch {
  param([Parameter(Mandatory)]$Expected, [Parameter(Mandatory)]$Actual)
  $pipeline = Get-RequiredString $Expected 'content_pipeline' '冻结内容来源'
  if ($pipeline -ne (Get-RequiredString $Actual 'content_pipeline' '当前内容来源')) { throw '内容管线已变化。' }
  if ($pipeline -eq 'custom-resume') {
    foreach ($field in 'approved_run_id','transaction_id','content_master_path','content_master_sha256','user_approval_id') {
      if ((Get-RequiredString $Expected $field '冻结内容来源') -ne (Get-RequiredString $Actual $field '当前内容来源')) { throw "custom-resume 内容来源的 $field 已变化。" }
    }
    if ([datetimeoffset](Get-RequiredString $Expected 'approved_at' '冻结内容来源') -ne [datetimeoffset](Get-RequiredString $Actual 'approved_at' '当前内容来源')) { throw 'custom-resume 内容批准时间已变化。' }
    return
  }
  if ($pipeline -eq 'fast-assemble') {
    if ([int]$Expected.generation_round -ne [int]$Actual.generation_round) { throw 'fast-assemble HR 审查轮次已变化。' }
    foreach ($name in 'facts','claims','jd','selection','content','hr_review','resume_yaml','pdf') {
      $expectedArtifact = Get-ObjectValue $Expected.artifacts $name
      $actualArtifact = Get-ObjectValue $Actual.artifacts $name
      foreach ($field in 'path','sha256') {
        if ((Get-RequiredString $expectedArtifact $field "冻结 fast-assemble.$name") -ne (Get-RequiredString $actualArtifact $field "当前 fast-assemble.$name")) {
          throw "fast-assemble 内容来源的 $name.$field 已变化。"
        }
      }
    }
    return
  }
  if ($pipeline -eq 'legacy-explicit-fallback') {
    foreach ($field in 'reason','approval_statement') {
      if ((Get-RequiredString $Expected $field '冻结回退来源') -ne (Get-RequiredString $Actual $field '当前回退来源')) { throw "旧版回退的 $field 已变化。" }
    }
    if ([datetimeoffset](Get-RequiredString $Expected 'approved_at' '冻结回退来源') -ne [datetimeoffset](Get-RequiredString $Actual 'approved_at' '当前回退来源')) { throw '旧版回退批准时间已变化。' }
  }
}

function Test-ApplicationDraft {
  param([Parameter(Mandatory)][System.IO.FileInfo]$DraftFile)
  $draft = Get-Content -LiteralPath $DraftFile.FullName -Raw | ConvertFrom-Json
  if ((Get-RequiredString $draft 'status' '草案') -ne 'ready_for_user_approval') { throw "草案状态不是 ready_for_user_approval：$($draft.status)" }
  foreach ($field in 'company','job_title','normalized_url','application_url','mode') { [void](Get-RequiredString $draft $field '草案') }
  foreach ($urlField in 'normalized_url','application_url') {
    $uri = $null
    if (-not [System.Uri]::TryCreate([string]$draft.$urlField, [System.UriKind]::Absolute, [ref]$uri) -or $uri.Scheme -notin @('http','https')) { throw "草案 $urlField 不是有效的 HTTP(S) URL。" }
  }
  $reviewChecksProperty = $draft.PSObject.Properties['review_checks']
  if (-not $reviewChecksProperty -or -not $reviewChecksProperty.Value) { throw '草案缺少 review_checks。' }
  foreach ($check in 'pdf_visual','pdf_text_layer','ats') {
    if ((Get-RequiredString $reviewChecksProperty.Value $check 'review_checks') -ne 'passed') { throw "review_checks.$check 未通过。" }
  }
  $base = $DraftFile.DirectoryName
  $artifacts = [ordered]@{}
  foreach ($artifactName in 'jd','resume','answers','review') { $artifacts[$artifactName] = Get-VerifiedArtifact $draft $base $artifactName }
  $provenance = Get-ContentProvenance $draft $base
  $applicationsDir = Split-Path -Parent $base
  $projectRoot = Split-Path -Parent $applicationsDir
  if ((Split-Path -Leaf $applicationsDir) -ne 'applications' -or -not (Test-Path -LiteralPath (Join-Path $projectRoot 'AGENTS.md') -PathType Leaf)) { throw '草案必须位于本工作区 applications/<公司>_<岗位>/ 内。' }
  return [pscustomobject]@{ draft = $draft; base = $base; project_root = $projectRoot; artifacts = $artifacts; content_provenance = $provenance }
}
