"""
Automation policy — may the agent commit or push its own fixes? (profile `automation`)

    automation:
      pr_fix: off | commit | push     # off (default): the agent commits/pushes only when the user asks
      protected_branches: [...]       # globs never committed or pushed to, besides origin's default branch, main and master
      branch_prefix: omni/            # work branch for a task: <prefix><task-id>

The level only widens what the agent may do unasked. These boundaries hold at every level
and are checked here, deterministically, before each commit/push (`orchestrator.py
automation --action commit|push`): a named work branch that is neither the default branch
nor protected, Gate 0 green on the current snapshot, no halted run (budget exhausted,
clarification needed), and for a push every routed gate passed (a gate not yet run blocks it)
and a push target that is neither the default nor a protected branch. Work found on the
default or a protected branch is not a dead end: the report names the remedy — switch to
`<prefix><task-id>`, push that, open a pull request. This module only reads git; the agent
runs the commands. Never done by anything in omni-team: force-push, history rewrite, merge,
tag, release, branch deletion — merge stays the human gate.
"""

from __future__ import annotations

import fnmatch
import re
from collections import namedtuple
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .diffscope import git

LEVELS = ("off", "commit", "push")
ACTIONS = ("commit", "push")
PASSED = "passed"
NEVER = "never force-push, rewrite pushed history, merge, tag, release or delete branches"
DEFAULT_PREFIX = "omni/"
BAD_REF = re.compile(r"(^[-/.])|\.\.|//|@\{|[\s~^:?*\[\\]|\.lock(/|$)")

# One repository's branch facts. cd: "" for the workspace, "-C <dir> " for a nested repository;
# ahead: commits on the branch not on its upstream (None when it has no upstream).
RepoBranch = namedtuple("RepoBranch", "branch default target ahead cd", defaults=(None, ""))


ALWAYS_PROTECTED = ("main", "master")   # on top of origin's default branch and protected_branches


class AutomationError(Exception):
    pass


@dataclass
class Policy:
    pr_fix: str = "off"
    protected_branches: List[str] = field(default_factory=list)
    branch_prefix: str = DEFAULT_PREFIX

    def work_branch(self, task_id: str) -> str:
        return f"{self.branch_prefix}{task_id}"

    def allows(self, action: str) -> bool:
        return LEVELS.index(self.pr_fix) >= LEVELS.index(action)

    def describe(self) -> str:
        if self.pr_fix == "off":
            return "pr_fix=off — the agent commits/pushes only when the user asks; merge stays human"
        what = "commit fixes" if self.pr_fix == "commit" else "commit and push fixes"
        return (f"pr_fix={self.pr_fix} — the agent may {what} on the work branch after "
                f"`orchestrator.py automation --action {self.pr_fix}` says yes; merge stays human")


def policy(tree: Dict[str, Any]) -> Policy:
    """Validated policy from the merged profile. YAML 1.1 reads a bare `off` as false."""
    raw = tree.get("automation") or {}
    if not isinstance(raw, dict):
        raise AutomationError("automation must be a mapping, e.g. `automation: {pr_fix: off}`")
    unknown = set(raw) - {"pr_fix", "protected_branches", "branch_prefix"}
    if unknown:
        raise AutomationError(f"automation: unknown key(s) {sorted(unknown)}")
    level = raw.get("pr_fix", "off")
    level = "off" if level is False or level is None else level
    if level not in LEVELS:
        raise AutomationError(f"automation.pr_fix must be one of {', '.join(LEVELS)}, got {level!r}")
    protected = raw.get("protected_branches") or []
    if not isinstance(protected, list) or not all(isinstance(p, str) for p in protected):
        raise AutomationError("automation.protected_branches must be a list of branch names or globs")
    prefix = raw.get("branch_prefix", DEFAULT_PREFIX)
    if not isinstance(prefix, str) or not prefix or BAD_REF.search(prefix):
        raise AutomationError(f"automation.branch_prefix must be a git branch-name prefix like 'omni/', got {prefix!r}")
    return Policy(level, protected, prefix)


def current_branch(repo: Path) -> str:
    """The checked-out branch, or "" when HEAD is detached."""
    rc, out = git(["symbolic-ref", "--quiet", "--short", "HEAD"], repo, check=False)
    return out.strip() if rc == 0 else ""


def default_branch(repo: Path) -> str:
    rc, out = git(["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"], repo, check=False)
    return out.strip().split("/", 1)[-1] if rc == 0 and out.strip() else ""


def push_target(repo: Path) -> str:
    """The remote branch a plain `git push` would update (`@{push}`, remote name stripped), or ""."""
    rc, out = git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{push}"], repo, check=False)
    return out.strip().split("/", 1)[-1] if rc == 0 and "/" in out.strip() else ""


def commits_ahead(repo: Path) -> Optional[int]:
    """Local commits not on the upstream of the checked-out branch; None without an upstream."""
    rc, out = git(["rev-list", "--count", "@{upstream}..HEAD"], repo, check=False)
    return int(out.strip()) if rc == 0 and out.strip().isdigit() else None


def _guarded(branch: str, default: str, protected: List[str]) -> str:
    """Why `branch` may never be committed or pushed to unasked, or ""."""
    if branch == default:
        return "is the default branch"
    if branch in ALWAYS_PROTECTED:
        return "is always protected"
    hit = next((p for p in protected if fnmatch.fnmatchcase(branch, p)), None)
    return f"matches protected branch pattern '{hit}'" if hit else ""


def branch_problems(branch: str, default: str, protected: List[str], where: str, target: str = "") -> List[str]:
    if not branch:
        return [f"{where}: HEAD is detached — never commit or push without a work branch"]
    why = _guarded(branch, default, protected)
    if why:
        return [f"{where}: '{branch}' {why} — never committed or pushed to; the work moves to a work branch"]
    why = _guarded(target, default, protected) if target and target != branch else ""
    return [f"{where}: '{branch}' pushes to '{target}', which {why}"] if why else []


def remedy(pol: Policy, action: str, task_id: str, where: str, rb: RepoBranch) -> List[str]:
    """The way forward when the work sits on (or would be pushed to) a guarded branch: a work
    branch and a pull request. Commands for the agent to run; empty when the branch is fine."""
    git_c = f"git {rb.cd}"
    if not rb.branch or _guarded(rb.branch, rb.default, pol.protected_branches):
        work = pol.work_branch(task_id)
        steps = [f"{where}: `{git_c}switch -c {work}` — keeps the uncommitted changes; then re-run this check"]
        if rb.branch and rb.ahead:
            steps.append(f"{where}: {rb.ahead} local commit(s) on '{rb.branch}' are not on its upstream — "
                         f"they come along to '{work}'; moving '{rb.branch}' back "
                         f"(`{git_c}branch -f {rb.branch} @{{upstream}}`) only on the user's yes, never unasked")
        if action == "push":
            steps.append(f"{where}: then `{git_c}push -u origin HEAD` and open a pull request into "
                         f"'{rb.default or 'the default branch'}'")
        return steps
    if action == "push" and rb.target and rb.target != rb.branch \
            and _guarded(rb.target, rb.default, pol.protected_branches):
        return [f"{where}: `{git_c}branch --unset-upstream`, re-run this check, then `{git_c}push -u origin HEAD` "
                f"(publishes '{rb.branch}' under its own name) and open a pull request"]
    return []


def pull_request_steps(task_id: str, branches: Dict[str, tuple], body: str) -> List[str]:
    """After an allowed push: open a pull request for each pushed branch that has none."""
    steps = []
    for where, rb in ((w, RepoBranch(*v)) for w, v in branches.items()):
        base = rb.default or "<default branch>"
        gh = f"gh {'-R <repo> ' if rb.cd else ''}"
        steps.append(f"{where}: `git {rb.cd}push -u origin HEAD`; if `{gh}pr view {rb.branch}` finds no pull request, "
                     f"`{gh}pr create --base {base} --head {rb.branch} --title \"{task_id}: <title>\" "
                     f"--body-file {body}` (no --admin, no auto-merge); without gh, give the user the compare "
                     f"URL ({base}...{rb.branch}); record the pull-request URL in the journal")
    return steps


def verdict(pol: Policy, action: str, task_id: str, branches: Dict[str, tuple], checks_green: bool,
            phase: str, gate_status: Dict[str, str], body: str) -> Tuple[bool, str]:
    """`orchestrator.py automation` output: (allowed, report)."""
    found = problems(pol, action, branches, checks_green, phase, gate_status)
    rbs = {w: RepoBranch(*v) for w, v in branches.items()}
    where = ", ".join(f"{k} on '{rb.branch or 'detached HEAD'}'" for k, rb in rbs.items())
    if not found:
        lines = [f"✅ {action} allowed ({where}) — add a `Task: {task_id}` trailer, record it in the journal, "
                 f"and {NEVER}"]
        lines += [f"   → {s}" for s in (pull_request_steps(task_id, branches, body) if action == "push" else [])]
        return True, "\n".join(lines)
    lines = [f"⛔ {action} not allowed unasked ({where}):"] + [f"   - {p}" for p in found]
    fixes = [s for w, rb in rbs.items() for s in remedy(pol, action, task_id, w, rb)]
    if fixes:
        lines += ["   Never on the default or a protected branch — move the work to a work branch and open a pull request:"]
        lines += [f"   → {s}" for s in fixes]
    return False, "\n".join(lines)


def problems(pol: Policy, action: str, branches: Dict[str, tuple], checks_green: bool,
             phase: str, gate_status: Dict[str, str]) -> List[str]:
    """Why `action` may not happen unasked now; empty → allowed.

    branches: repo label → RepoBranch fields (current branch, default branch, push target[, ahead, cd]).
    gate_status: every routed gate → its status ("not run" when it has no state yet).
    """
    if action not in ACTIONS:
        raise AutomationError(f"action must be one of {', '.join(ACTIONS)}")
    found = []
    if not pol.allows(action):
        found.append(f"automation.pr_fix is '{pol.pr_fix}' — {action} only when the user asks")
    for where, rb in ((w, RepoBranch(*v)) for w, v in branches.items()):
        found += branch_problems(rb.branch, rb.default, pol.protected_branches, where,
                                 rb.target if action == "push" else "")
    if not checks_green:
        found.append("Gate 0 is not green on the current snapshot — run `orchestrator.py checks` first")
    if phase == "halted":
        found.append("the run is halted (retry budget exhausted or a human is needed) — escalate instead")
    if action == "push":
        found += [f"gate {name} is {status} — every routed gate must pass before pushing"
                  for name, status in gate_status.items() if status != PASSED]
    return found
