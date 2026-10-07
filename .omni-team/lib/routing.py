"""
Routing evaluator — picks review gates for a change scope.

All routing knowledge (signals, rules, order) is DATA in defaults.yaml /
project/profile.yaml. This module only evaluates predicates; it must never
embed stack- or project-specific patterns (docs/critical-rules.md §2).
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Set


class RoutingError(Exception):
    pass


@dataclass
class Scope:
    changed_paths: List[str] = field(default_factory=list)
    added_lines: List[str] = field(default_factory=list)
    removed_lines: List[str] = field(default_factory=list)
    components: Set[str] = field(default_factory=set)  # touched component names AND kinds

    @property
    def loc(self) -> int:
        return len(self.added_lines)

    @property
    def changed_text_lower(self) -> str:
        return "\n".join(self.added_lines + self.removed_lines).lower()


@dataclass
class Selection:
    gates: List[str]                 # flattened execution order
    base_rule: str
    add_rules: List[str]
    signals: Dict[str, bool]
    stages: List[List[str]] = field(default_factory=list)  # gates in one stage may run concurrently


def glob_match(path: str, pattern: str) -> bool:
    """fnmatch where a leading `**/` also matches at the repo root."""
    if fnmatch.fnmatchcase(path, pattern):
        return True
    return pattern.startswith("**/") and fnmatch.fnmatchcase(path, pattern[3:])


def _any_path(scope: Scope, globs: List[str]) -> bool:
    return any(glob_match(p, g) for p in scope.changed_paths for g in globs)


def _only_paths(scope: Scope, globs: List[str]) -> bool:
    return bool(scope.changed_paths) and all(
        any(glob_match(p, g) for g in globs) for p in scope.changed_paths
    )


def _added_lines(scope: Scope, patterns: List[str]) -> bool:
    try:
        compiled = [re.compile(p) for p in patterns]
    except re.error as exc:
        raise RoutingError(f"invalid added_lines regex: {exc}") from exc
    return any(rx.search(line) for rx in compiled for line in scope.added_lines)


def _keywords(scope: Scope, words: List[str]) -> bool:
    text = scope.changed_text_lower
    return any(w.lower() in text for w in words)


PREDICATES: Dict[str, Callable[[Scope, Any], bool]] = {
    "loc_min": lambda s, v: s.loc >= int(v),
    "loc_max": lambda s, v: s.loc <= int(v),
    "files_min": lambda s, v: len(s.changed_paths) >= int(v),
    "files_max": lambda s, v: len(s.changed_paths) <= int(v),
    "paths": _any_path,
    "only_paths": _only_paths,
    "added_lines": _added_lines,
    "keywords": _keywords,
    "components": lambda s, v: set(v).issubset(s.components),
    "any_component": lambda s, v: bool(set(v) & s.components),
}


def match_when(when: Dict[str, Any], scope: Scope, signals: Dict[str, bool]) -> bool:
    """A rule matches when ALL of its predicates match. `{}` always matches."""
    for key, value in (when or {}).items():
        if key == "signals":
            unknown = [n for n in value if n not in signals]
            if unknown:
                raise RoutingError(f"rule references undefined signal(s): {unknown}")
            if not all(signals[n] for n in value):
                return False
            continue
        if key not in PREDICATES:
            raise RoutingError(f"unknown predicate '{key}' (known: {sorted(PREDICATES)} + signals)")
        if not PREDICATES[key](scope, value):
            return False
    return True


def evaluate_signals(defs: Dict[str, Any], scope: Scope) -> Dict[str, bool]:
    """A signal is a predicate mapping (AND) or a list of mappings (OR of ANDs)."""
    results: Dict[str, bool] = {}
    for name, spec in (defs or {}).items():
        alternatives = spec if isinstance(spec, list) else [spec]
        for alt in alternatives:
            if not isinstance(alt, dict) or "signals" in alt:
                raise RoutingError(f"signal '{name}': each entry must be a predicate mapping without `signals`")
        results[name] = any(match_when(alt, scope, {}) for alt in alternatives)
    return results


def stage_layout(routing: Dict[str, Any]) -> List[List[str]]:
    """`stages` (list of gate groups) or legacy `order` (one gate per stage) — never both."""
    if routing.get("stages") and routing.get("order"):
        raise RoutingError("routing: use either `stages` or `order`, not both")
    raw = routing.get("stages") or [[g] for g in routing.get("order", [])]
    return [[s] if isinstance(s, str) else list(s) for s in raw]


def plan_stages(routing: Dict[str, Any], gates: List[str]) -> List[List[str]]:
    """Group selected gates by stage; gates missing from the layout run alone, last, in selection order."""
    wanted = list(dict.fromkeys(gates))
    seen: set = set()
    stages: List[List[str]] = []
    for layout_stage in stage_layout(routing):
        picked = [g for g in layout_stage if g in wanted and g not in seen]
        seen.update(picked)
        if picked:
            stages.append(picked)
    return stages + [[g] for g in wanted if g not in seen]


def select_gates(tree: Dict[str, Any], scope: Scope) -> Selection:
    routing = tree.get("routing") or {}
    signals = evaluate_signals(tree.get("signals") or {}, scope)

    gates: List[str] = []
    base_rule, final = "no-match", False
    for rule in routing.get("base", []):
        if match_when(rule.get("when", {}), scope, signals):
            gates = list(rule.get("agents", []))
            base_rule = rule.get("name", "<unnamed>")
            final = bool(rule.get("final", False))
            break

    add_rules: List[str] = []
    if not final:
        for rule in routing.get("add_if", []):
            if match_when(rule.get("when", {}), scope, signals):
                add_rules.append(rule.get("name", "<unnamed>"))
                gates.extend(rule.get("agents_add", []))

    stages = plan_stages(routing, gates)
    return Selection([g for s in stages for g in s], base_rule, add_rules, signals, stages)
