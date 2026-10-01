#!/usr/bin/env python3
"""Match priority rewrite candidates to their application manifests and report
role-family / JD-completeness coverage for fast-lane eligibility."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(r"E:\zhuomian\简历\项目\Codex-求职助手")
APPS = ROOT / "applications"
PRIORITY = json.loads(
    (ROOT / "outputs" / "fast-lane-pilot" / "priority-rewrites.json").read_text(encoding="utf-8")
)


def norm_url(url: str) -> str:
    return url.strip().rstrip("/").lower()


def main() -> None:
    manifests = []
    for mf in APPS.rglob("manifest.json"):
        try:
            data = json.loads(mf.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        manifests.append((mf, data))

    matched = []
    for row in PRIORITY["rows"]:
        jd = norm_url(row["jd"])
        company = row["company"].strip()
        job = row["job"].strip()
        hit = None
        for mf, data in manifests:
            if jd and norm_url(str(data.get("job_url", ""))) == jd:
                hit = (mf, data)
                break
        if hit is None:
            for mf, data in manifests:
                if data.get("company") == company and data.get("role") == job:
                    hit = (mf, data)
                    break
        if hit is None:
            matched.append({**row, "role_family": None, "has_jd": False, "app_dir": None})
            continue
        mf, data = hit
        matched.append({
            **row,
            "role_family": data.get("role_family"),
            "role_track": data.get("role_track"),
            "has_jd": (mf.parent / "jd.md").exists(),
            "app_dir": str(mf.parent.relative_to(ROOT)),
        })

    from collections import Counter

    family = Counter((m["role_family"] or "(无)") for m in matched)
    print("role_family distribution:")
    for k, v in family.most_common():
        print(f"  {k}: {v}")

    eligible = [
        m
        for m in matched
        if m["role_family"] == "ai_product_manager" and m["has_jd"]
    ]
    eligible.sort(key=lambda m: (0 if m["category"].startswith("1-") else 1, m["company"], m["job"]))
    print(f"\neligible ai_product_manager with jd: {len(eligible)}")
    out = ROOT / "outputs" / "fast-lane-pilot" / "priority-ai-pm-eligible.json"
    out.write_text(json.dumps({"count": len(eligible), "rows": eligible}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out}")
    for m in eligible[:25]:
        print(f"  [{m['category']}] {m['company']}｜{m['job']} | {m['source_row']} | {m['app_dir']}")


if __name__ == "__main__":
    main()
