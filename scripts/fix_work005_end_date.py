#!/usr/bin/env python3
"""Sync EXP-WORK-005 end date (至今 -> 2026/09) in resume-claims.json.

This is a fact-correction the user confirmed. It updates every approved claim
heading for EXP-WORK-005 and recomputes the library-level claims_sha256 so the
claim content and its hash stay consistent.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(r"E:\zhuomian\简历\项目\Codex-求职助手")
MODULE = ROOT / ".agents" / "skills" / "china-job-search" / "scripts" / "fast_resume.py"
SPEC = importlib.util.spec_from_file_location("fast_resume", MODULE)
assert SPEC and SPEC.loader
fast_resume = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fast_resume)

CLAIMS_PATH = ROOT / "profile" / "resume-claims.json"


def main() -> None:
    data = fast_resume.read_json(CLAIMS_PATH)
    changed = []
    for claim in data["claims"]:
        if claim.get("experience_id") != "EXP-WORK-005":
            continue
        old = claim.get("heading", "")
        new = old.replace("至今", "2026/09")
        if new != old:
            claim["heading"] = new
            changed.append({"claim_id": claim.get("claim_id"), "from": old, "to": new})
    old_hash = data.get("claims_sha256")
    new_hash = fast_resume.canonical_json_sha256(data["claims"])
    data["claims_sha256"] = new_hash
    fast_resume.write_json(CLAIMS_PATH, data)
    print(json.dumps(
        {"changed_count": len(changed), "changed": changed, "claims_sha256": {"from": old_hash, "to": new_hash}},
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
