#!/usr/bin/env python3
"""
git-guard — Claude Code PreToolUse hook that blocks the git operations omni-team never
automates, whatever a project's `automation.pr_fix` level: force-push, deleting or mirroring
remote refs, pushing tags, pushing to (or a plain push from) a protected branch, merge, tag
creation, branch deletion, merging a pull request with `gh`, and `gh … --admin` (bypasses
branch protection). The way forward it allows: `git switch -c <work>` / `git checkout -b`,
`git push -u origin <work>`, `gh pr create`.

Deploy it with managed settings (see docs/automation.md#organisation-enforcement), or in a
project's `.claude/settings.json`. Exit 2 blocks the call and shows the reason; exit 0 lets
the normal permission rules decide. Best effort on the command text: `sh -c '…'` or an alias
can slip past, so keep server-side branch protection as the real boundary.

Protected branches: main and master always, plus OMNI_GUARD_PROTECTED (comma-separated
globs, default develop,release/*,hotfix/*). Standard library only.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
import subprocess
import sys
from typing import List, Optional

ALWAYS_PROTECTED = ["main", "master"]
DEFAULT_PROTECTED = "develop,release/*,hotfix/*"
SEPARATORS = re.compile(r"\|\||&&|[;|&\n]")
WRAPPERS = {"timeout", "time", "nice", "nohup", "stdbuf", "command", "builtin", "noglob", "xargs", "sudo"}
GIT_OPTS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
FORCE = re.compile(r"^(-f|--force|--force-with-lease(=.*)?|--force-if-includes|--mirror|--delete|-d|--tags|--prune)$")


def protected() -> List[str]:
    extra = [p.strip() for p in os.environ.get("OMNI_GUARD_PROTECTED", DEFAULT_PROTECTED).split(",") if p.strip()]
    return ALWAYS_PROTECTED + extra


def is_protected(branch: str) -> bool:
    branch = branch[len("refs/heads/"):] if branch.startswith("refs/heads/") else branch
    return any(fnmatch.fnmatchcase(branch, p) for p in protected())


def current_branch(cwd: str) -> str:
    done = subprocess.run(["git", "symbolic-ref", "--quiet", "--short", "HEAD"], cwd=cwd,
                          capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 else ""


def push_target(cwd: str) -> str:
    """Where a plain `git push` goes (`@{push}`, remote stripped); the current branch when unknown."""
    done = subprocess.run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{push}"], cwd=cwd,
                          capture_output=True, text=True)
    target = done.stdout.strip()
    return target.split("/", 1)[-1] if done.returncode == 0 and "/" in target else current_branch(cwd)


def words(segment: str) -> List[str]:
    try:
        parts = shlex.split(segment)
    except ValueError:
        parts = segment.split()
    while parts and (re.match(r"^\w+=", parts[0]) or parts[0] in WRAPPERS):
        parts.pop(0)
    return parts


def check_push(args: List[str], cwd: str) -> Optional[str]:
    flags = [a for a in args if a.startswith("-")]
    bad = next((f for f in flags if FORCE.match(f)), None)
    if bad:
        return f"`git push {bad}` rewrites or deletes remote refs"
    refspecs = [a for a in args if not a.startswith("-")][1:]   # first positional is the remote
    if any(r.startswith(("+", ":")) for r in refspecs):
        return "a `+` (force) or `:` (delete) refspec rewrites or deletes remote refs"
    targets = [r.rsplit(":", 1)[-1] for r in refspecs]
    targets = [current_branch(cwd) if t == "HEAD" else t for t in targets] or [push_target(cwd)]
    targets += [current_branch(cwd)] if not refspecs else []        # never from a protected branch either
    hit = next((t for t in targets if t and is_protected(t)), None)
    return (f"pushing to protected branch '{hit}' — `git switch -c <work-branch>`, `git push -u origin HEAD`, "
            f"then `gh pr create`") if hit else None


def check_git(parts: List[str], cwd: str) -> Optional[str]:
    i = 1
    while i < len(parts) and parts[i].startswith("-"):
        opt = parts[i]
        if opt in GIT_OPTS_WITH_VALUE and i + 1 < len(parts):
            if opt == "-C":
                cwd = os.path.join(cwd, parts[i + 1])
            i += 1
        i += 1
    if i >= len(parts):
        return None
    sub, args = parts[i], parts[i + 1:]
    if sub == "push":
        return check_push(args, cwd)
    if sub == "merge" and not {"--abort", "--continue", "--quit"} & set(args):
        return "`git merge` — merging is the human gate"
    listing = any(a in ("-l", "--list", "-v", "--verify", "--contains", "--points-at") or a.startswith("-n")
                  for a in args)
    if sub == "tag" and args and not listing:
        return "`git tag` creates or deletes a release marker — tagging stays human"
    if sub == "branch" and {"-d", "-D", "--delete"} & set(args):
        return "`git branch --delete` — deleting branches stays human"
    return None


def check(command: str, cwd: str) -> Optional[str]:
    for segment in SEPARATORS.split(command):
        parts = words(segment)
        if not parts:
            continue
        program = os.path.basename(parts[0])
        if program == "git":
            reason = check_git(parts, cwd)
        elif program == "gh" and parts[1:3] == ["pr", "merge"]:
            reason = "`gh pr merge` — merging is the human gate"
        elif program == "gh" and "--admin" in parts:
            reason = "`gh … --admin` bypasses branch protection"
        else:
            reason = None
        if reason:
            return reason
    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    if event.get("tool_name") != "Bash":
        return 0
    reason = check(str((event.get("tool_input") or {}).get("command", "")), event.get("cwd") or os.getcwd())
    if not reason:
        return 0
    print(f"omni-team git-guard: {reason}. Organisation policy; ask a human to do it.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
