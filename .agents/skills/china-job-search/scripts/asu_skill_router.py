"""Deterministic policy router for the installed ASu job-search skills.

This module deliberately does not invoke a skill or modify a job application.
It makes the capability boundary explicit so the calling Codex workflow can
route user requests without replacing the project's fact, approval, or browser
execution gates.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


GLOBAL_SKILLS = {
    "great-resume": "经历提升、岗位定位与 HR 开场白",
    "make-resume": "已批准内容的可编辑 HTML/PDF 制版",
    "job-match": "JD—证据—缺口矩阵",
    "job-apply": "字段映射与提交摘要规范",
    "interview": "面试预测、模拟与复练",
    "offer": "投递进度归档规范",
}
LEGACY_ASU_NAME = "asu"


@dataclass(frozen=True)
class SkillAvailability:
    name: str
    installed: bool
    skill_file: str
    purpose: str


@dataclass(frozen=True)
class RouteDecision:
    intent: str
    status: Literal["ready", "degraded"]
    capability_skill: str | None
    executor: str | None
    requires: tuple[str, ...]
    prohibitions: tuple[str, ...]
    detail: str


def default_skills_root() -> Path:
    """Return the user-overridable global Codex skills directory."""
    configured = os.environ.get("CODEX_JOB_SKILLS_ROOT")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".codex" / "skills"


def discover_skills(skills_root: Path | None = None) -> dict[str, SkillAvailability]:
    root = skills_root or default_skills_root()
    result = {
        name: SkillAvailability(
            name=name,
            installed=(root / name / "SKILL.md").is_file(),
            skill_file=str(root / name / "SKILL.md"),
            purpose=purpose,
        )
        for name, purpose in GLOBAL_SKILLS.items()
    }
    result[LEGACY_ASU_NAME] = SkillAvailability(
        name=LEGACY_ASU_NAME,
        installed=False,
        skill_file=str(root / LEGACY_ASU_NAME / "SKILL.md"),
        purpose="历史全局名称；不是运行时依赖",
    )
    return result


def dual_writer_ready(workspace_root: Path) -> bool:
    """The second Writer remains project-local and independent of global ASu."""
    return all(
        (workspace_root / relative).is_file()
        for relative in (
            ".codex/agents/custom-resume-writer.toml",
            ".codex/agents/custom-resume-asu-writer.toml",
            ".agents/prompts/custom-resume/writer.md",
            ".agents/prompts/custom-resume/asu-writer.md",
        )
    )


def route_intent(
    intent: str,
    availability: dict[str, SkillAvailability],
    *,
    content_pipeline: str | None = None,
) -> RouteDecision:
    """Return a non-mutating, fail-closed integration decision.

    `content_pipeline` is relevant only for resume rendering.  Fast assembly
    always stays on RenderCV; it must never be silently moved to make-resume.
    """
    normalized = intent.strip().lower().replace("-", "_")
    routes: dict[str, tuple[str, str | None, tuple[str, ...], tuple[str, ...], str]] = {
        "job_match": (
            "job-match",
            "china-job-search",
            ("official JD", "confirmed fact library"),
            ("do not create facts", "do not change application state"),
            "The result is a readable evidence matrix; the project persists JD analysis.",
        ),
        "great_resume": (
            "great-resume",
            None,
            ("confirmed facts with fact IDs", "explicit user request"),
            (
                "do not write atomic facts",
                "do not enter custom-resume dual-writer or fusion",
                "do not change application state",
            ),
            "Advisory positioning, bullets and HR opening copy only.",
        ),
        "job_apply": (
            "job-apply",
            "browser-application",
            ("validated approved manifest", "approved attachment and answers"),
            (
                "do not use Kimi WebBridge as an executor",
                "do not upload or submit outside browser-application",
            ),
            "job-apply supplies mapping and summary policy; browser-application performs all page actions.",
        ),
        "interview": (
            "interview",
            None,
            ("confirmed resume claims", "target JD or explicit no-JD mode"),
            ("do not invent interview answers", "do not update application state"),
            "Interview output is a de-identified practice record unless the user asks to save it.",
        ),
        "offer": (
            "offer",
            "harness-state",
            ("visible receipt, email, or user-provided evidence"),
            ("do not create a separate tracker", "do not infer submitted without receipt"),
            "The harness remains the sole state and evidence store.",
        ),
    }
    if normalized == "make_resume":
        if content_pipeline == "fast-assemble":
            return RouteDecision(
                intent=normalized,
                status="ready",
                capability_skill=None,
                executor="resume/RenderCV",
                requires=("passing fast-assemble HR gate", "passing deterministic PDF QA"),
                prohibitions=("do not call make-resume", "do not replace resume.yaml"),
                detail="Fast assembly stays on the fixed RenderCV route.",
            )
        routes[normalized] = (
            "make-resume",
            "resume",
            ("approved custom-resume content or an explicit user file-making request",),
            ("no placeholder photo", "do not use unapproved content for an application"),
            "make-resume is the capability layer; the local resume workflow owns artifact QA and records.",
        )
    if normalized not in routes:
        raise ValueError(f"unsupported integration intent: {intent}")
    skill, executor, requires, prohibitions, detail = routes[normalized]
    item = availability[skill]
    if not item.installed:
        return RouteDecision(
            intent=normalized,
            status="degraded",
            capability_skill=None,
            executor=None,
            requires=(),
            prohibitions=("do not silently substitute another global skill",),
            detail=f"Required global skill '{skill}' is unavailable: {item.skill_file}",
        )
    return RouteDecision(normalized, "ready", skill, executor, requires, prohibitions, detail)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Inspect and route ASu job-search capabilities")
    parser.add_argument("command", choices=("inspect", "route"))
    parser.add_argument("--skills-root", type=Path)
    parser.add_argument("--intent", choices=("job-match", "great-resume", "make-resume", "job-apply", "interview", "offer"))
    parser.add_argument("--content-pipeline")
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    availability = discover_skills(args.skills_root)
    payload: dict[str, object] = {
        "skills": {name: asdict(item) for name, item in availability.items()},
        "project_dual_writer_ready": dual_writer_ready(args.workspace_root),
    }
    if args.command == "route":
        if not args.intent:
            parser.error("route requires --intent")
        payload["route"] = asdict(
            route_intent(args.intent, availability, content_pipeline=args.content_pipeline)
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
