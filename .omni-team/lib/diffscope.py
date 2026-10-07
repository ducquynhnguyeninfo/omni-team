"""
Diff scope — turn the git working tree into a routing Scope.

Reviews happen BEFORE commit, so by default the scope is the working tree
(committed + staged + unstaged + untracked) compared with the merge-base of
the base ref.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .routing import Scope, glob_match

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
AUTO_BASE_CANDIDATES = ("origin/HEAD", "origin/main", "origin/master", "main", "master")
MAX_UNTRACKED_BYTES = 1_000_000


class GitError(Exception):
    pass


@dataclass
class DiffInfo:
    scope: Scope
    base_ref: str
    compared_to: str
    notes: List[str] = field(default_factory=list)


def git(args: List[str], cwd: Path, check: bool = True) -> Tuple[int, str]:
    try:
        done = subprocess.run(
            ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False
        )
    except FileNotFoundError as exc:
        raise GitError("git is not installed or not on PATH") from exc
    if check and done.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {done.stderr.strip()}")
    return done.returncode, done.stdout


def _verify(ref: str, cwd: Path) -> bool:
    rc, _ = git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], cwd, check=False)
    return rc == 0


def resolve_base(ref: str, cwd: Path) -> Optional[str]:
    candidates = AUTO_BASE_CANDIDATES if ref in ("", "auto") else (ref,)
    return next((c for c in candidates if _verify(c, cwd)), None)


def _comparison_point(base_ref: str, cwd: Path, notes: List[str]) -> Tuple[str, str]:
    if not _verify("HEAD", cwd):
        notes.append("repository has no commits yet — comparing against the empty tree")
        return "(none)", EMPTY_TREE
    base = resolve_base(base_ref, cwd)
    if base is None:
        notes.append(f"base ref '{base_ref}' not found — reviewing uncommitted changes vs HEAD only")
        return "HEAD", "HEAD"
    rc, out = git(["merge-base", base, "HEAD"], cwd, check=False)
    return base, (out.strip() if rc == 0 and out.strip() else base)


def _pathspec(excludes: List[str]) -> List[str]:
    return ["--", "."] + [f":(exclude,glob){pattern}" for pattern in excludes]


def _untracked(cwd: Path, excludes: List[str]) -> Dict[str, List[str]]:
    _, out = git(["ls-files", "--others", "--exclude-standard"], cwd)
    files: Dict[str, List[str]] = {}
    for rel in out.splitlines():
        if any(glob_match(rel, g) for g in excludes):
            continue
        path = cwd / rel
        try:
            if path.stat().st_size > MAX_UNTRACKED_BYTES:
                files[rel] = []
                continue
            files[rel] = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            files[rel] = []  # binary or unreadable: counts as a changed path, no lines
    return files


def _split_diff(text: str) -> Tuple[List[str], List[str]]:
    added, removed = [], []
    for line in text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            removed.append(line[1:])
    return added, removed


def touched_components(paths: List[str], comps: List[Dict[str, Any]]) -> set:
    touched = set()
    for comp in comps:
        root = str(comp["path"]).strip().rstrip("/")
        if root in ("", ".") or any(p == root or p.startswith(root + "/") for p in paths):
            touched.add(str(comp["name"]))
            if comp.get("kind"):
                touched.add(str(comp["kind"]))
    return touched


def compute(
    project_root: Path,
    base_ref: str,
    include_uncommitted: bool,
    excludes: List[str],
    comps: List[Dict[str, Any]],
) -> DiffInfo:
    notes: List[str] = []
    base_used, point = _comparison_point(base_ref, project_root, notes)
    target = [point] if include_uncommitted else [point, "HEAD"]
    common = ["diff", "--no-color", "--no-ext-diff", *target]
    _, names = git([*common, "--name-only", *_pathspec(excludes)], project_root)
    _, patch = git([*common, *_pathspec(excludes)], project_root)

    paths = [p for p in names.splitlines() if p]
    added, removed = _split_diff(patch)
    if include_uncommitted:
        for rel, lines in _untracked(project_root, excludes).items():
            paths.append(rel)
            added.extend(lines)

    scope = Scope(
        changed_paths=paths,
        added_lines=added,
        removed_lines=removed,
        components=touched_components(paths, comps),
    )
    compared = f"{point[:12]} → {'working tree' if include_uncommitted else 'HEAD'}"
    return DiffInfo(scope=scope, base_ref=base_used, compared_to=compared, notes=notes)
