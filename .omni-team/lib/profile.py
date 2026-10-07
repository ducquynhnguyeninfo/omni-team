"""
Profile loader — framework defaults (defaults.yaml) merged with the host
project's overrides (project/profile.yaml).

Merge rules (documented in docs/profile.md):
  - top-level keys in the profile replace the defaults' keys,
  - except `signals` (merged by signal name), `quality_limits` and
    `orchestrator` (merged key by key, `engines` merged by engine name),
  - and `routing`, where order/base/add_if each replace the default when
    given and `extra_add_if` is appended to add_if.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from .roles import FRAMEWORK_ROOT

DEFAULTS_FILE = FRAMEWORK_ROOT / "defaults.yaml"
PROFILE_FILE = FRAMEWORK_ROOT / "project" / "profile.yaml"


class ProfileError(Exception):
    pass


def _yaml():
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise ProfileError(
            "PyYAML is required by orchestrator.py (install.py does not need it).\n"
            "  pip install -r .omni-team/requirements.txt"
        ) from exc
    return yaml


def read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ProfileError(f"file not found: {path}")
    yaml = _yaml()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ProfileError(f"{path}: invalid YAML — {exc}") from exc
    if not isinstance(data, dict):
        raise ProfileError(f"{path}: top level must be a mapping")
    return data


def _merge_orchestrator(base: Dict[str, Any], over: Dict[str, Any]) -> Dict[str, Any]:
    merged = {**base, **over}
    engines = dict(base.get("engines", {}))
    for name, spec in (over.get("engines") or {}).items():
        engines[name] = {**engines.get(name, {}), **spec}
    merged["engines"] = engines
    if "retry_budget" in over:
        merged["retry_budget"] = {**base.get("retry_budget", {}), **over["retry_budget"]}
    return merged


def _merge_routing(base: Dict[str, Any], over: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key in ("order", "base", "add_if"):
        if key in over:
            merged[key] = over[key]
    merged["add_if"] = list(merged.get("add_if", [])) + list(over.get("extra_add_if", []))
    unknown = set(over) - {"order", "base", "add_if", "extra_add_if"}
    if unknown:
        raise ProfileError(f"routing: unknown key(s) {sorted(unknown)}")
    return merged


def merge(defaults: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    merged = {**defaults, **profile}
    if "signals" in profile:
        merged["signals"] = {**defaults.get("signals", {}), **(profile["signals"] or {})}
    if "quality_limits" in profile:
        merged["quality_limits"] = {**defaults.get("quality_limits", {}), **profile["quality_limits"]}
    if "orchestrator" in profile:
        merged["orchestrator"] = _merge_orchestrator(
            defaults.get("orchestrator", {}), profile["orchestrator"] or {}
        )
    if "routing" in profile:
        merged["routing"] = _merge_routing(defaults.get("routing", {}), profile["routing"] or {})
    return merged


def load(profile_path: Optional[Path] = None, defaults_path: Path = DEFAULTS_FILE) -> Dict[str, Any]:
    defaults = read_yaml(defaults_path)
    path = profile_path or PROFILE_FILE
    profile = read_yaml(path) if path.exists() else {}
    return merge(defaults, profile)


def components(tree: Dict[str, Any]) -> list:
    comps = tree.get("components") or []
    if not isinstance(comps, list):
        raise ProfileError("components must be a list (use [] for auto-discovery)")
    for c in comps:
        if not isinstance(c, dict) or "name" not in c or "path" not in c:
            raise ProfileError(f"each component needs at least `name` and `path`: {c!r}")
    return comps
