"""
Diff scope — turn the git working tree into a routing Scope.

Reviews happen BEFORE commit, so the working tree (committed + staged +
unstaged + untracked, minus .gitignore'd files) is captured as a git *tree
object* — a snapshot written through a temporary index, so the real index and
working tree are never touched. Snapshots make two things exact and cheap:

  - the review scope:   diff(merge-base of base ref, snapshot)
  - what changed since a gate approved:   diff(approved snapshot, current snapshot)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .routing import Scope

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
AUTO_BASE_CANDIDATES = ("origin/HEAD", "origin/main", "origin/master", "main", "master")


class GitError(Exception):
    pass


@dataclass
class DiffInfo:
    scope: Scope
    base_ref: str
    compared_to: str
    tree: str                                  # snapshot reviewed (working tree or HEAD tree)
    notes: List[str] = field(default_factory=list)


def git(args: List[str], cwd: Path, check: bool = True, env: Optional[Dict[str, str]] = None) -> Tuple[int, str]:
    try:
        done = subprocess.run(
            ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False, env=env
        )
    except FileNotFoundError as exc:
        raise GitError("git is not installed or not on PATH") from exc
    if check and done.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {done.stderr.strip()}")
    return done.returncode, done.stdout


def _verify(ref: str, cwd: Path) -> bool:
    rc, _ = git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], cwd, check=False)
    return rc == 0


def tree_exists(tree: str, cwd: Path) -> bool:
    rc, _ = git(["cat-file", "-e", f"{tree}^{{tree}}"], cwd, check=False)
    return bool(tree) and rc == 0


def resolve_base(ref: str, cwd: Path) -> Optional[str]:
    candidates = AUTO_BASE_CANDIDATES if ref in ("", "auto") else (ref,)
    return next((c for c in candidates if _verify(c, cwd)), None)


def snapshot_tree(cwd: Path, excludes: List[str]) -> str:
    """Write the working tree (incl. untracked, minus ignored and excluded paths) as a tree object.

    Touches neither the real index nor the working tree. Excluded paths (run artifacts, the
    vendored framework) keep their index version, so writing a gate report does not change
    the snapshot.
    """
    _, index_rel = git(["rev-parse", "--git-path", "index"], cwd)
    real_index = Path(index_rel.strip())
    real_index = real_index if real_index.is_absolute() else cwd / real_index
    with tempfile.TemporaryDirectory(prefix="omni-team-") as tmp:
        tmp_index = Path(tmp) / "index"
        if real_index.exists():
            shutil.copyfile(real_index, tmp_index)  # reuse the stat cache: only changed files get hashed
        env = {**os.environ, "GIT_INDEX_FILE": str(tmp_index)}
        git(["add", "-A", *_pathspec(excludes)], cwd, env=env)
        _, out = git(["write-tree"], cwd, env=env)
    return out.strip()


def head_tree(cwd: Path) -> str:
    _, out = git(["rev-parse", "HEAD^{tree}"], cwd)
    return out.strip()


def _pathspec(excludes: List[str]) -> List[str]:
    return ["--", "."] + [f":(exclude,glob){pattern}" for pattern in excludes]


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


def diff_scope(cwd: Path, old: str, new: str, excludes: List[str], comps: List[Dict[str, Any]]) -> Scope:
    common = ["diff", "--no-color", "--no-ext-diff", old, new]
    _, names = git([*common, "--name-only", *_pathspec(excludes)], cwd)
    _, patch = git([*common, *_pathspec(excludes)], cwd)
    paths = [p for p in names.splitlines() if p]
    added, removed = _split_diff(patch)
    return Scope(changed_paths=paths, added_lines=added, removed_lines=removed,
                 components=touched_components(paths, comps))


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


def compute(
    project_root: Path,
    base_ref: str,
    include_uncommitted: bool,
    excludes: List[str],
    comps: List[Dict[str, Any]],
) -> DiffInfo:
    notes: List[str] = []
    base_used, point = _comparison_point(base_ref, project_root, notes)
    if include_uncommitted or point == EMPTY_TREE:
        tree = snapshot_tree(project_root, excludes)
    else:
        tree = head_tree(project_root)
    scope = diff_scope(project_root, point, tree, excludes, comps)
    compared = f"{point[:12]} → {'working tree' if include_uncommitted else 'HEAD'} (snapshot {tree[:12]})"
    return DiffInfo(scope=scope, base_ref=base_used, compared_to=compared, tree=tree, notes=notes)


def delta(project_root: Path, old_tree: str, new_tree: str, excludes: List[str],
          comps: List[Dict[str, Any]]) -> Optional[Scope]:
    """What changed between two snapshots; None when the old snapshot is unknown (e.g. pruned)."""
    if not tree_exists(old_tree, project_root):
        return None
    return diff_scope(project_root, old_tree, new_tree, excludes, comps)
