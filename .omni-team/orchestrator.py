#!/usr/bin/env python3
"""
orchestrator.py — auto-run the omni-team gate pipeline for one work unit.

Usage:
    # Full pipeline against the diff since `main`:
    python orchestrator.py run --mp MP-A06 --sprint 4

    # Classify only (no invocations):
    python orchestrator.py classify --mp MP-A06 --base main

    # Re-run a single gate:
    python orchestrator.py run-gate backend-reviewer --mp MP-A06 --sprint 4

    # Dry-run (no Claude calls; synthetic verdicts):
    python orchestrator.py run --mp MP-A06 --sprint 4 --dry-run

State file:
    Per the manifest's `orchestrator.state_file_pattern`.
    Default: document/sprints/{sprint}/agent-pow/{mp_id}/_state.json

Stops at the human gate (default: "Codex crosscheck") — orchestrator never
auto-commits, never auto-pushes, never runs the final reviewer.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT
sys.path.insert(0, str(ROOT))

from lib import manifest as _manifest        # noqa: E402
from lib.decision import Scope, select_agents  # noqa: E402
from lib.runner import invoke                  # noqa: E402
from lib.state import GateState, RunState      # noqa: E402

DEFAULT_MANIFEST = ROOT / "manifests" / "example.yaml"
ROUTE_DECORATOR_RE = re.compile(r"@(?:app|router)\.(?:get|post|put|patch|delete)\(")


# ---------------------------------------------------------------------------
# Scope classification
# ---------------------------------------------------------------------------

def _git(args: list[str], cwd: Path) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout


def _detect_stack(path: str, manifest: dict) -> str | None:
    be_root = manifest["backend"].get("root", "")
    fe_root = manifest["frontend"].get("root", "")
    db_versions = manifest["database"]["migrations"].get("versions_dir", "")
    if db_versions and path.startswith(db_versions):
        return "database"
    if be_root and (path.startswith(be_root + "/") or path == be_root):
        return "backend"
    if fe_root and (path.startswith(fe_root + "/") or path == fe_root):
        return "frontend"
    return None


def compute_scope(manifest: dict, base_ref: str) -> Scope:
    diff_files = _git(
        ["diff", "--name-only", f"{base_ref}...HEAD"], PROJECT_ROOT
    ).splitlines()
    diff_text = _git(["diff", f"{base_ref}...HEAD"], PROJECT_ROOT)
    loc = sum(1 for ln in diff_text.splitlines() if ln.startswith("+") and not ln.startswith("+++"))

    scope = Scope(loc=loc, diff_text=diff_text, changed_paths=diff_files)

    for p in diff_files:
        stk = _detect_stack(p, manifest)
        if stk:
            scope.stacks.add(stk)

    # new_route: any added @router.<verb> in BE diff
    if ROUTE_DECORATOR_RE.search(diff_text):
        # only count if it is an addition line
        for ln in diff_text.splitlines():
            if ln.startswith("+") and not ln.startswith("+++") and ROUTE_DECORATOR_RE.search(ln):
                scope.new_route = True
                break

    # schema_change: any new file in migrations versions_dir
    db_versions = manifest["database"]["migrations"].get("versions_dir", "")
    if db_versions and any(p.startswith(db_versions) for p in diff_files):
        scope.schema_change = True

    # pii_fields_touched: scan diff for PII keywords
    pii_csv = manifest.get("security", {}).get("pii_fields_csv", "")
    for piif in [p.strip() for p in pii_csv.split(",") if p.strip()]:
        if piif.lower() in diff_text.lower():
            scope.pii_fields_touched.add(piif)

    return scope


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _state_path(manifest: dict, mp_id: str, sprint: str) -> Path:
    pattern: str = manifest["orchestrator"]["state_file_pattern"]
    return PROJECT_ROOT / pattern.format(mp_id=mp_id, sprint=sprint)


def _artifact_path(manifest: dict, mp_id: str, sprint: str, agent: str) -> Path:
    pattern: str = manifest["artifact_dir"]
    base = PROJECT_ROOT / pattern.format(mp_id=mp_id, sprint=sprint)
    return base / f"{agent}.md"


def _post_ship_path(manifest: dict, mp_id: str, sprint: str) -> Path:
    pattern: str = manifest["artifact_dir"]
    base = PROJECT_ROOT / pattern.format(mp_id=mp_id, sprint=sprint)
    return base / "_post-ship-escapes.md"


def _scope_summary(scope: Scope, mp_id: str, sprint: str, manifest: dict) -> str:
    spec_root = manifest.get("spec_root", "")
    return (
        f"- {manifest['work_unit_label']} id: {mp_id}\n"
        f"- sprint: {sprint}\n"
        f"- spec root: {spec_root}\n"
        f"- LoC changed: {scope.loc}\n"
        f"- stacks touched: {', '.join(sorted(scope.stacks)) or '(none)'}\n"
        f"- new route added: {scope.new_route}\n"
        f"- schema change: {scope.schema_change}\n"
        f"- PII fields touched: {', '.join(sorted(scope.pii_fields_touched)) or '(none)'}\n"
        f"- changed files (first 30):\n"
        + "\n".join(f"    - {p}" for p in scope.changed_paths[:30])
    )


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_classify(args: argparse.Namespace, manifest: dict) -> int:
    scope = compute_scope(manifest, args.base)
    agents, base_rule = select_agents(manifest, scope)
    print(f"📊 Scope")
    print(_scope_summary(scope, args.mp, args.sprint or "?", manifest))
    print()
    print(f"🎯 Matched base rule: {base_rule}")
    print(f"🧩 Gates to run ({len(agents)}):")
    for a in agents:
        print(f"   • {a}")
    return 0


def cmd_run(args: argparse.Namespace, manifest: dict) -> int:
    scope = compute_scope(manifest, args.base)
    agents, base_rule = select_agents(manifest, scope)

    state_path = _state_path(manifest, args.mp, args.sprint)
    if state_path.exists() and not args.fresh:
        state = RunState.from_path(state_path)
        print(f"📂 Resuming state: {state_path.relative_to(PROJECT_ROOT)}")
    else:
        state = RunState(
            mp_id=args.mp,
            phase="review",
            base_rule=base_rule,
            gates=[GateState(name=a) for a in agents],
        )

    state.save(state_path)
    print(f"🚀 Running {len(agents)} gate(s) for {args.mp} (rule: {base_rule})")

    budget_block = manifest["orchestrator"]["retry_budget"]["block_max"]
    budget_rc = manifest["orchestrator"]["retry_budget"]["request_changes_max"]
    claude_cmd = manifest["orchestrator"]["claude_cmd"]
    scope_summary = _scope_summary(scope, args.mp, args.sprint, manifest)

    for gate in state.gates:
        if gate.status == "passed":
            print(f"   ✅ {gate.name} already passed; skipping")
            continue

        artifact_path = _artifact_path(manifest, args.mp, args.sprint, gate.name)
        print(f"\n--- {gate.name} (attempt {gate.retry_count + 1}) ---")

        result = invoke(
            agent=gate.name,
            scope_summary=scope_summary,
            project_root=PROJECT_ROOT,
            artifact_path=artifact_path,
            claude_cmd=claude_cmd,
            timeout_s=args.timeout,
            dry_run=args.dry_run,
        )
        gate.last_verdict = result.verdict
        gate.last_run_at = dt.datetime.now().isoformat()

        if result.verdict in {"APPROVE", "NOT_APPLICABLE"}:
            gate.status = "passed"
            print(f"   ✅ {gate.name}: {result.verdict}")
        elif result.verdict == "REQUEST_CHANGES":
            gate.retry_count += 1
            gate.status = "request_changes"
            print(f"   ✋ {gate.name}: REQUEST_CHANGES (retries used {gate.retry_count}/{budget_rc})")
            if gate.retry_count >= budget_rc:
                state.halted = True
                state.halt_reason = f"{gate.name} exceeded REQUEST_CHANGES budget"
                _escape(manifest, args, state, gate, "request_changes-budget")
                state.save(state_path)
                return 3
            state.save(state_path)
            print(f"   ⏸  Pausing pipeline so engineer can address findings.")
            print(f"   ▶  Re-run when fixes are in: orchestrator.py run --mp {args.mp} --sprint {args.sprint}")
            return 0
        elif result.verdict in {"BLOCK", "BLOCKED"}:
            gate.retry_count += 1
            gate.status = "block"
            print(f"   ⛔ {gate.name}: BLOCK (retries used {gate.retry_count}/{budget_block})")
            if gate.retry_count >= budget_block:
                state.halted = True
                state.halt_reason = f"{gate.name} blocked {budget_block} times"
                _escape(manifest, args, state, gate, "block-budget")
                state.save(state_path)
                return 4
            state.save(state_path)
            print(f"   ⏸  Pausing. Address the BLOCK and re-run.")
            return 0
        else:
            gate.status = "error"
            state.halted = True
            state.halt_reason = f"{gate.name} returned UNKNOWN verdict"
            state.save(state_path)
            print(f"   ❓ {gate.name}: UNKNOWN — see {artifact_path}")
            return 5

        state.save(state_path)

    state.phase = "ready_for_human"
    state.save(state_path)
    print()
    print(f"🏁 All gates passed.")
    print(f"   Next step (HUMAN): {manifest['orchestrator']['final_human_gate']}")
    print(f"   State: {state_path.relative_to(PROJECT_ROOT)}")
    return 0


def cmd_run_gate(args: argparse.Namespace, manifest: dict) -> int:
    scope = compute_scope(manifest, args.base)
    scope_summary = _scope_summary(scope, args.mp, args.sprint, manifest)
    artifact_path = _artifact_path(manifest, args.mp, args.sprint, args.agent)
    result = invoke(
        agent=args.agent,
        scope_summary=scope_summary,
        project_root=PROJECT_ROOT,
        artifact_path=artifact_path,
        claude_cmd=manifest["orchestrator"]["claude_cmd"],
        timeout_s=args.timeout,
        dry_run=args.dry_run,
    )
    print(f"{args.agent}: {result.verdict}  ({result.duration_s:.1f}s)")
    print(f"artifact: {artifact_path.relative_to(PROJECT_ROOT)}")
    return 0 if result.verdict in {"APPROVE", "NOT_APPLICABLE"} else 1


def cmd_status(args: argparse.Namespace, manifest: dict) -> int:
    state_path = _state_path(manifest, args.mp, args.sprint)
    if not state_path.exists():
        print(f"no state file at {state_path}")
        return 1
    state = RunState.from_path(state_path)
    print(f"📂 {state_path.relative_to(PROJECT_ROOT)}")
    print(f"   phase: {state.phase}")
    print(f"   base rule: {state.base_rule}")
    print(f"   halted: {state.halted}{(' — ' + state.halt_reason) if state.halted else ''}")
    print()
    for g in state.gates:
        icon = {"passed": "✅", "block": "⛔", "request_changes": "✋", "pending": "·", "error": "❓"}.get(g.status, "?")
        print(f"   {icon} {g.name:20s} retries={g.retry_count}  last={g.last_verdict or '-'}")
    return 0


def _escape(
    manifest: dict,
    args: argparse.Namespace,
    state: RunState,
    gate: GateState,
    reason: str,
) -> None:
    path = _post_ship_path(manifest, args.mp, args.sprint)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = (
        f"\n\n---\n\n"
        f"## Escape: {dt.datetime.now().isoformat()}\n"
        f"- agent: `{gate.name}`\n"
        f"- reason: **{reason}**\n"
        f"- last verdict: {gate.last_verdict}\n"
        f"- retries: {gate.retry_count}\n"
        f"- halt_reason: {state.halt_reason}\n"
    )
    with path.open("a", encoding="utf-8") as fh:
        fh.write(entry)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    p.add_argument("--mp", required=True, help="Work unit id (e.g. MP-A06)")
    p.add_argument("--sprint", default="", help="Sprint number / label")
    p.add_argument("--base", default="origin/main", help="Git base ref for diff")
    p.add_argument("--timeout", type=int, default=1800)
    p.add_argument("--dry-run", action="store_true")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_class = sub.add_parser("classify", help="Print scope and gate plan; do not invoke.")
    _add_common(p_class)

    p_run = sub.add_parser("run", help="Run the full pipeline.")
    _add_common(p_run)
    p_run.add_argument("--fresh", action="store_true", help="Ignore existing state file")

    p_gate = sub.add_parser("run-gate", help="Re-run a single named gate.")
    _add_common(p_gate)
    p_gate.add_argument("agent")

    p_status = sub.add_parser("status", help="Show the state of the current run.")
    p_status.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    p_status.add_argument("--mp", required=True)
    p_status.add_argument("--sprint", default="")

    args = parser.parse_args()

    try:
        manifest = _manifest.load(args.manifest)
    except _manifest.ManifestError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2

    dispatch = {
        "classify": cmd_classify,
        "run": cmd_run,
        "run-gate": cmd_run_gate,
        "status": cmd_status,
    }
    return dispatch[args.cmd](args, manifest)


if __name__ == "__main__":
    raise SystemExit(main())
