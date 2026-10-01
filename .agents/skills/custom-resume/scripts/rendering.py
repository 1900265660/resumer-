from __future__ import annotations

from models import FusionArtifact


def render_resume_markdown(fusion: FusionArtifact) -> str:
    lines: list[str] = []
    for section in fusion.sections:
        lines.extend([f"## {section.name.value}", ""])
        for entry in section.entries:
            lines.extend([f"### {entry.heading}", ""])
            visible_bullets = [
                bullet
                for bullet in entry.bullets
                if bullet.text.strip().rstrip("。")
                not in entry.heading.strip().rstrip("。")
            ]
            lines.extend(f"- {bullet.text}" for bullet in visible_bullets)
            if visible_bullets:
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"
