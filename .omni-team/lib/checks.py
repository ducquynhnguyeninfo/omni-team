"""
Gate 0 — deterministic project checks (lint / typecheck / test) run before any
AI gate. Cheap, reproducible, and it stops reviewers from spending tokens on
code that does not even pass its own tests.

Command source (data, from the profile):
  checks: [<shell>, ...]   → each runs at the project root
  checks: auto             → lint/typecheck/test of each TOUCHED component
                             (all components when none is touched), run in its path
  checks: none | []        → disabled
"""

from __future__ import annotations

import datetime as dt
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Set

CHECK_KINDS = ("lint", "typecheck", "test")
OUTPUT_TAIL_LINES = 40


class ChecksError(Exception):
    pass


@dataclass
class Check:
    name: str
    command: str
    cwd: str          # project-root-relative


@dataclass
class CheckResult:
    check: Check
    exit_code: int
    duration_s: float
    output_tail: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


def resolve(tree: Dict[str, Any], touched: Set[str]) -> List[Check]:
    spec = tree.get("checks", "auto")
    if spec in (None, "none", []):
        return []
    if isinstance(spec, list):
        return [Check(name=str(cmd), command=str(cmd), cwd=".") for cmd in spec]
    if spec != "auto":
        raise ChecksError(f"`checks` must be a list of shell commands, `auto` or `none`, got {spec!r}")
    comps = tree.get("components") or []
    selected = [c for c in comps if str(c.get("name")) in touched] or comps
    resolved = []
    for comp in selected:
        commands = comp.get("commands") or {}
        for kind in CHECK_KINDS:
            if commands.get(kind):
                resolved.append(Check(f"{comp['name']}:{kind}", str(commands[kind]), str(comp.get("path", "."))))
    return resolved


def _run_one(check: Check, project_root: Path, timeout_s: int) -> CheckResult:
    started = time.monotonic()
    try:
        # Commands are the project's own configured shell lines (profile.yaml), hence shell=True.
        done = subprocess.run(check.command, shell=True, cwd=str(project_root / check.cwd),
                              capture_output=True, text=True, timeout=timeout_s, check=False)
        code, output = done.returncode, (done.stdout or "") + (done.stderr or "")
    except subprocess.TimeoutExpired:
        code, output = 124, f"timed out after {timeout_s}s"
    except OSError as exc:
        code, output = 127, f"could not start: {exc}"
    tail = "\n".join(output.strip().splitlines()[-OUTPUT_TAIL_LINES:])
    return CheckResult(check, code, time.monotonic() - started, tail)


def run_all(checks: List[Check], project_root: Path, timeout_s: int) -> List[CheckResult]:
    """Run every check (not fail-fast) so the implementer sees all failures at once."""
    return [_run_one(c, project_root, timeout_s) for c in checks]


def write_log(path: Path, results: List[CheckResult], tree: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"\n\n---\n\n## Checks {dt.datetime.now().isoformat(timespec='seconds')} (snapshot {tree[:12]})\n"]
    for r in results:
        mark = "✅" if r.ok else "❌"
        lines.append(f"- {mark} `{r.check.name}` — `{r.check.command}` in `{r.check.cwd}` "
                     f"(exit {r.exit_code}, {r.duration_s:.1f}s)")
        if not r.ok and r.output_tail:
            lines.append(f"\n```text\n{r.output_tail}\n```\n")
    with path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
