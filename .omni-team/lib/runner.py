"""
Gate runner — build a self-contained role prompt, run it through a headless
engine (claude / codex / any CLI declared in defaults.yaml), parse the
verdict, and append the verbatim output to the role's artifact file.

The prompt embeds the canonical role + protocol, so headless runs do not
depend on install.py having been run.
"""

from __future__ import annotations

import datetime as dt
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .roles import Role, compose_instructions

VERDICTS = (
    "APPROVE", "REQUEST_CHANGES", "BLOCK", "NOT_APPLICABLE",
    "NEEDS_CLARIFICATION", "BLOCKED", "PLAN_READY",
)
ALIASES = {
    "SHIP_READY": "APPROVE", "PASS": "APPROVE", "ADEQUATE": "APPROVE",
    "NEEDS_WORK": "REQUEST_CHANGES", "NEEDS_ATTENTION": "REQUEST_CHANGES",
    "INSUFFICIENT": "REQUEST_CHANGES", "NOT_IN_SCOPE": "NOT_APPLICABLE",
}
# Tolerates markdown decoration such as **VERDICT:** `APPROVE`.
_VERDICT_LINE = re.compile(r"^[\s>*_`#-]*VERDICT[*_`\s]*:[*_`\s]*(.*)$", re.IGNORECASE)
_TOKENS = sorted(set(VERDICTS) | set(ALIASES), key=len, reverse=True)
_TOKEN_RES = [
    (tok, re.compile(r"^" + tok.replace("_", r"[ _-]") + r"(?![A-Za-z_])", re.IGNORECASE))
    for tok in _TOKENS
]


STDERR_TAIL_LINES = 30


class EngineError(Exception):
    pass


@dataclass
class GateResult:
    role: str
    verdict: str
    output: str
    duration_s: float
    artifact_path: Path


def parse_verdict(text: str) -> str:
    """Return the LAST `VERDICT: <TOKEN>` line's token, or UNKNOWN. Never guesses from prose."""
    for line in reversed(text.splitlines()):
        match = _VERDICT_LINE.match(line)
        if not match:
            continue
        rest = match.group(1).strip()
        for token, rx in _TOKEN_RES:
            if rx.match(rest):
                return ALIASES.get(token, token)
        return "UNKNOWN"
    return "UNKNOWN"


def build_prompt(role: Role, protocol: str, invocation: str) -> str:
    return (
        f"You are running headless as the omni-team role `{role.name}`. Your complete "
        f"instructions follow; obey them exactly.\n\n"
        f"{compose_instructions(role, protocol)}\n---\n\n"
        f"## This invocation\n\n{invocation.strip()}\n\n"
        f"Produce your full report using your role's output template. "
        f"The last line must be the `VERDICT:` line."
    )


def engine_argv(engine: Dict[str, Any], role: Role, prompt: str) -> Tuple[List[str], Optional[str]]:
    """Return (argv, stdin). Without a `{prompt}` element the prompt is piped through stdin."""
    template = engine.get("cmd_run") if role.access == "run" and engine.get("cmd_run") else engine.get("cmd")
    if not template:
        raise EngineError("engine has no `cmd` argv template")
    tier = str((engine.get("tiers") or {}).get(role.tier, ""))
    argv = [prompt if arg == "{prompt}" else str(arg).replace("{tier}", tier) for arg in template]
    return argv, (None if "{prompt}" in template else prompt)


def _execute(argv: List[str], stdin: Optional[str], cwd: Path, timeout_s: int) -> str:
    try:
        done = subprocess.run(
            argv, input=stdin, cwd=str(cwd), capture_output=True, text=True,
            timeout=timeout_s, check=False,
        )
    except FileNotFoundError:
        return f"[runner] `{argv[0]}` not found on PATH.\nVERDICT: BLOCKED — engine CLI missing\n"
    except subprocess.TimeoutExpired:
        return f"[runner] timed out after {timeout_s}s.\nVERDICT: BLOCKED — timeout\n"
    output = done.stdout or ""
    if done.returncode == 0:
        return output
    # The verdict must come from the report (stdout) only: some CLIs echo the prompt — which
    # contains example VERDICT lines — to stderr. Re-state the stdout verdict as the last line.
    verdict = parse_verdict(output)
    stderr_tail = "\n".join((done.stderr or "").strip().splitlines()[-STDERR_TAIL_LINES:])
    output += f"\n[runner] exit code {done.returncode}; stderr (last {STDERR_TAIL_LINES} lines):\n{stderr_tail}\n"
    if verdict == "UNKNOWN":
        return output + "VERDICT: BLOCKED — engine exited with an error\n"
    return output + f"VERDICT: {verdict} — restated from the report; engine exited non-zero\n"


def _append_artifact(path: Path, role: str, verdict: str, started: dt.datetime,
                     duration_s: float, engine_name: str, output: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        f"\n\n---\n\n## Invocation {started.isoformat(timespec='seconds')}\n"
        f"- role: `{role}`\n- engine: `{engine_name}`\n"
        f"- verdict: **{verdict}**\n- duration: {duration_s:.1f}s\n\n### Output\n\n"
    )
    with path.open("a", encoding="utf-8") as fh:
        fh.write(header + output.rstrip() + "\n")


def run_gate(
    *,
    role: Role,
    protocol: str,
    invocation: str,
    engine_name: str,
    engine: Dict[str, Any],
    project_root: Path,
    artifact_path: Path,
    timeout_s: int,
    dry_run: bool = False,
) -> GateResult:
    prompt = build_prompt(role, protocol, invocation)
    started = dt.datetime.now()
    if dry_run:
        argv, stdin = engine_argv(engine, role, "<prompt>")
        output = (
            f"[dry-run] would run: {' '.join(argv)}{' < <prompt>' if stdin else ''}\n"
            f"[dry-run] prompt: {len(prompt):,} chars\n"
            f"VERDICT: {'PLAN_READY' if role.name == 'tech-lead' else 'APPROVE'} — dry-run synthetic verdict\n"
        )
    else:
        argv, stdin = engine_argv(engine, role, prompt)
        output = _execute(argv, stdin, project_root, timeout_s)
    duration_s = (dt.datetime.now() - started).total_seconds()
    verdict = parse_verdict(output)
    _append_artifact(artifact_path, role.name, verdict, started, duration_s, engine_name, output)
    return GateResult(role.name, verdict, output, duration_s, artifact_path)
