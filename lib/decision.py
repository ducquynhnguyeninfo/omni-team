"""
Decision matrix evaluator — picks agents for a given change scope.

Inputs:
  - manifest's `decision_matrix` section
  - a Scope dict computed by orchestrator (loc, stacks touched, new_route, etc.)

Output:
  - ordered list of agent names to invoke
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Scope:
    loc: int = 0
    stacks: set[str] = field(default_factory=set)  # {"backend", "frontend", "database"}
    new_route: bool = False
    schema_change: bool = False
    changed_paths: list[str] = field(default_factory=list)
    diff_text: str = ""               # for keyword scanning

    pii_fields_touched: set[str] = field(default_factory=set)


def _match_rule(when: dict[str, Any], scope: Scope) -> bool:
    if "loc_max" in when and scope.loc > when["loc_max"]:
        return False
    if "loc_min" in when and scope.loc < when["loc_min"]:
        return False
    if "stacks" in when:
        required = set(when["stacks"])
        if not required.issubset(scope.stacks):
            return False
    if "new_route" in when and bool(when["new_route"]) != scope.new_route:
        return False
    if "schema_change" in when and bool(when["schema_change"]) != scope.schema_change:
        return False
    if "path_globs" in when:
        globs = when["path_globs"]
        if not any(
            fnmatch.fnmatch(p, g) for p in scope.changed_paths for g in globs
        ):
            return False
    if "keywords" in when:
        kws = [k.lower() for k in when["keywords"]]
        text = scope.diff_text.lower()
        if not any(k in text for k in kws):
            return False
    if "pii_fields" in when:
        if not (set(when["pii_fields"]) & scope.pii_fields_touched):
            return False
    return True


def select_agents(manifest: dict[str, Any], scope: Scope) -> list[str]:
    matrix = manifest["decision_matrix"]
    agents: list[str] = []

    # First matching base rule wins
    base_rule_name = None
    for rule in matrix.get("base", []):
        if _match_rule(rule.get("when", {}), scope):
            agents = list(rule.get("agents", []))
            base_rule_name = rule.get("name", "")
            break

    # All matching add_if rules append (preserving order, dedup)
    for rule in matrix.get("add_if", []):
        if _match_rule(rule.get("when", {}), scope):
            for a in rule.get("agents_add", []):
                if a not in agents:
                    agents.append(a)

    return agents, base_rule_name or "no-match"
