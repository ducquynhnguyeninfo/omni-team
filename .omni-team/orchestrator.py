#!/usr/bin/env python3
"""
orchestrator.py — headless runner for the omni-team review gates.

    python3 .omni-team/orchestrator.py classify --task T-1        # which gates would run, no AI calls
    python3 .omni-team/orchestrator.py run      --task T-1        # run pending gates serially
    python3 .omni-team/orchestrator.py run-gate code-reviewer --task T-1
    python3 .omni-team/orchestrator.py status   --task T-1
    python3 .omni-team/orchestrator.py prompt   code-reviewer --task T-1   # print the full prompt

Common flags: --engine claude|codex|<custom>, --base <ref>, --committed-only,
--spec <path>, --request "<text>", --profile <path>, --dry-run, --fresh.

Exit codes: 0 ready for the human gate · 1 paused (fix findings, re-run) ·
2 configuration error · 3 REQUEST_CHANGES budget exhausted · 4 BLOCK budget
exhausted · 5 unparseable verdict · 6 needs a human (clarification / blocked env).

The orchestrator NEVER commits, pushes or merges. It stops at the human gate.
Requires PyYAML (pip install -r .omni-team/requirements.txt).
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

FRAMEWORK_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = FRAMEWORK_ROOT.parent
sys.path.insert(0, str(FRAMEWORK_ROOT))

from lib import diffscope, profile  # noqa: E402
from lib.roles import RoleError, load_protocol, role_by_name  # noqa: E402
from lib.routing import RoutingError, select_gates  # noqa: E402
from lib.runner import EngineError, build_prompt, run_gate  # noqa: E402
from lib.state import GateState, RunState  # noqa: E402

TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
PASSING = {"APPROVE", "NOT_APPLICABLE", "PLAN_READY"}
EXIT_READY, EXIT_PAUSED, EXIT_CONFIG, EXIT_RC_BUDGET, EXIT_BLOCK_BUDGET, EXIT_UNKNOWN, EXIT_HUMAN = 0, 1, 2, 3, 4, 5, 6


class Context:
    """Everything one invocation needs: merged profile, diff scope, routing, paths."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.tree = profile.load(args.profile)
        orch = self.tree.get("orchestrator", {})
        self.orch = orch
        self.task_id = args.task
        if not TASK_ID_RE.match(self.task_id):
            raise profile.ProfileError(f"task id '{self.task_id}' may only contain letters, digits, . _ -")
        self.artifacts = PROJECT_ROOT / str(self.tree["artifacts_dir"]).format(task_id=self.task_id)
        self.state_path = self.artifacts / "_state.json"
        self._diff: Optional[diffscope.DiffInfo] = None
        self._selection = None

    @property
    def diff(self) -> diffscope.DiffInfo:
        if self._diff is None:
            self._diff = diffscope.compute(
                PROJECT_ROOT,
                self.args.base or str(self.orch.get("base_ref", "auto")),
                bool(self.orch.get("include_uncommitted", True)) and not self.args.committed_only,
                list(self.orch.get("exclude_paths", [])),
                profile.components(self.tree),
            )
        return self._diff

    @property
    def selection(self):
        if self._selection is None:
            self._selection = select_gates(self.tree, self.diff.scope)
        return self._selection

    def engine(self) -> tuple:
        name = self.args.engine or str(self.orch.get("engine", "claude"))
        engines: Dict[str, Any] = self.orch.get("engines", {})
        if name not in engines:
            raise EngineError(f"engine '{name}' is not defined under orchestrator.engines ({', '.join(engines)})")
        return name, engines[name]

    def rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(PROJECT_ROOT))
        except ValueError:
            return str(path)


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------

def scope_summary(ctx: Context) -> str:
    d, sel, wu = ctx.diff, ctx.selection, ctx.tree.get("work_unit", {})
    fired = [name for name, on in sel.signals.items() if on]
    files = "\n".join(f"  - {p}" for p in d.scope.changed_paths[:80])
    more = len(d.scope.changed_paths) - 80
    lines = [
        f"- {wu.get('label', 'Task')} id: {ctx.task_id}",
        f"- Acceptance source: {ctx.args.spec or 'locate by id under work_unit.spec_root (' + str(wu.get('spec_root', 'auto')) + ')'}",
        f"- Request: {ctx.args.request or '(see spec / tech-lead plan)'}",
        f"- Artifacts directory (earlier gate reports): {ctx.rel(ctx.artifacts)}/",
        f"- Diff: base {d.base_ref}, {d.compared_to}",
        f"- Lines added: {d.scope.loc}; files changed: {len(d.scope.changed_paths)}",
        f"- Components touched: {', '.join(sorted(d.scope.components)) or '(none declared / auto)'}",
        f"- Signals: {', '.join(fired) or '(none)'}",
        f"- Routed gates in order: {', '.join(sel.gates) or '(none)'}",
    ]
    lines += [f"- Note: {n}" for n in d.notes]
    lines.append("- Changed files:\n" + (files or "  (none)") + (f"\n  … and {more} more" if more > 0 else ""))
    return "\n".join(lines)


def invocation_text(ctx: Context, gate: GateState) -> str:
    text = scope_summary(ctx)
    if gate.attempts:
        text += (
            f"\n\nThis is attempt {gate.attempts + 1}. Your previous verdict was {gate.last_verdict}; "
            f"previous reports are in {ctx.rel(ctx.artifacts / (gate.name + '.md'))}. "
            f"Verify each earlier finding was addressed before looking for new ones."
        )
    return text


def write_summary(ctx: Context, state: RunState) -> None:
    rows = "\n".join(
        f"| {g.name} | {g.status} | {g.last_verdict or '-'} | {g.attempts} | [{g.name}.md]({g.name}.md) |"
        for g in state.gates
    )
    body = (
        f"# omni-team run — {state.task_id}\n\n"
        f"- phase: **{state.phase}**{(' — ' + state.halt_reason) if state.halt_reason else ''}\n"
        f"- base rule: {state.base_rule}; add rules: {', '.join(state.add_rules) or '(none)'}\n"
        f"- next step: {ctx.tree.get('human_gate', 'human review')}\n\n"
        f"| Gate | Status | Last verdict | Attempts | Report |\n|---|---|---|---|---|\n{rows}\n"
    )
    (ctx.artifacts / "_summary.md").write_text(body, encoding="utf-8")


def log_escape(ctx: Context, gate: GateState, reason: str) -> None:
    path = ctx.artifacts / "_escapes.md"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(
            f"\n## {dt.datetime.now().isoformat(timespec='seconds')} — {gate.name}\n"
            f"- reason: **{reason}**\n- last verdict: {gate.last_verdict}\n- attempts: {gate.attempts}\n"
        )


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_classify(ctx: Context) -> int:
    sel = ctx.selection
    print("📊 Scope\n" + scope_summary(ctx))
    print(f"\n🎯 Base rule: {sel.base_rule}")
    print(f"➕ Add rules: {', '.join(sel.add_rules) or '(none)'}")
    print(f"🧩 Gates ({len(sel.gates)}): {' → '.join(sel.gates) or 'none — run the project checks only'}")
    return EXIT_READY


def _execute_gate(ctx: Context, gate: GateState):
    engine_name, engine = ctx.engine()
    return run_gate(
        role=role_by_name(gate.name),
        protocol=load_protocol(),
        invocation=invocation_text(ctx, gate),
        engine_name=engine_name,
        engine=engine,
        project_root=PROJECT_ROOT,
        artifact_path=ctx.artifacts / f"{gate.name}.md",
        timeout_s=int(ctx.args.timeout or ctx.orch.get("timeout_s", 1800)),
        dry_run=ctx.args.dry_run,
    )


def _record(ctx: Context, state: RunState, gate: GateState, verdict: str) -> Optional[int]:
    """Update gate state from a verdict. Returns an exit code to stop with, or None to continue."""
    budget = ctx.orch.get("retry_budget", {})
    gate.attempts += 1
    gate.last_verdict = verdict
    gate.last_run_at = dt.datetime.now().isoformat(timespec="seconds")
    if verdict in PASSING:
        gate.status = "passed"
        return None
    if verdict in ("REQUEST_CHANGES", "BLOCK"):
        counter = "request_changes_count" if verdict == "REQUEST_CHANGES" else "block_count"
        limit = int(budget.get("request_changes_max" if verdict == "REQUEST_CHANGES" else "block_max", 3))
        setattr(gate, counter, getattr(gate, counter) + 1)
        gate.status = "request_changes" if verdict == "REQUEST_CHANGES" else "block"
        if getattr(gate, counter) >= limit:
            state.phase, state.halt_reason = "halted", f"{gate.name}: {verdict} budget ({limit}) exhausted"
            log_escape(ctx, gate, f"{verdict.lower()} budget exhausted")
            return EXIT_RC_BUDGET if verdict == "REQUEST_CHANGES" else EXIT_BLOCK_BUDGET
        print(f"   ⏸  fix the findings in {ctx.rel(ctx.artifacts / (gate.name + '.md'))}, then re-run")
        return EXIT_PAUSED
    gate.status = "needs_human" if verdict in ("NEEDS_CLARIFICATION", "BLOCKED") else "error"
    state.phase, state.halt_reason = "halted", f"{gate.name}: {verdict}"
    return EXIT_HUMAN if gate.status == "needs_human" else EXIT_UNKNOWN


def cmd_run(ctx: Context) -> int:
    sel = ctx.selection
    if ctx.state_path.exists() and not ctx.args.fresh:
        state = RunState.from_path(ctx.state_path)
        added = state.sync_gates(sel.gates)
        state.phase, state.halt_reason = "review", ""
        print(f"📂 resuming {ctx.rel(ctx.state_path)}" + (f" (+ new gates: {', '.join(added)})" if added else ""))
    else:
        state = RunState(task_id=ctx.task_id, base_rule=sel.base_rule, add_rules=sel.add_rules,
                         gates=[GateState(name=g) for g in sel.gates])
    state.save(ctx.state_path)
    print(f"🚀 {ctx.task_id}: {' → '.join(g.name for g in state.gates) or 'no gates'} (engine: {ctx.engine()[0]})")

    for gate in state.gates:
        if gate.status == "passed":
            print(f"   ✅ {gate.name}: already passed")
            continue
        print(f"   ▶  {gate.name} (attempt {gate.attempts + 1}) …", flush=True)
        result = _execute_gate(ctx, gate)
        stop = _record(ctx, state, gate, result.verdict)
        print(f"   {'✅' if stop is None else '✋'} {gate.name}: {result.verdict} ({result.duration_s:.0f}s)")
        state.save(ctx.state_path)
        if stop is not None:
            write_summary(ctx, state)
            return stop

    state.phase = "ready_for_human"
    state.save(ctx.state_path)
    write_summary(ctx, state)
    print(f"\n🏁 all gates passed. Next (HUMAN): {ctx.tree.get('human_gate')}")
    print(f"   summary: {ctx.rel(ctx.artifacts / '_summary.md')}")
    return EXIT_READY


def cmd_run_gate(ctx: Context) -> int:
    state = RunState.from_path(ctx.state_path) if ctx.state_path.exists() else RunState(task_id=ctx.task_id)
    gate = state.gate(ctx.args.role) or GateState(name=ctx.args.role)
    if state.gate(gate.name) is None:
        state.gates.append(gate)
    result = _execute_gate(ctx, gate)
    stop = _record(ctx, state, gate, result.verdict)
    state.save(ctx.state_path)
    print(f"{gate.name}: {result.verdict} ({result.duration_s:.0f}s) → {ctx.rel(result.artifact_path)}")
    return EXIT_READY if stop is None else stop


def cmd_status(ctx: Context) -> int:
    if not ctx.state_path.exists():
        print(f"no state yet at {ctx.rel(ctx.state_path)}")
        return EXIT_PAUSED
    state = RunState.from_path(ctx.state_path)
    icons = {"passed": "✅", "request_changes": "✋", "block": "⛔", "needs_human": "🙋", "error": "❓"}
    print(f"📂 {ctx.rel(ctx.state_path)}\n   phase: {state.phase}{(' — ' + state.halt_reason) if state.halt_reason else ''}")
    for g in state.gates:
        print(f"   {icons.get(g.status, '·')} {g.name:18s} attempts={g.attempts} last={g.last_verdict or '-'}")
    return EXIT_READY if state.phase == "ready_for_human" else EXIT_PAUSED


def cmd_prompt(ctx: Context) -> int:
    role = role_by_name(ctx.args.role)
    print(build_prompt(role, load_protocol(), invocation_text(ctx, GateState(name=role.name))))
    return EXIT_READY


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--task", required=True, help="work-unit id, e.g. TASK-12 (used for the artifacts folder)")
        p.add_argument("--profile", type=Path, help="profile path (default: .omni-team/project/profile.yaml)")
        p.add_argument("--base", help="git base ref (default: orchestrator.base_ref)")
        p.add_argument("--committed-only", action="store_true", help="ignore uncommitted / untracked changes")
        p.add_argument("--spec", help="spec / ticket path passed to the roles")
        p.add_argument("--request", help="plain-language task statement passed to the roles")
        p.add_argument("--engine", help="engine name under orchestrator.engines (default: orchestrator.engine)")
        p.add_argument("--timeout", type=int, help="per-gate timeout in seconds")
        p.add_argument("--dry-run", action="store_true", help="no AI calls; synthetic APPROVE verdicts")

    for name, helptext in (("classify", "show scope and routed gates"), ("run", "run pending gates"),
                           ("status", "show state")):
        p = sub.add_parser(name, help=helptext)
        common(p)
        if name == "run":
            p.add_argument("--fresh", action="store_true", help="discard existing state and start over")
    for name, helptext in (("run-gate", "run one named gate"), ("prompt", "print a role's full prompt")):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("role")
        common(p)
    return parser


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    dispatch = {"classify": cmd_classify, "run": cmd_run, "run-gate": cmd_run_gate,
                "status": cmd_status, "prompt": cmd_prompt}
    try:
        return dispatch[args.cmd](Context(args))
    except (profile.ProfileError, RoutingError, RoleError, EngineError, diffscope.GitError) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return EXIT_CONFIG


if __name__ == "__main__":
    raise SystemExit(main())
