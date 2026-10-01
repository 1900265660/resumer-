from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / ".agents" / "skills" / "china-job-search" / "scripts" / "fast_resume.py"
SPEC = importlib.util.spec_from_file_location("fast_resume", MODULE_PATH)
assert SPEC and SPEC.loader
fast_resume = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fast_resume)


def _profile(*fact_ids: str) -> str:
    return "\n".join(
        f"- 已确认事实 {index} <!-- fact_id: {fact_id}; provenance: observed -->"
        for index, fact_id in enumerate(fact_ids, start=1)
    )


def _claim(
    experience_id: str,
    fact_ids: list[str],
    *,
    text: str = "负责需求拆解并推进跨团队交付，按计划完成验收。",
    context: str = "both",
    section: str = "实践经历",
) -> dict[str, object]:
    return {
        "claim_id": "CLAIM-" + fast_resume.sha256_bytes(text.encode("utf-8"))[:12],
        "experience_id": experience_id,
        "fact_ids": fact_ids,
        "text": text,
        "capability_tags": ["项目推进"],
        "role_families": ["general", "ai_product_manager"],
        "context": context,
        "section": section,
        "heading": "示例项目｜负责人｜2026/01–2026/06",
        "source": {
            "application_dir": "applications/example",
            "run_id": "run-1",
            "fusion_sha256": "a" * 64,
            "source_files": [],
            "approval_basis": "user_approved_current",
        },
        "status": "active",
    }


def _contact() -> dict[str, str]:
    return {
        "name": "测试候选人",
        "phone": "13800138000",
        "email": "test@example.com",
        "location": "上海",
    }


def test_vertical_coverage_distinguishes_sparse_and_filled_single_pages() -> None:
    assert fast_resume._vertical_coverage_from_positions(842, []) is None
    assert fast_resume._vertical_coverage_from_positions(842, [(410, 10)]) < 0.05
    assert fast_resume._vertical_coverage_from_positions(842, [(90, 10), (770, 10)]) > 0.8


def test_text_position_combines_current_and_text_matrices() -> None:
    # RenderCV places its page-space translation in the current matrix while
    # leaving the text matrix at the origin.
    assert fast_resume._text_position_y(
        [1, 0, 0, -1, 60, 710], [1, 0, 0, 1, 0, 0]
    ) == 710


def test_library_scan_deduplicates_and_quarantines_conflicts(tmp_path: Path) -> None:
    source = tmp_path / "latest"
    source.mkdir()
    clean = "围绕用户反馈拆解需求并形成原型，完成多轮验证后交付可运行版本。"
    (source / "a.md").write_text(clean + "\n环比增长 300%", encoding="utf-8")
    (source / "duplicate.md").write_text(clean + "\n环比增长 300%", encoding="utf-8")
    before = _profile("FACT-PROJECT-001-01")
    report = fast_resume.scan_fact_candidates(source, before)
    assert report["summary"]["unique_files"] == 1
    assert report["summary"]["duplicate_files"] == 1
    assert report["summary"]["profile_was_modified"] is False
    classifications = {item["classification"] for item in report["fact_diff_candidates"]}
    assert "new_candidate" in classifications
    assert "conflict_or_withdrawn" in classifications
    assert before == _profile("FACT-PROJECT-001-01")


def test_confirmed_candidate_maps_to_existing_facts_without_profile_rewrite(
    tmp_path: Path,
) -> None:
    source = tmp_path / "latest"
    source.mkdir()
    text = "负责需求拆解并推进跨团队交付，按计划完成验收。"
    (source / "approved.md").write_text(text, encoding="utf-8")
    candidate_id = "FACT-CAND-" + fast_resume.sha256_bytes(
        fast_resume.canonical_text(text).lower().encode("utf-8")
    )[:12]
    profile = _profile("FACT-PROJECT-001-01")
    report = fast_resume.scan_fact_candidates(
        source,
        profile,
        confirmed_candidates={
            candidate_id: {
                "fact_ids": ["FACT-PROJECT-001-01"],
                "confirmed_at": "2026-09-23",
            }
        },
    )
    item = next(value for value in report["fact_diff_candidates"] if value["candidate_id"] == candidate_id)
    assert item["classification"] == "confirmed_existing_fact"
    assert item["mapped_fact_ids"] == ["FACT-PROJECT-001-01"]
    assert report["review_queue"] == []
    assert profile == _profile("FACT-PROJECT-001-01")


def test_fact_confirmation_loader_rejects_missing_fact_mapping(tmp_path: Path) -> None:
    source = tmp_path / "latest"
    source.mkdir()
    (source / "approved.md").write_text(
        "负责需求拆解并推进跨团队交付，按计划完成验收。", encoding="utf-8"
    )
    profile_path = tmp_path / "profile" / "01-candidate-profile.md"
    profile_path.parent.mkdir()
    profile_path.write_text(_profile("FACT-PROJECT-001-01"), encoding="utf-8")
    drafts = profile_path.parent / "drafts"
    fast_resume.write_json(
        drafts / "fast-assemble-fact-confirmation-test.json",
        {
            "status": "confirmed_and_mapped",
            "confirmed_at": "2026-09-23T00:00:00+08:00",
            "items": [
                {
                    "candidate_id": "FACT-CAND-000000000000",
                    "fact_ids": ["FACT-PROJECT-999-01"],
                }
            ],
        },
    )
    baseline = tmp_path / "baseline.json"
    fast_resume.write_json(baseline, {"items": []})
    with pytest.raises(fast_resume.FastResumeError, match="missing profile facts"):
        fast_resume.import_library(
            source,
            tmp_path / "applications",
            baseline,
            profile_path,
            tmp_path / "claims.json",
            tmp_path / "report.json",
        )


def test_claim_import_requires_approved_reusable_hash_valid_source(tmp_path: Path) -> None:
    source_root = tmp_path / "latest"
    source_root.mkdir()
    source_pdf = source_root / "approved.pdf"
    source_pdf.write_bytes(b"approved-source")
    applications = tmp_path / "applications"
    application = applications / "示例公司_产品经理"
    run_dir = application / "resume-content" / "runs" / "run-approved"
    run_dir.mkdir(parents=True)
    fast_resume.write_json(
        application / "resume-content" / "current.json",
        {"status": "approved", "approved_run_id": "run-approved"},
    )
    fast_resume.write_json(run_dir / "hr-review.json", {"passed": True})
    fast_resume.write_json(
        run_dir / "jd-analysis.json", {"role_family": "ai_product_manager"}
    )
    fast_resume.write_json(
        run_dir / "fusion.json",
        {
            "sections": [
                {
                    "name": "实践经历",
                    "entries": [
                        {
                            "experience_id": "EXP-PROJECT-001",
                            "heading": "示例项目",
                            "bullets": [
                                {
                                    "text": "围绕用户反馈拆解需求并形成原型，完成多轮验证后交付可运行版本。",
                                    "fact_ids": ["FACT-PROJECT-001-01"],
                                    "primary_value": "需求与验证",
                                },
                                {
                                    "text": "内容环比增长 300%。",
                                    "fact_ids": ["FACT-PROJECT-001-01"],
                                    "primary_value": "错误口径",
                                },
                            ],
                        }
                    ],
                }
            ]
        },
    )
    baseline = {
        "items": [
            {
                "status": "reusable",
                "application_dirs": [str(application)],
                "source_files": [
                    {"path": str(source_pdf), "sha256": fast_resume.sha256_file(source_pdf)}
                ],
            }
        ]
    }
    library = fast_resume.build_claim_library(
        applications, baseline, source_root, _profile("FACT-PROJECT-001-01")
    )
    assert len(library["claims"]) == 1
    assert library["claims"][0]["fact_ids"] == ["FACT-PROJECT-001-01"]
    assert "300%" not in library["claims"][0]["text"]


def test_non_game_assembly_rejects_game_experience() -> None:
    jd = {
        "company": "示例公司",
        "target_role": "产品经理",
        "role_family": "ai_product_manager",
        "context": "non_game",
        "requirements": [],
    }
    selection = {"selected_experience_ids": ["EXP-PROJECT-010"]}
    with pytest.raises(fast_resume.FastResumeError, match="cannot select game"):
        fast_resume.assemble_fast_content(
            jd,
            selection,
            {"claims_sha256": "a" * 64, "claims": []},
            _profile("FACT-PROJECT-010-01"),
            _contact(),
        )


def test_supported_jd_ability_becomes_writer_gap_and_unsupported_stays_fact_gap() -> None:
    fact_id = "FACT-PROJECT-001-01"
    claims = [_claim("EXP-PROJECT-001", [fact_id])]
    library = {"claims_sha256": fast_resume.canonical_json_sha256(claims), "claims": claims}
    jd = {
        "company": "示例公司",
        "target_role": "AI 产品经理",
        "role_family": "ai_product_manager",
        "context": "non_game",
        "requirements": [
            {"requirement_id": "REQ-1", "text": "项目推进", "fact_ids": [fact_id]},
            {"requirement_id": "REQ-2", "text": "模型训练", "fact_ids": []},
        ],
    }
    content = fast_resume.assemble_fast_content(
        jd,
        {"selected_experience_ids": ["EXP-PROJECT-001"]},
        library,
        _profile(fact_id),
        _contact(),
    )
    assert content["covered_requirement_ids"] == ["REQ-1"]
    assert [item["requirement_id"] for item in content["supported_coverage_gaps"]] == ["REQ-1"]
    assert [item["requirement_id"] for item in content["fact_gaps"]] == ["REQ-2"]


def test_fast_writer_closes_only_fact_supported_gap_once() -> None:
    fact_id = "FACT-PROJECT-001-01"
    content = fast_resume.assemble_fast_content(
        {
            "company": "示例公司",
            "target_role": "AI 产品经理",
            "role_family": "ai_product_manager",
            "context": "non_game",
            "requirements": [
                {"requirement_id": "REQ-1", "text": "项目推进", "fact_ids": [fact_id]}
            ],
        },
        {"selected_experience_ids": ["EXP-PROJECT-001"]},
        {
            "claims_sha256": "a" * 64,
            "claims": [_claim("EXP-PROJECT-001", [fact_id])],
        },
        _profile(fact_id),
        _contact(),
    )
    result = fast_resume.apply_writer_additions(
        content,
        {
            "writer_additions": [
                {
                    "text": "项目推进：可拆解里程碑并协调跨团队完成交付。",
                    "experience_id": "EXP-SKILL-001",
                    "fact_ids": [fact_id],
                    "requirement_ids": ["REQ-1"],
                    "capability_tags": ["项目推进"],
                    "heading": "产品与项目能力",
                }
            ]
        },
        _profile(fact_id),
    )
    assert result["supported_coverage_gaps"] == []
    assert "REQ-1" in result["covered_requirement_ids"]
    assert any(section["name"] == "自我能力" for section in result["sections"])
    with pytest.raises(fast_resume.FastResumeError, match="only once"):
        fast_resume.apply_writer_additions(result, {"writer_additions": [{}]}, _profile(fact_id))


def test_fast_writer_rejects_unconfirmed_fact() -> None:
    content = {
        "content_pipeline": "fast-assemble",
        "context": "non_game",
        "contact": _contact(),
        "sections": [],
        "covered_requirement_ids": [],
        "supported_coverage_gaps": [
            {"requirement_id": "REQ-1", "text": "数据分析", "fact_ids": ["FACT-OK"]}
        ],
        "writer_additions": [],
    }
    with pytest.raises(fast_resume.FastResumeError, match="unconfirmed"):
        fast_resume.apply_writer_additions(
            content,
            {
                "writer_additions": [
                    {
                        "text": "擅长数据分析。",
                        "fact_ids": ["FACT-NOT-CONFIRMED"],
                        "requirement_ids": ["REQ-1"],
                        "capability_tags": ["数据分析"],
                    }
                ]
            },
            _profile("FACT-OK"),
        )


def test_writer_packet_exposes_only_gap_bound_fact_text() -> None:
    content = {
        "content_pipeline": "fast-assemble",
        "company": "示例公司",
        "target_role": "AI 产品经理",
        "role_family": "ai_product_manager",
        "context": "non_game",
        "supported_coverage_gaps": [
            {
                "requirement_id": "REQ-1",
                "text": "项目推进",
                "fact_ids": ["FACT-PROJECT-001-01"],
            }
        ],
    }
    packet = fast_resume.build_fast_writer_packet(
        content, _profile("FACT-PROJECT-001-01", "FACT-UNRELATED-001")
    )
    assert packet["rules"]["max_writer_calls"] == 1
    assert packet["rules"]["non_game_game_content_forbidden"] is True
    exposed = packet["supported_coverage_gaps"][0]["allowed_facts"]
    assert [item["fact_id"] for item in exposed] == ["FACT-PROJECT-001-01"]


@pytest.mark.parametrize("failed_gate", fast_resume.HR_GATES)
def test_four_hr_gates_each_block_pass(failed_gate: str) -> None:
    checks = {
        gate: {"passed": gate != failed_gate, "findings": ["问题"] if gate == failed_gate else []}
        for gate in fast_resume.HR_GATES
    }
    review = {
        "schema_version": "1.0",
        "generation_round": 1,
        "decision": "repair",
        "checks": checks,
        "exact_repairs": [
            {
                "gate": failed_gate,
                "location": "自我能力",
                "problem": "问题",
                "replacement_or_action": "删除或替换",
            }
        ],
        "requires_manual_review": False,
    }
    assert fast_resume.validate_hr_review(review)["status"] == "repair_once"


def test_second_failed_hr_review_requires_manual_handling() -> None:
    review = {
        "schema_version": "1.0",
        "generation_round": 2,
        "decision": "repair",
        "checks": {
            gate: {"passed": gate != "relevance", "findings": ["冗余"] if gate == "relevance" else []}
            for gate in fast_resume.HR_GATES
        },
        "exact_repairs": [
            {"gate": "relevance", "location": "实践经历", "problem": "冗余", "replacement_or_action": "人工处理"}
        ],
        "requires_manual_review": True,
    }
    assert fast_resume.validate_hr_review(review)["status"] == "manual_required"


def test_route_uses_new_five_strategy_values(monkeypatch: pytest.MonkeyPatch) -> None:
    claims = {"claims": [_claim("EXP-PROJECT-001", ["FACT-PROJECT-001-01"])]}
    assert fast_resume.route_job({"excluded": True}, claims)["resume_strategy"] == "排除"
    monkeypatch.setattr(fast_resume, "_pdf_matches_existing", lambda *_: (True, "f" * 64))
    direct = fast_resume.route_job(
        {"target_role": "产品经理", "existing_resume_path": "existing.pdf"}, claims
    )
    assert direct["resume_strategy"] == "直接复用"
    needs_fact = fast_resume.route_job(
        {
            "target_role": "产品经理",
            "jd_complete": True,
            "requirements": [{"required": True, "fact_ids": []}],
        },
        claims,
    )
    assert needs_fact["resume_strategy"] == "待补事实"
    fast = fast_resume.route_job(
        {
            "target_role": "产品经理",
            "jd_complete": True,
            "requirements": [{"required": True, "fact_ids": ["FACT-PROJECT-001-01"]}],
            "selected_experience_ids": ["EXP-PROJECT-001"],
            "context": "non_game",
            "role_family": "ai_product_manager",
        },
        claims,
    )
    assert fast == {
        "resume_strategy": "快速生成",
        "content_pipeline": "fast-assemble",
        "reason": "complete JD and approved claims cover the selected experiences",
    }
    deferred = fast_resume.route_job(
        {
            "target_role": "产品经理",
            "jd_complete": True,
            "requirements": [],
            "selected_experience_ids": ["EXP-PROJECT-999"],
            "context": "non_game",
            "role_family": "ai_product_manager",
        },
        claims,
    )
    assert deferred["resume_strategy"] == "暂缓完整重写"


def test_job_batch_priority_is_direct_fast_fact_deferred_excluded() -> None:
    positions = [
        {"company": "E", "concrete_job": "排除", "resume_strategy": "排除"},
        {"company": "D", "concrete_job": "重写", "resume_strategy": "暂缓完整重写"},
        {"company": "B", "concrete_job": "快速", "resume_strategy": "快速生成"},
        {"company": "C", "concrete_job": "补事实", "resume_strategy": "待补事实"},
        {"company": "A", "concrete_job": "复用", "resume_strategy": "直接复用"},
    ]
    result = fast_resume.prioritize_job_batch(
        {"schema_version": "1.0", "positions": positions}
    )
    assert [item["resume_strategy"] for item in result["positions"]] == [
        "直接复用",
        "快速生成",
        "待补事实",
        "暂缓完整重写",
        "排除",
    ]


def test_rendercv_document_is_a4_yahei_and_has_no_file_fields() -> None:
    content = {
        "target_role": "产品经理",
        "contact": _contact(),
        "sections": [
            {
                "name": "实践经历",
                "entries": [
                    {
                        "heading": "示例项目｜负责人｜2026/01–2026/06",
                        "bullets": [{"text": "完成需求拆解与验证。"}],
                    }
                ],
            }
        ],
    }
    document = fast_resume.build_rendercv_document(content)
    assert document["design"]["page"]["size"] == "a4"
    assert document["design"]["typography"]["font_family"] == "Microsoft YaHei"
    assert "photo" not in json.dumps(document, ensure_ascii=False).lower()


def test_new_schemas_are_valid_json_and_workbook_uses_new_routes() -> None:
    schemas = ROOT / ".agents" / "skills" / "china-job-search" / "schemas"
    for name in (
        "resume-claims.schema.json",
        "fast-resume-content.schema.json",
        "fast-hr-review.schema.json",
        "fast-writer-packet.schema.json",
        "concrete-job-batch.schema.json",
    ):
        json.loads((schemas / name).read_text(encoding="utf-8"))
    updater = (ROOT / "scripts" / "update_job_resume_workbook.mjs").read_text(encoding="utf-8")
    for value in ("直接复用", "快速生成", "待补事实", "暂缓完整重写", "排除"):
        assert value in updater or value in (schemas / "concrete-job-batch.schema.json").read_text(encoding="utf-8")
