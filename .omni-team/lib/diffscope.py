"""
Diff scope — turn the git working tree(s) into a routing Scope.

Reviews happen BEFORE commit, so the working tree (committed + staged + unstaged + untracked,
minus .gitignore'd files) is captured as a git *tree object* — written through a temporary
index, so the real index and working tree are never touched.

Workspaces: a component whose folder is its own git repository (a product repo cloned inside a
private workspace, a gitlink, a polyrepo checkout) is diffed inside that repository and its paths
are prefixed with the component path, so routing, Gate 0 and component detection see one
workspace-relative scope. The workspace repo itself is diffed with those folders excluded.

A snapshot is one string: a plain tree id for a single repo (backward compatible), or
"<repo>:<tree>|<repo>:<tree>…" with "." for the workspace repo.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .routing import Scope

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
DEFAULT_BASE_CANDIDATES = ("origin/HEAD", "origin/main", "origin/master", "main", "master")
WORKSPACE = "."


class GitError(Exception):
    pass


@dataclass
class RepoTarget:
    key: str                  # "." for the workspace repo, else the component path
    path: Path
    base_ref: str
    excludes: List[str]       # repo-relative exclude globs


@dataclass
class RepoDiff:
    key: str
    base_ref: str
    point: str
    tree: str
    changed: int


@dataclass
class DiffInfo:
    scope: Scope
    base_ref: str
    compared_to: str
    tree: str                                  # snapshot reviewed (see module docstring)
    notes: List[str] = field(default_factory=list)
    repos: List[RepoDiff] = field(default_factory=list)


def git(args: List[str], cwd: Path, check: bool = True, env: Optional[Dict[str, str]] = None) -> Tuple[int, str]:
    try:
        done = subprocess.run(
            ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False, env=env
        )
    except FileNotFoundError as exc:
        raise GitError("git is not installed or not on PATH") from exc
    if check and done.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed in {cwd}: {done.stderr.strip()}")
    return done.returncode, done.stdout


def _verify(ref: str, cwd: Path) -> bool:
    rc, _ = git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], cwd, check=False)
    return rc == 0


def is_repo(path: Path) -> bool:
    rc, out = git(["rev-parse", "--is-inside-work-tree"], path, check=False)
    return rc == 0 and out.strip() == "true"


def tree_exists(tree: str, cwd: Path) -> bool:
    rc, _ = git(["cat-file", "-e", f"{tree}^{{tree}}"], cwd, check=False)
    return bool(tree) and rc == 0


def resolve_base(ref: str, cwd: Path, candidates: Sequence[str] = DEFAULT_BASE_CANDIDATES) -> Optional[str]:
    options = tuple(candidates) if ref in ("", "auto") else (ref,)
    return next((c for c in options if _verify(c, cwd)), None)


def _pathspec(excludes: List[str]) -> List[str]:
    return ["--", "."] + [f":(exclude,glob){pattern}" for pattern in excludes]


def snapshot_tree(cwd: Path, excludes: List[str]) -> str:
    """Write the working tree (incl. untracked, minus ignored and excluded paths) as a tree object.

    Touches neither the real index nor the working tree. Excluded paths (run artifacts, the
    vendored framework, nested repos) keep their index version, so they never move the snapshot.
    """
    _, index_rel = git(["rev-parse", "--git-path", "index"], cwd)
    real_index = Path(index_rel.strip())
    real_index = real_index if real_index.is_absolute() else cwd / real_index
    with tempfile.TemporaryDirectory(prefix="omni-team-") as tmp:
        tmp_index = Path(tmp) / "index"
        if real_index.exists():
            # copy2 keeps the index's mtime: git's racy-clean check re-hashes files modified in the
            # same second as the last index write. A fresh mtime would make git trust stale stat
            # data and miss same-size edits (e.g. a one-character fix right after a commit).
            shutil.copy2(real_index, tmp_index)
        env = {**os.environ, "GIT_INDEX_FILE": str(tmp_index)}
        git(["add", "-A", *_pathspec(excludes)], cwd, env=env)
        _, out = git(["write-tree"], cwd, env=env)
    return out.strip()


def head_tree(cwd: Path) -> str:
    _, out = git(["rev-parse", "HEAD^{tree}"], cwd)
    return out.strip()


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


def _raw_diff(cwd: Path, old: str, new: str, excludes: List[str], prefix: str) -> Scope:
    common = ["diff", "--no-color", "--no-ext-diff", old, new]
    _, names = git([*common, "--name-only", *_pathspec(excludes)], cwd)
    _, patch = git([*common, *_pathspec(excludes)], cwd)
    paths = [f"{prefix}{p}" for p in names.splitlines() if p]
    added, removed = _split_diff(patch)
    return Scope(changed_paths=paths, added_lines=added, removed_lines=removed)


def diff_scope(cwd: Path, old: str, new: str, excludes: List[str], comps: List[Dict[str, Any]]) -> Scope:
    scope = _raw_diff(cwd, old, new, excludes, "")
    scope.components = touched_components(scope.changed_paths, comps)
    return scope


# ---------------------------------------------------------------------------
# Workspace targets
# ---------------------------------------------------------------------------

def _nested_repo_components(root: Path, comps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    nested = []
    for comp in comps:
        rel = str(comp["path"]).strip().strip("/")
        explicit = comp.get("repo")
        if rel in ("", ".") or explicit is False:
            continue
        if explicit is True or (root / rel / ".git").exists():
            nested.append(comp)
    return nested


def _relative_excludes(excludes: List[str], prefix: str) -> List[str]:
    """Workspace exclude globs as seen from inside a nested repo at `prefix`."""
    out = []
    for pattern in excludes:
        if pattern.startswith("**/"):
            out.append(pattern)
        elif pattern.startswith(prefix + "/"):
            out.append(pattern[len(prefix) + 1:])
    return out


def targets(root: Path, base_ref: str, excludes: List[str], comps: List[Dict[str, Any]]) -> List[RepoTarget]:
    nested = _nested_repo_components(root, comps)
    found: List[RepoTarget] = []
    if is_repo(root):
        # Nested repos the workspace already ignores need nothing; a gitlink (or an unignored
        # clone) is excluded explicitly. Excluding an ignored path makes `git add` fail.
        hide = []
        for comp in nested:
            rel = str(comp["path"]).strip().strip("/")
            if git(["check-ignore", "-q", rel], root, check=False)[0] != 0:
                hide.append(rel)  # to the workspace a nested repo is one entry (a gitlink), never its files
        found.append(RepoTarget(WORKSPACE, root, base_ref, list(excludes) + hide))
    for comp in nested:
        rel = str(comp["path"]).strip().strip("/")
        path = root / rel
        if not is_repo(path):
            raise GitError(f"component '{comp['name']}' is marked as a repository but {path} is not a git work tree")
        found.append(RepoTarget(rel, path, str(comp.get("base_ref") or base_ref), _relative_excludes(excludes, rel)))
    if not found:
        raise GitError(f"{root} is not a git repository and no component is a nested repository")
    return found


def encode_snapshot(trees: Dict[str, str]) -> str:
    if list(trees) == [WORKSPACE]:
        return trees[WORKSPACE]
    return "|".join(f"{key}:{tree}" for key, tree in sorted(trees.items()))


def decode_snapshot(snapshot: str) -> Dict[str, str]:
    if not snapshot:
        return {}
    if "|" not in snapshot and ":" not in snapshot:
        return {WORKSPACE: snapshot}
    return {key: tree for key, _, tree in (part.rpartition(":") for part in snapshot.split("|"))}


# ---------------------------------------------------------------------------
# Scope over all targets
# ---------------------------------------------------------------------------

def _comparison_point(target: RepoTarget, candidates: Sequence[str], notes: List[str]) -> Tuple[str, str]:
    label = "workspace" if target.key == WORKSPACE else target.key
    if not _verify("HEAD", target.path):
        notes.append(f"{label}: no commits yet — comparing against the empty tree")
        return "(none)", EMPTY_TREE
    base = resolve_base(target.base_ref, target.path, candidates)
    if base is None:
        notes.append(f"{label}: base ref '{target.base_ref}' not found — reviewing uncommitted changes vs HEAD only")
        return "HEAD", "HEAD"
    rc, out = git(["merge-base", base, "HEAD"], target.path, check=False)
    return base, (out.strip() if rc == 0 and out.strip() else base)


def _merge(scopes: List[Scope], comps: List[Dict[str, Any]]) -> Scope:
    merged = Scope()
    for s in scopes:
        merged.changed_paths += s.changed_paths
        merged.added_lines += s.added_lines
        merged.removed_lines += s.removed_lines
    merged.components = touched_components(merged.changed_paths, comps)
    return merged


def compute(
    project_root: Path,
    base_ref: str,
    include_uncommitted: bool,
    excludes: List[str],
    comps: List[Dict[str, Any]],
    candidates: Sequence[str] = DEFAULT_BASE_CANDIDATES,
) -> DiffInfo:
    notes: List[str] = []
    scopes, trees, repos = [], {}, []
    for target in targets(project_root, base_ref, excludes, comps):
        base_used, point = _comparison_point(target, candidates, notes)
        if include_uncommitted or point == EMPTY_TREE:
            tree = snapshot_tree(target.path, target.excludes)
        else:
            tree = head_tree(target.path)
        prefix = "" if target.key == WORKSPACE else f"{target.key}/"
        scope = _raw_diff(target.path, point, tree, target.excludes, prefix)
        scopes.append(scope)
        trees[target.key] = tree
        repos.append(RepoDiff(target.key, base_used, point, tree, len(scope.changed_paths)))
    merged = _merge(scopes, comps)
    mode = "working tree" if include_uncommitted else "HEAD"
    compared = "; ".join(
        f"{'workspace' if r.key == WORKSPACE else r.key}: {r.point[:12]} → {mode}" for r in repos
    ) + f" (snapshot {encode_snapshot(trees)[:24]})"
    base_label = ", ".join(f"{'workspace' if r.key == WORKSPACE else r.key}={r.base_ref}" for r in repos)
    if len(repos) == 1:
        base_label = repos[0].base_ref
    return DiffInfo(scope=merged, base_ref=base_label, compared_to=compared, tree=encode_snapshot(trees),
                    notes=notes, repos=repos)


def delta(project_root: Path, old: str, new: str, excludes: List[str],
          comps: List[Dict[str, Any]]) -> Optional[Scope]:
    """What changed between two snapshots; None when the old one is unknown (pruned, repo added)."""
    old_trees, new_trees = decode_snapshot(old), decode_snapshot(new)
    if set(old_trees) != set(new_trees):
        return None
    by_key = {t.key: t for t in targets(project_root, "auto", excludes, comps)}
    scopes = []
    for key, new_tree in new_trees.items():
        if old_trees[key] == new_tree:
            continue
        target = by_key.get(key)
        if target is None or not tree_exists(old_trees[key], target.path):
            return None
        prefix = "" if key == WORKSPACE else f"{key}/"
        scopes.append(_raw_diff(target.path, old_trees[key], new_tree, target.excludes, prefix))
    return _merge(scopes, comps)
