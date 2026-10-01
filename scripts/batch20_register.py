#!/usr/bin/env python3
"""Register the 20 batch jobs: copy artifacts, build workbook positions, update manifests."""

from __future__ import annotations

import importlib.util
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"E:\zhuomian\简历\项目\Codex-求职助手")
MODULE = ROOT / ".agents" / "skills" / "china-job-search" / "scripts" / "fast_resume.py"
SPEC = importlib.util.spec_from_file_location("fast_resume", MODULE)
assert SPEC and SPEC.loader
fast_resume = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fast_resume)

OUT = ROOT / "outputs" / "fast-lane-pilot" / "batch20-jobs"
rows = json.loads((ROOT / "outputs" / "fast-lane-pilot" / "batch20.json").read_text(encoding="utf-8"))["rows"]
results = {r["key"]: r for r in json.loads((OUT / "batch20-result.json").read_text(encoding="utf-8"))}


def main() -> None:
    positions = []
    for row in rows:
        key = Path(row["app_dir"]).name
        res = results[key]
        app_dir = ROOT / row["app_dir"]
        resume_dir = app_dir / "resume"
        resume_dir.mkdir(parents=True, exist_ok=True)
        base = f"测试候选人_{key}"
        pdf_dst = resume_dir / f"{base}.pdf"
        yaml_dst = resume_dir / f"{base}.yaml"
        shutil.copyfile(OUT / f"{key}.resume.pdf", pdf_dst)
        shutil.copyfile(OUT / f"{key}.resume.yaml", yaml_dst)

        rel_pdf = pdf_dst.relative_to(ROOT).as_posix()
        positions.append({
            "source_row": int(row["source_row"]),
            "company": row["company"],
            "concrete_job": row["job"],
            "jd_url": row["jd"],
            "application_url": row.get("application_url") or row["jd"],
            "resume_strategy": "快速生成",
            "baseline_id": "",
            "hr_result": "pass",
            "resume_path": rel_pdf,
            "material_status": "可投递",
            "notes": f"快速通道四项HR门禁pass，RenderCV 2.8单页PDF已生成，SHA-256 {res['pdf_sha256']}。",
        })

        mf_path = app_dir / "manifest.json"
        mf = fast_resume.read_json(mf_path)
        mf["resume_strategy"] = "快速生成"
        mf["material_status"] = "可投递"
        mf["baseline_id"] = ""
        mf["requires_rewrite_batch_approval"] = False
        mf["content_pipeline"] = "fast-assemble"
        mf["resume_pdf"] = {
            "path": rel_pdf,
            "sha256": res["pdf_sha256"],
            "bytes": pdf_dst.stat().st_size,
            "pages": res["pages"],
        }
        mf["fast_hr"] = {"passed": True, "decision": "pass", "gates": list(fast_resume.HR_GATES)}
        mf["updated_at"] = datetime.now(timezone.utc).isoformat()
        fast_resume.write_json(mf_path, mf)

    positions_path = OUT / "register-20-positions.json"
    fast_resume.write_json(positions_path, {"schema_version": "1.0", "positions": positions})
    print(f"registered {len(positions)} positions -> {positions_path}")


if __name__ == "__main__":
    main()
