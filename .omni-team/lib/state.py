"""
Orchestrator state file — `<artifacts_dir>/_state.json` per task.

JSON keeps it machine-readable, diff-friendly and easy to inspect.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional

# pending | passed | request_changes | block | needs_human | error  (see GATE_STATUSES)
GATE_STATUSES = ("pending", "passed", "request_changes", "block", "needs_human", "error")


@dataclass
class GateState:
    name: str
    status: str = "pending"
    attempts: int = 0
    request_changes_count: int = 0
    block_count: int = 0
    last_verdict: str = ""
    last_run_at: str = ""
    approved_tree: str = ""        # snapshot the gate approved; a later change can re-open the gate
    note: str = ""


@dataclass
class RunState:
    task_id: str
    phase: str = "review"          # checks_failed | review | ready_for_human | halted
    base_rule: str = ""
    add_rules: List[str] = field(default_factory=list)
    gates: List[GateState] = field(default_factory=list)
    halt_reason: str = ""
    checks_green_tree: str = ""    # last snapshot on which Gate 0 (project checks) passed

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    @classmethod
    def from_path(cls, path: Path) -> "RunState":
        raw = json.loads(path.read_text(encoding="utf-8"))
        gates = [GateState(**g) for g in raw.pop("gates", [])]
        return cls(gates=gates, **raw)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json() + "\n", encoding="utf-8")

    def gate(self, name: str) -> Optional[GateState]:
        return next((g for g in self.gates if g.name == name), None)

    def sync_gates(self, selected: List[str]) -> List[str]:
        """Add newly-routed gates (a fix may touch new areas); keep history of existing ones."""
        added = [name for name in selected if self.gate(name) is None]
        self.gates.extend(GateState(name=n) for n in added)
        order = {name: i for i, name in enumerate(selected)}
        self.gates.sort(key=lambda g: order.get(g.name, len(order)))
        return added
