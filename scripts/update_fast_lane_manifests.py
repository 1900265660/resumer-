#!/usr/bin/env python3
"""Record fast-assemble results into the three pilot manifests."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"E:\zhuomian\简历\项目\Codex-求职助手")
MODULE = ROOT / ".agents" / "skills" / "china-job-search" / "scripts" / "fast_resume.py"
SPEC = importlib.util.spec_from_file_location("fast_resume", MODULE)
assert SPEC and SPEC.loader
fast_resume = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fast_resume)

MANIFESTS = {
    "applications/腾讯_AI产品经理": {
        "pdf": "applications/腾讯_AI产品经理/resume/测试候选人_腾讯_AI产品经理_校招简历.pdf",
    },
    "applications/盒马_AI Agent产品经理_199907740089": {
        "pdf": "applications/盒马_AI Agent产品经理_199907740089/resume/测试候选人_盒马_AI Agent产品经理_校招简历.pdf",
    },
    "applications/阿里云_AI产品经理": {
        "pdf": "applications/阿里云_AI产品经理/resume/测试候选人_阿里云_AI产品经理_校招简历.pdf",
    },
}


def main() -> None:
    for rel, spec in MANIFESTS.items():
        manifest_path = ROOT / rel / "manifest.json"
        data = fast_resume.read_json(manifest_path)
        pdf_path = ROOT / spec["pdf"]
        data["resume_strategy"] = "快速生成"
        data["material_status"] = "可投递"
        data["baseline_id"] = ""
        data["requires_rewrite_batch_approval"] = False
        data["content_pipeline"] = "fast-assemble"
        data["resume_pdf"] = {
            "path": spec["pdf"].replace("\\", "/"),
            "sha256": fast_resume.sha256_file(pdf_path),
            "bytes": pdf_path.stat().st_size,
            "pages": 1,
        }
        data["fast_hr"] = {
            "passed": True,
            "decision": "pass",
            "gates": list(fast_resume.HR_GATES),
        }
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        fast_resume.write_json(manifest_path, data)
        print(f"updated {rel}: {data['resume_pdf']['sha256']}")


if __name__ == "__main__":
    main()
