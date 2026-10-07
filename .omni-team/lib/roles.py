"""
Canonical role and skill sources.

Roles live in team/<name>.md and skills in skills/<name>/SKILL.md. Both start
with a tiny `key: value` frontmatter block. Parsing it here (stdlib only) keeps
install.py dependency-free so a freshly copied .omni-team/ works immediately.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent
TEAM_DIR = FRAMEWORK_ROOT / "team"
SKILLS_DIR = FRAMEWORK_ROOT / "skills"
PROTOCOL_FILE = TEAM_DIR / "_protocol.md"

VALID_TIERS = ("deep", "standard", "fast")
VALID_ACCESS = ("read-only", "run")
ROLE_KEYS = ("name", "description", "tier", "access")
SKILL_KEYS = ("name", "description")


class RoleError(Exception):
    pass


@dataclass
class Role:
    name: str
    description: str
    tier: str
    access: str
    body: str
    source: Path


@dataclass
class Skill:
    name: str
    description: str
    text: str
    source: Path


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def split_frontmatter(text: str, source: Path) -> Tuple[Dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise RoleError(f"{source}: must start with a '---' frontmatter block")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise RoleError(f"{source}: frontmatter block is not closed with '---'")
    meta: Dict[str, str] = {}
    for lineno, line in enumerate(lines[1:end], start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise RoleError(f"{source}:{lineno}: expected 'key: value', got {line!r}")
        meta[key.strip()] = _unquote(value.strip())
    body = "\n".join(lines[end + 1:]).strip() + "\n"
    return meta, body


def _require(meta: Dict[str, str], keys: Tuple[str, ...], source: Path) -> None:
    missing = [k for k in keys if not meta.get(k)]
    if missing:
        raise RoleError(f"{source}: missing frontmatter key(s): {', '.join(missing)}")


def load_role(path: Path) -> Role:
    meta, body = split_frontmatter(path.read_text(encoding="utf-8"), path)
    _require(meta, ROLE_KEYS, path)
    if meta["name"] != path.stem:
        raise RoleError(f"{path}: name '{meta['name']}' must match the file name '{path.stem}'")
    if meta["tier"] not in VALID_TIERS:
        raise RoleError(f"{path}: tier must be one of {VALID_TIERS}, got '{meta['tier']}'")
    if meta["access"] not in VALID_ACCESS:
        raise RoleError(f"{path}: access must be one of {VALID_ACCESS}, got '{meta['access']}'")
    return Role(meta["name"], meta["description"], meta["tier"], meta["access"], body, path)


def load_roles(team_dir: Path = TEAM_DIR) -> List[Role]:
    return [load_role(p) for p in sorted(team_dir.glob("*.md")) if not p.name.startswith("_")]


def role_by_name(name: str, team_dir: Path = TEAM_DIR) -> Role:
    path = team_dir / f"{name}.md"
    if not path.exists():
        known = ", ".join(r.name for r in load_roles(team_dir))
        raise RoleError(f"unknown role '{name}' (known: {known})")
    return load_role(path)


def load_protocol(path: Path = PROTOCOL_FILE) -> str:
    return path.read_text(encoding="utf-8").strip() + "\n"


def load_skills(skills_dir: Path = SKILLS_DIR) -> List[Skill]:
    skills = []
    for path in sorted(skills_dir.glob("*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        meta, _ = split_frontmatter(text, path)
        _require(meta, SKILL_KEYS, path)
        if meta["name"] != path.parent.name:
            raise RoleError(f"{path}: name '{meta['name']}' must match its folder name")
        skills.append(Skill(meta["name"], meta["description"], text, path))
    return skills


def compose_instructions(role: Role, protocol: str) -> str:
    """Role body first (who you are), shared protocol second (how every role behaves)."""
    return f"{role.body.rstrip()}\n\n---\n\n{protocol}"
