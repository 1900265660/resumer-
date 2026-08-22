from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / ".agents" / "skills" / "custom-resume"


def _skill_frontmatter() -> dict[str, str]:
    content = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"\A---\n(?P<body>.*?)\n---\n", content, re.DOTALL)
    assert match is not None, "SKILL.md must start with YAML frontmatter"

    values: dict[str, str] = {}
    for line in match.group("body").splitlines():
        key, value = line.split(":", maxsplit=1)
        values[key.strip()] = value.strip()
    return values


def test_skill_name_matches_discovery_directory() -> None:
    metadata = _skill_frontmatter()
    assert metadata["name"] == SKILL_DIR.name == "custom-resume"
    assert metadata["description"]


def test_openai_metadata_keeps_implicit_invocation_and_explicit_example() -> None:
    metadata = (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")
    assert 'allow_implicit_invocation: true' in metadata
    assert "$custom-resume" in metadata


def test_all_local_skill_markdown_links_resolve() -> None:
    skill_file = SKILL_DIR / "SKILL.md"
    content = skill_file.read_text(encoding="utf-8")
    links = re.findall(r"\[[^]]+\]\(([^)]+\.md)\)", content)
    assert links, "SKILL.md must route to its progressive-disclosure references"

    missing = [link for link in links if not (SKILL_DIR / link).is_file()]
    assert missing == []
