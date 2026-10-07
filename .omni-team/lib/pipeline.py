"""
Pipeline mechanics shared by the orchestrator commands: verdict → gate state,
retry budget, re-opening approvals that a later change invalidated, and
running the gates of one stage concurrently.

Kept free of CLI concerns so every rule here is unit-testable.
"""

from __future__ import annotations

import datetime as dt
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple, TypeVar

from .routing import Scope
from .state import GateState, RunState

EXIT_READY, EXIT_PAUSED, EXIT_CONFIG = 0, 1, 2
EXIT_RC_BUDGET, EXIT_BLOCK_BUDGET, EXIT_UNKNOWN, EXIT_HUMAN, EXIT_CHECKS = 3, 4, 5, 6, 7
# When several gates of one stage stop the run, report the most serious reason.
SEVERITY = (EXIT_BLOCK_BUDGET, EXIT_RC_BUDGET, EXIT_HUMAN, EXIT_UNKNOWN, EXIT_PAUSED)
PASSING = {"APPROVE", "NOT_APPLICABLE", "PLAN_READY"}

T = TypeVar("T")


@dataclass
class Budget:
    request_changes_max: int = 3
    block_max: int = 3


def _halt(state: RunState, reason: str) -> None:
    state.phase = "halted"
    state.halt_reason = "; ".join(r for r in (state.halt_reason, reason) if r)


def record(state: RunState, gate: GateState, verdict: str, tree: str, budget: Budget) -> Tuple[Optional[int], str]:
    """Apply one verdict. Returns (exit code to stop with or None, escape reason or "")."""
    gate.attempts += 1
    gate.last_verdict = verdict
    gate.last_run_at = dt.datetime.now().isoformat(timespec="seconds")
    if verdict in PASSING:
        gate.status, gate.approved_tree, gate.note = "passed", tree, ""
        return None, ""
    if verdict in ("REQUEST_CHANGES", "BLOCK"):
        is_rc = verdict == "REQUEST_CHANGES"
        gate.status = "request_changes" if is_rc else "block"
        if is_rc:
            gate.request_changes_count += 1
        else:
            gate.block_count += 1
        used = gate.request_changes_count if is_rc else gate.block_count
        limit = budget.request_changes_max if is_rc else budget.block_max
        if used >= limit:
            _halt(state, f"{gate.name}: {verdict} budget ({limit}) exhausted")
            return (EXIT_RC_BUDGET if is_rc else EXIT_BLOCK_BUDGET), f"{verdict.lower()} budget exhausted"
        return EXIT_PAUSED, ""
    gate.status = "needs_human" if verdict in ("NEEDS_CLARIFICATION", "BLOCKED") else "error"
    _halt(state, f"{gate.name}: {verdict}")
    return (EXIT_HUMAN if gate.status == "needs_human" else EXIT_UNKNOWN), ""


def most_severe(codes: Sequence[Optional[int]]) -> Optional[int]:
    present = {c for c in codes if c is not None}
    return next((c for c in SEVERITY if c in present), None)


def reopen_changed(
    state: RunState,
    current_tree: str,
    delta_for: Callable[[str], Optional[Scope]],
    gates_for: Callable[[Scope], List[str]],
) -> List[Tuple[str, str]]:
    """Re-open passed gates whose area changed since they approved.

    The rule is the routing itself: a gate is re-opened when the change made *since its
    approval* would, on its own, route that gate. Small, unrelated fixes therefore do not
    re-trigger every reviewer, while e.g. a fix that touches a migration re-opens
    data-reviewer. Deltas are measured from the original approval, so many small edits
    still add up. Returns [(gate, reason)].
    """
    reopened = []
    for gate in state.gates:
        if gate.status != "passed" or gate.approved_tree == current_tree:
            continue
        scope = delta_for(gate.approved_tree) if gate.approved_tree else None
        if scope is None:
            reason = "approval snapshot unknown"
        elif not scope.changed_paths:
            continue
        elif gate.name in gates_for(scope):
            reason = f"changed since approval: {len(scope.changed_paths)} file(s), +{scope.loc} lines"
        else:
            continue
        gate.status, gate.note = "pending", f"re-opened — {reason}"
        reopened.append((gate.name, reason))
    return reopened


def run_stage(gates: List[GateState], execute: Callable[[GateState], T], max_parallel: int) -> List[Tuple[GateState, T]]:
    """Run the gates of ONE stage; concurrently when allowed. Results keep stage order."""
    if max_parallel <= 1 or len(gates) <= 1:
        return [(g, execute(g)) for g in gates]
    with ThreadPoolExecutor(max_workers=min(max_parallel, len(gates))) as pool:
        futures = [pool.submit(execute, g) for g in gates]
        return [(g, f.result()) for g, f in zip(gates, futures)]
