#!/usr/bin/env python3
"""
orchestrator.py — headless runner for the omni-team review gates.

    python3 .omni-team/orchestrator.py classify --task T-1        # scope, gates, stages — no AI calls
    python3 .omni-team/orchestrator.py checks   --task T-1        # Gate 0 only: the project's own checks
    python3 .omni-team/orchestrator.py run      --task T-1        # Gate 0, then the routed gates stage by stage
    python3 .omni-team/orchestrator.py run-gate code-reviewer --task T-1
    python3 .omni-team/orchestrator.py status   --task T-1
    python3 .omni-team/orchestrator.py prompt   code-reviewer --task T-1   # print the full prompt

Common flags: --engine claude|codex|<custom>, --base <ref>, --committed-only,
--spec <path>, --request "<text>", --profile <path>, --dry-run.
run only: --fresh, --skip-checks, --serial.

Exit codes: 0 ready for the human gate · 1 paused (fix findings, re-run) ·
2 configuration error · 3 REQUEST_CHANGES budget exhausted · 4 BLOCK budget
exhausted · 5 unparseable verdict · 6 needs a human (clarification / blocked env) ·
7 project checks (Gate 0) failed.

The orchestrator NEVER commits, pushes or merges. It stops at the human gate.
Requires PyYAML (pip install -r .omni-team/requirements.txt).
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

FRAMEWORK_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = FRAMEWORK_ROOT.parent
sys.path.insert(0, str(FRAMEWORK_ROOT))

from lib import checks, diffscope, pipeline, profile  # noqa: E402
from lib.pipeline import EXIT_CHECKS, EXIT_CONFIG, EXIT_PAUSED, EXIT_READY  # noqa: E402
from lib.roles import RoleError, load_protocol, role_by_name  # noqa: E402
from lib.routing import RoutingError, plan_stages, select_gates  # noqa: E402
from lib.runner import EngineError, build_prompt, run_gate  # noqa: E402
from lib.state import GateState, RunState  # noqa: E402

TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
ICONS = {"passed": "✅", "request_changes": "✋", "block": "⛔", "needs_human": "🙋", "error": "❓"}


def generated_paths() -> List[str]:
    """Adapter files install.py generated (see install.record_generated) — never review scope."""
    listing = FRAMEWORK_ROOT / ".generated"
    if not listing.exists():
        return []
    return [line.strip() for line in listing.read_text(encoding="utf-8").splitlines() if line.strip()]


class Context:
    """Everything one invocation needs: merged profile, diff scope, routing, paths."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.tree = profile.load(args.profile)
        self.orch: Dict[str, Any] = self.tree.get("orchestrator", {})
        self.task_id = args.task
        if not TASK_ID_RE.match(self.task_id):
            raise profile.ProfileError(f"task id '{self.task_id}' may only contain letters, digits, . _ -")
        self.artifacts = PROJECT_ROOT / str(self.tree["artifacts_dir"]).format(task_id=self.task_id)
        self.state_path = self.artifacts / "_state.json"
        self.excludes: List[str] = list(self.orch.get("exclude_paths", [])) + generated_paths()
        self._diff: Optional[diffscope.DiffInfo] = None
        self._selection = None

    @property
    def diff(self) -> diffscope.DiffInfo:
        if self._diff is None:
            self._diff = diffscope.compute(
                PROJECT_ROOT,
                self.args.base or str(self.orch.get("base_ref", "auto")),
                bool(self.orch.get("include_uncommitted", True)) and not self.args.committed_only,
                self.excludes,
                profile.components(self.tree),
                list(self.orch.get("base_candidates") or diffscope.DEFAULT_BASE_CANDIDATES),
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

    def budget(self) -> pipeline.Budget:
        raw = self.orch.get("retry_budget", {})
        return pipeline.Budget(int(raw.get("request_changes_max", 3)), int(raw.get("block_max", 3)))

    def load_state(self) -> RunState:
        return RunState.from_path(self.state_path) if self.state_path.exists() else RunState(task_id=self.task_id)

    def rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(PROJECT_ROOT))
        except ValueError:
            return str(path)


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------

def stages_text(stages: List[List[str]]) -> str:
    return " → ".join("[" + " ‖ ".join(s) + "]" for s in stages) or "none — run the project checks only"


def repo_lines(d: diffscope.DiffInfo) -> List[str]:
    """For workspaces with nested repos: where each part of the diff lives and how to see it."""
    if len(d.repos) < 2:
        return []
    lines = ["- Repositories (each nested repo has its own git history — run git inside it):"]
    for r in d.repos:
        where = "workspace" if r.key == diffscope.WORKSPACE else r.key
        cmd = "git diff" if r.key == diffscope.WORKSPACE else f"git -C {r.key} diff"
        lines.append(f"  - {where}: {r.changed} changed file(s); see `{cmd} {r.point[:12]}` plus untracked files")
    return lines


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
        *repo_lines(d),
        f"- Lines added: {d.scope.loc}; files changed: {len(d.scope.changed_paths)}",
        f"- Components touched: {', '.join(sorted(d.scope.components)) or '(none declared / auto)'}",
        f"- Signals: {', '.join(fired) or '(none)'}",
        f"- Routed gates (stages): {stages_text(sel.stages)}",
    ]
    lines += [f"- Note: {n}" for n in d.notes]
    lines.append("- Changed files:\n" + (files or "  (none)") + (f"\n  … and {more} more" if more > 0 else ""))
    return "\n".join(lines)


def invocation_text(ctx: Context, gate: GateState) -> str:
    text = scope_summary(ctx)
    if gate.attempts:
        text += (
            f"\n\nThis is attempt {gate.attempts + 1}. Your previous verdict was {gate.last_verdict}"
            f"{' (' + gate.note + ')' if gate.note else ''}; previous reports are in "
            f"{ctx.rel(ctx.artifacts / (gate.name + '.md'))}. "
            f"Verify each earlier finding was addressed before looking for new ones."
        )
    return text


def write_summary(ctx: Context, state: RunState) -> None:
    rows = "\n".join(
        f"| {g.name} | {g.status} | {g.last_verdict or '-'} | {g.attempts} | {g.note or ''} | [{g.name}.md]({g.name}.md) |"
        for g in state.gates
    )
    body = (
        f"# omni-team run — {state.task_id}\n\n"
        f"- phase: **{state.phase}**{(' — ' + state.halt_reason) if state.halt_reason else ''}\n"
        f"- base rule: {state.base_rule}; add rules: {', '.join(state.add_rules) or '(none)'}\n"
        f"- project checks (Gate 0): {'green on ' + state.checks_green_tree[:12] if state.checks_green_tree else 'not green yet'}"
        f" — log: [_checks.md](_checks.md)\n"
        f"- next step: {ctx.tree.get('human_gate', 'human review')}\n"
        f"{commit_hint(ctx)}\n"
        f"| Gate | Status | Last verdict | Attempts | Note | Report |\n|---|---|---|---|---|---|\n{rows}\n"
    )
    ctx.artifacts.mkdir(parents=True, exist_ok=True)
    (ctx.artifacts / "_summary.md").write_text(body, encoding="utf-8")


def commit_hint(ctx: Context) -> str:
    changed = [r for r in ctx.diff.repos if r.changed]
    if len(ctx.diff.repos) < 2 or not changed:
        return ""
    names = ", ".join(f"`{'workspace' if r.key == diffscope.WORKSPACE else r.key}` ({r.changed} files)" for r in changed)
    return f"- repositories with changes to commit (each separately): {names}\n"


def log_escape(ctx: Context, gate: GateState, reason: str) -> None:
    with (ctx.artifacts / "_escapes.md").open("a", encoding="utf-8") as fh:
        fh.write(
            f"\n## {dt.datetime.now().isoformat(timespec='seconds')} — {gate.name}\n"
            f"- reason: **{reason}**\n- last verdict: {gate.last_verdict}\n- attempts: {gate.attempts}\n"
        )


# ---------------------------------------------------------------------------
# Gate 0 and gate execution
# ---------------------------------------------------------------------------

def run_checks(ctx: Context, state: RunState, force: bool = False) -> Optional[int]:
    """Gate 0. Returns EXIT_CHECKS on failure, None when green / skipped / nothing to run."""
    tree = ctx.diff.tree
    if not force and state.checks_green_tree == tree:
        print("   ✅ gate 0 (project checks): already green for this snapshot")
        return None
    planned = checks.resolve(ctx.tree, ctx.diff.scope.components)
    if not planned:
        print("   ⚠️  gate 0: no checks configured (set `checks` or component `commands` in project/profile.yaml)")
        return None
    if ctx.args.dry_run:
        for c in planned:
            print(f"   [dry-run] gate 0 would run `{c.command}` in {c.cwd}")
        return None
    print(f"   ▶  gate 0: {len(planned)} project check(s) …", flush=True)
    results = checks.run_all(planned, PROJECT_ROOT, int(ctx.orch.get("checks_timeout_s", 900)))
    checks.write_log(ctx.artifacts / "_checks.md", results, tree)
    for r in results:
        print(f"      {'✅' if r.ok else '❌'} {r.check.name} (exit {r.exit_code}, {r.duration_s:.0f}s)")
    failed = [r.check.name for r in results if not r.ok]
    if failed:
        state.phase, state.halt_reason = "checks_failed", f"project checks failed: {', '.join(failed)}"
        print(f"   ⛔ fix the failing checks first — details in {ctx.rel(ctx.artifacts / '_checks.md')}")
        return EXIT_CHECKS
    state.checks_green_tree = tree
    return None


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


def _record(ctx: Context, state: RunState, gate: GateState, result) -> Optional[int]:
    code, escape = pipeline.record(state, gate, result.verdict, ctx.diff.tree, ctx.budget())
    if escape:
        log_escape(ctx, gate, escape)
    icon = "✅" if code is None else ICONS.get(gate.status, "✋")
    print(f"   {icon} {gate.name}: {result.verdict} ({result.duration_s:.0f}s)")
    return code


def _prepare_state(ctx: Context) -> RunState:
    sel = ctx.selection
    if ctx.state_path.exists() and not ctx.args.fresh:
        state = RunState.from_path(ctx.state_path)
        state.phase, state.halt_reason = "review", ""
        added = state.sync_gates(sel.gates)
        print(f"📂 resuming {ctx.rel(ctx.state_path)}" + (f" (+ new gates: {', '.join(added)})" if added else ""))
        reopened = pipeline.reopen_changed(
            state, ctx.diff.tree,
            lambda old: diffscope.delta(PROJECT_ROOT, old, ctx.diff.tree, ctx.excludes, profile.components(ctx.tree)),
            lambda scope: select_gates(ctx.tree, scope).gates,
        )
        for name, reason in reopened:
            print(f"   ↺  {name} re-opened — {reason}")
    else:
        state = RunState(task_id=ctx.task_id, base_rule=sel.base_rule, add_rules=sel.add_rules,
                         gates=[GateState(name=g) for g in sel.gates])
    return state


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_classify(ctx: Context) -> int:
    sel = ctx.selection
    print("📊 Scope\n" + scope_summary(ctx))
    print(f"\n🎯 Base rule: {sel.base_rule}")
    print(f"➕ Add rules: {', '.join(sel.add_rules) or '(none)'}")
    print(f"🧪 Gate 0: {', '.join(c.name for c in checks.resolve(ctx.tree, ctx.diff.scope.components)) or '(none configured)'}")
    print(f"🧩 Stages ({len(sel.gates)} gates): {stages_text(sel.stages)}")
    return EXIT_READY


def cmd_checks(ctx: Context) -> int:
    state = ctx.load_state()
    code = run_checks(ctx, state, force=True)
    if code is None and state.phase == "checks_failed":
        state.phase, state.halt_reason = "review", ""
    state.save(ctx.state_path)
    return EXIT_READY if code is None else code


def cmd_run(ctx: Context) -> int:
    state = _prepare_state(ctx)
    engine_name = ctx.engine()[0]
    print(f"🚀 {ctx.task_id}: {stages_text(plan_stages(ctx.tree.get('routing') or {}, [g.name for g in state.gates]))}"
          f" (engine: {engine_name})")
    if not ctx.args.skip_checks and ctx.orch.get("run_checks", True):
        code = run_checks(ctx, state)
        if code is not None:
            state.save(ctx.state_path)
            write_summary(ctx, state)
            return code
    state.save(ctx.state_path)

    max_parallel = 1 if ctx.args.serial else int(ctx.orch.get("max_parallel", 3))
    for stage in plan_stages(ctx.tree.get("routing") or {}, [g.name for g in state.gates]):
        gates = [state.gate(name) for name in stage]
        pending = [g for g in gates if g.status != "passed"]
        for g in gates:
            if g.status == "passed":
                print(f"   ✅ {g.name}: already passed")
        if not pending:
            continue
        print(f"   ▶  {' ‖ '.join(g.name for g in pending)} …", flush=True)
        results = pipeline.run_stage(pending, lambda g: _execute_gate(ctx, g), max_parallel)
        stop = pipeline.most_severe([_record(ctx, state, g, r) for g, r in results])
        state.save(ctx.state_path)
        if stop is not None:
            if stop == EXIT_PAUSED:
                print("   ⏸  fix the findings in the reports above, then re-run (changed areas re-open their gates)")
            write_summary(ctx, state)
            return stop

    state.phase = "ready_for_human"
    state.save(ctx.state_path)
    write_summary(ctx, state)
    print(f"\n🏁 all gates passed. Next (HUMAN): {ctx.tree.get('human_gate')}")
    print(f"   summary: {ctx.rel(ctx.artifacts / '_summary.md')}")
    return EXIT_READY


def cmd_run_gate(ctx: Context) -> int:
    state = ctx.load_state()
    gate = state.gate(ctx.args.role) or GateState(name=ctx.args.role)
    if state.gate(gate.name) is None:
        state.gates.append(gate)
    result = _execute_gate(ctx, gate)
    stop = _record(ctx, state, gate, result)
    state.save(ctx.state_path)
    print(f"   report: {ctx.rel(result.artifact_path)}")
    return EXIT_READY if stop is None else stop


def cmd_status(ctx: Context) -> int:
    if not ctx.state_path.exists():
        print(f"no state yet at {ctx.rel(ctx.state_path)}")
        return EXIT_PAUSED
    state = RunState.from_path(ctx.state_path)
    print(f"📂 {ctx.rel(ctx.state_path)}\n   phase: {state.phase}{(' — ' + state.halt_reason) if state.halt_reason else ''}")
    print(f"   gate 0: {'green on ' + state.checks_green_tree[:12] if state.checks_green_tree else 'not green yet'}")
    for g in state.gates:
        print(f"   {ICONS.get(g.status, '·')} {g.name:18s} attempts={g.attempts} last={g.last_verdict or '-'}"
              f"{'  ' + g.note if g.note else ''}")
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
        p.add_argument("--dry-run", action="store_true", help="no AI calls and no checks; synthetic APPROVE verdicts")

    for name, helptext in (("classify", "show scope, Gate 0 checks and routed stages"),
                           ("checks", "run Gate 0 (project checks) only"),
                           ("run", "Gate 0, then pending gates stage by stage"), ("status", "show state")):
        p = sub.add_parser(name, help=helptext)
        common(p)
        if name == "run":
            p.add_argument("--fresh", action="store_true", help="discard existing state and start over")
            p.add_argument("--skip-checks", action="store_true", help="skip Gate 0 (project checks)")
            p.add_argument("--serial", action="store_true", help="one gate at a time, even inside a stage")
    for name, helptext in (("run-gate", "run one named gate"), ("prompt", "print a role's full prompt")):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("role")
        common(p)
    return parser


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    dispatch = {"classify": cmd_classify, "checks": cmd_checks, "run": cmd_run, "run-gate": cmd_run_gate,
                "status": cmd_status, "prompt": cmd_prompt}
    try:
        return dispatch[args.cmd](Context(args))
    except (profile.ProfileError, RoutingError, RoleError, EngineError, diffscope.GitError,
            checks.ChecksError) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return EXIT_CONFIG


if __name__ == "__main__":
    raise SystemExit(main())
