"""
Vendoring — copy (or upgrade) the framework into a host project.

    fresh    <project>/.omni-team/ does not exist → copy the runtime set + project/ template
    upgrade  it exists → replace framework files, delete framework files that are no longer
             shipped, and NEVER touch project/ or runs/ (they belong to the host)
    same     the source already is <project>/.omni-team/ → nothing to copy

Flavours
    slim (default)  only what agents and the orchestrator use at run time (RUNTIME_SET);
                    the installer, tests, examples and maintainer docs stay in the omni-team
                    checkout. skills/ is added only for tools without native skills.
    full            the whole framework folder (e.g. to develop omni-team inside a project).

Every copy records `.omni-team/.vendor.json` (version, source, flavour, files) so the next
upgrade removes exactly the files it shipped. Standard library only (Python 3.8+).
"""

from __future__ import annotations

import datetime as dt
import filecmp
import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

FOLDER = ".omni-team"
MANIFEST = ".vendor.json"
HOST_OWNED = ("project", "runs")              # preserved on upgrade
EXCLUDED_NAMES = {"__pycache__", ".DS_Store", ".pytest_cache"}
EXCLUDED_SUFFIXES = (".pyc", ".pyo")
MARKER_FILE = Path("team") / "_protocol.md"   # proves a folder is an omni-team copy

# What a project needs at run time. Entries ending in "/" are folders. Keep in sync with
# docs/repository-layout.md; tests verify every entry exists and every link inside resolves.
RUNTIME_SET: Tuple[str, ...] = (
    ".gitignore", "AGENTS.md", "CLAUDE.md", "GEMINI.md", "VERSION", "requirements.txt",
    "defaults.yaml", "orchestrator.py",
    "lib/__init__.py", "lib/checks.py", "lib/diffscope.py", "lib/pipeline.py", "lib/profile.py",
    "lib/roles.py", "lib/routing.py", "lib/runner.py", "lib/state.py",
    "team/",
    "docs/workflow.md", "docs/roles.md", "docs/profile.md", "docs/routing.md", "docs/adapters.md",
)
SKILLS_ENTRY = "skills/"
PROJECT_TEMPLATE = "project/"


class VendorError(Exception):
    pass


@dataclass
class VendorPlan:
    source: Path
    target: Path
    mode: str                                            # fresh | upgrade | same
    flavor: str = "slim"                                 # slim | full
    from_version: str = ""
    to_version: str = ""
    files: List[Path] = field(default_factory=list)      # framework files the target will hold
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


def read_manifest(target: Path) -> Optional[dict]:
    path = target / MANIFEST
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def framework_files(root: Path, skip_top: Sequence[str] = ()) -> List[Path]:
    """Relative paths of files under root, minus caches, the manifest and skipped top folders."""
    files = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if rel.parts[0] in skip_top or str(rel) == MANIFEST or any(p in EXCLUDED_NAMES for p in rel.parts):
            continue
        if path.is_file() and not path.name.endswith(EXCLUDED_SUFFIXES):
            files.append(rel)
    return files


def expand(source: Path, entries: Sequence[str]) -> List[Path]:
    """Resolve RUNTIME_SET-style entries to files; a missing entry is a packaging bug."""
    files: List[Path] = []
    for entry in entries:
        path = source / entry
        if entry.endswith("/"):
            if not path.is_dir():
                raise VendorError(f"runtime set lists missing folder: {entry}")
            files += [Path(entry.rstrip("/")) / rel for rel in framework_files(path)]
        elif path.is_file():
            files.append(Path(entry))
        else:
            raise VendorError(f"runtime set lists missing file: {entry}")
    return sorted(dict.fromkeys(files))


def _shipped_files(source: Path, full: bool, with_skills: bool) -> List[Path]:
    if full:
        return framework_files(source, HOST_OWNED)
    entries = list(RUNTIME_SET) + ([SKILLS_ENTRY] if with_skills else [])
    return expand(source, entries)


def _check_target(source: Path, project_dir: Path, result: VendorPlan, force: bool) -> None:
    if source == project_dir or source in project_dir.parents:
        raise VendorError(f"refusing to vendor into a folder inside the framework source: {project_dir}")
    if not result.target.exists():
        return
    if not (result.target / MARKER_FILE).exists():
        raise VendorError(f"{result.target} exists but is not an omni-team folder (no {MARKER_FILE}); move it away first")
    if version_key(result.from_version) > version_key(result.to_version) and not force:
        raise VendorError(
            f"{result.target} has v{result.from_version}, newer than this source (v{result.to_version}); "
            "pass --force to downgrade"
        )


def plan(source: Path, project_dir: Path, force: bool = False, full: bool = False,
         with_skills: bool = False) -> VendorPlan:
    source, project_dir = source.resolve(), project_dir.resolve()
    if not project_dir.is_dir():
        raise VendorError(f"project directory does not exist: {project_dir}")
    target = project_dir / FOLDER
    result = VendorPlan(source, target, "same", "full" if full else "slim", read_version(target), read_version(source))
    if target.exists() and target.resolve() == source:
        return result
    _check_target(source, project_dir, result, force)
    fresh = not target.exists()
    result.mode = "fresh" if fresh else "upgrade"
    if fresh:
        result.from_version = ""

    result.files = _shipped_files(source, full, with_skills)
    copies = list(result.files)
    if fresh:
        copies += [Path("project") / rel for rel in framework_files(source / "project")]
    for rel in copies:
        src, dst = source / rel, target / rel
        if not dst.exists():
            result.added.append((src, dst))
        elif not filecmp.cmp(src, dst, shallow=False):
            result.updated.append((src, dst))

    if not fresh:
        manifest = read_manifest(target)
        previous = [Path(p) for p in manifest["files"]] if manifest else framework_files(target, HOST_OWNED)
        keep = set(result.files)
        result.removed = [target / rel for rel in previous
                          if rel not in keep and rel.parts[0] not in HOST_OWNED and (target / rel).is_file()]
    return result


def apply(vplan: VendorPlan) -> None:
    if vplan.mode == "same":
        return
    for src, dst in vplan.added + vplan.updated:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    for path in vplan.removed:
        path.unlink()
    for path in sorted({p.parent for p in vplan.removed}, key=lambda p: len(p.parts), reverse=True):
        while path != vplan.target and path.exists() and not any(path.iterdir()):
            path.rmdir()
            path = path.parent
    manifest = {
        "version": vplan.to_version,
        "flavor": vplan.flavor,
        "source": str(vplan.source),
        "installed_at": dt.datetime.now().isoformat(timespec="seconds"),
        "files": [str(p) for p in vplan.files],
    }
    (vplan.target / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
