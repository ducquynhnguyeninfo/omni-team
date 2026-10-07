"""
Vendoring — copy (or upgrade) the framework folder into a host project.

    fresh    <project>/.omni-team/ does not exist → copy everything except runs/
    upgrade  it exists → replace every framework file, delete framework files that
             no longer exist, and NEVER touch project/ or runs/ (they belong to the host)
    same     the source already is <project>/.omni-team/ → nothing to copy

Standard library only (install.py must run on a bare Python 3.8+).
"""

from __future__ import annotations

import filecmp
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

FOLDER = ".omni-team"
HOST_OWNED = ("project", "runs")              # preserved on upgrade
EXCLUDED_NAMES = {"__pycache__", ".DS_Store", ".pytest_cache"}
EXCLUDED_SUFFIXES = (".pyc", ".pyo")
MARKER_FILE = Path("team") / "_protocol.md"   # proves a folder is an omni-team copy


class VendorError(Exception):
    pass


@dataclass
class VendorPlan:
    source: Path
    target: Path
    mode: str                                            # fresh | upgrade | same
    from_version: str = ""
    to_version: str = ""
    added: List[Tuple[Path, Path]] = field(default_factory=list)
    updated: List[Tuple[Path, Path]] = field(default_factory=list)
    removed: List[Path] = field(default_factory=list)

    @property
    def changes(self) -> int:
        return len(self.added) + len(self.updated) + len(self.removed)


def read_version(folder: Path) -> str:
    path = folder / "VERSION"
    return path.read_text(encoding="utf-8").strip() if path.exists() else "0.0.0"


def version_key(version: str) -> Tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", version)[:3]) or (0,)


def framework_files(root: Path, skip_top: Tuple[str, ...]) -> List[Path]:
    """Relative paths of framework files under root, minus caches and host-owned folders."""
    files = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if rel.parts[0] in skip_top or any(part in EXCLUDED_NAMES for part in rel.parts):
            continue
        if path.is_file() and not path.name.endswith(EXCLUDED_SUFFIXES):
            files.append(rel)
    return files


def plan(source: Path, project_dir: Path, force: bool = False) -> VendorPlan:
    source, project_dir = source.resolve(), project_dir.resolve()
    if not project_dir.is_dir():
        raise VendorError(f"project directory does not exist: {project_dir}")
    target = project_dir / FOLDER
    result = VendorPlan(source, target, "same", read_version(target), read_version(source))
    if target.exists() and target.resolve() == source:
        return result
    if source == project_dir or source in project_dir.parents:
        raise VendorError(f"refusing to vendor into a folder inside the framework source: {project_dir}")

    if target.exists():
        if not (target / MARKER_FILE).exists():
            raise VendorError(f"{target} exists but is not an omni-team folder (no {MARKER_FILE}); move it away first")
        result.mode = "upgrade"
        if version_key(result.from_version) > version_key(result.to_version) and not force:
            raise VendorError(
                f"{target} has v{result.from_version}, newer than this source (v{result.to_version}); "
                "pass --force to downgrade"
            )
        skip = HOST_OWNED
    else:
        result.mode, result.from_version = "fresh", ""
        skip = ("runs",)

    source_files = framework_files(source, skip)
    for rel in source_files:
        src, dst = source / rel, target / rel
        if not dst.exists():
            result.added.append((src, dst))
        elif not filecmp.cmp(src, dst, shallow=False):
            result.updated.append((src, dst))
    if result.mode == "upgrade":
        keep = set(source_files)
        result.removed = [target / rel for rel in framework_files(target, HOST_OWNED) if rel not in keep]
    return result


def apply(vplan: VendorPlan) -> None:
    for src, dst in vplan.added + vplan.updated:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    for path in vplan.removed:
        path.unlink()
    for path in sorted({p.parent for p in vplan.removed}, key=lambda p: len(p.parts), reverse=True):
        while path != vplan.target and path.exists() and not any(path.iterdir()):
            path.rmdir()
            path = path.parent
