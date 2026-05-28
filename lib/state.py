"""
Orchestrator state file management.

State lives at {artifact_dir}/_state.json. JSON for machine-readable, gentle
on diffs, and easy to inspect.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class GateState:
    name: str
    status: str = "pending"        # pending | passed | request_changes | block | error
    retry_count: int = 0
    last_verdict: str = ""
    last_run_at: str = ""


@dataclass
class RunState:
    mp_id: str
    phase: str = "classify"        # classify | plan | execute | review | ready_for_human
    base_rule: str = ""
    gates: list[GateState] = field(default_factory=list)
    halted: bool = False
    halt_reason: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    @classmethod
    def from_path(cls, path: Path) -> "RunState":
        with path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
        gates = [GateState(**g) for g in raw.pop("gates", [])]
        return cls(gates=gates, **raw)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")

    def gate(self, name: str) -> GateState | None:
        for g in self.gates:
            if g.name == name:
                return g
        return None
