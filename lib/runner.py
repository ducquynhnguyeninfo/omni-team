"""
Agent runner — wraps spawning a `claude -p` subprocess (or emitting an
inline invocation prompt) for a single agent on a single scope.

The runner is intentionally thin: it builds a prompt, runs Claude headless,
captures the verbatim output, classifies the verdict from the output,
appends to the per-agent artifact file, and returns a (verdict, output) tuple.
"""

from __future__ import annotations

import datetime as dt
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path


VERDICT_PATTERNS = [
    # order matters: more specific first
    (re.compile(r"\bBLOCK\b"), "BLOCK"),
    (re.compile(r"\bBLOCKED\b"), "BLOCKED"),
    (re.compile(r"\bREQUEST[_ -]CHANGES\b", re.I), "REQUEST_CHANGES"),
    (re.compile(r"\bNEEDS[_ -]WORK\b", re.I), "REQUEST_CHANGES"),
    (re.compile(r"\bNEEDS[_ -]ATTENTION\b", re.I), "REQUEST_CHANGES"),
    (re.compile(r"\bNEEDS[_ -]CLARIFICATION\b", re.I), "NEEDS_CLARIFICATION"),
    (re.compile(r"\bSHIP[_ -]READY\b", re.I), "APPROVE"),
    (re.compile(r"\bAPPROVE\b"), "APPROVE"),
    (re.compile(r"\bADEQUATE\b"), "APPROVE"),
    (re.compile(r"\bPASS\b"), "APPROVE"),
    (re.compile(r"\bNOT[_ -]APPLICABLE\b", re.I), "NOT_APPLICABLE"),
    (re.compile(r"\bNOT[_ -]IN[_ -]SCOPE\b", re.I), "NOT_APPLICABLE"),
]


@dataclass
class AgentResult:
    agent: str
    verdict: str
    output: str
    duration_s: float
    artifact_path: Path


def classify_verdict(text: str) -> str:
    # scan the LAST 60 lines (verdict block is at the bottom)
    tail = "\n".join(text.splitlines()[-60:])
    for pattern, verdict in VERDICT_PATTERNS:
        if pattern.search(tail):
            return verdict
    return "UNKNOWN"


def _build_prompt(agent: str, scope_summary: str, project_root: Path) -> str:
    return (
        f"You are running headless inside `claude -p`. Act as the `{agent}` "
        f"sub-agent defined in `.claude/agents/{agent}.md` — read that file "
        f"first to load your role and rules.\n\n"
        f"Project root: {project_root}\n\n"
        f"Scope for this invocation:\n{scope_summary}\n\n"
        f"Produce your full report exactly per the agent's Output format. "
        f"End with the verdict line."
    )


def invoke(
    *,
    agent: str,
    scope_summary: str,
    project_root: Path,
    artifact_path: Path,
    claude_cmd: str = "claude",
    timeout_s: int = 1800,
    dry_run: bool = False,
) -> AgentResult:
    """Spawn `claude -p` for one agent, capture verbatim output."""
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    prompt = _build_prompt(agent, scope_summary, project_root)

    started = dt.datetime.now()
    if dry_run:
        output = (
            f"[DRY-RUN] would invoke: {claude_cmd} -p (agent={agent})\n"
            f"---prompt---\n{prompt}\n---end---\n"
            f"### Verdict\nAPPROVE — dry-run synthetic verdict\n"
        )
    else:
        cmd = [claude_cmd, "-p", prompt]
        try:
            completed = subprocess.run(
                cmd,
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
            output = (completed.stdout or "") + (
                f"\n[stderr]\n{completed.stderr}" if completed.stderr else ""
            )
            if completed.returncode != 0:
                output += f"\n[exit-code {completed.returncode}]"
        except FileNotFoundError:
            output = (
                f"[ERROR] `{claude_cmd}` not found in PATH. "
                f"Set orchestrator.claude_cmd or install Claude CLI.\n"
                f"### Verdict\nBLOCK — runner could not invoke Claude CLI\n"
            )
        except subprocess.TimeoutExpired:
            output = (
                f"[ERROR] {agent} timed out after {timeout_s}s\n"
                f"### Verdict\nBLOCK — timeout\n"
            )

    duration_s = (dt.datetime.now() - started).total_seconds()
    verdict = classify_verdict(output)

    # Append per-agent artifact entry
    header = (
        f"\n\n---\n\n"
        f"## Invocation: {started.isoformat()}\n"
        f"- agent: `{agent}`\n"
        f"- verdict: **{verdict}**\n"
        f"- duration: {duration_s:.1f}s\n"
        f"- cmd: `{shlex.join([claude_cmd, '-p', '<prompt>'])}`\n\n"
        f"### Output\n\n"
    )
    with artifact_path.open("a", encoding="utf-8") as fh:
        fh.write(header + output + "\n")

    return AgentResult(
        agent=agent,
        verdict=verdict,
        output=output,
        duration_s=duration_s,
        artifact_path=artifact_path,
    )
