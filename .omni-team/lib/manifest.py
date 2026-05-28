"""
Manifest loader + flat-key lookup.

A manifest is a YAML tree. Templates use {{path.to.key}}; the renderer walks
this tree and substitutes. Missing keys raise so they cannot silently render as
empty strings.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print(
        "PyYAML is required. Install with: pip install pyyaml",
        file=sys.stderr,
    )
    raise


class ManifestError(Exception):
    pass


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ManifestError(f"Manifest not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ManifestError(f"Manifest root must be a mapping: {path}")
    return data


def lookup(tree: dict[str, Any], dotted: str) -> Any:
    """Resolve `a.b.c` against the manifest tree. Raise on missing key."""
    node: Any = tree
    parts = dotted.split(".")
    for i, key in enumerate(parts):
        if not isinstance(node, dict):
            raise ManifestError(
                f"Cannot descend into non-mapping at '{'.'.join(parts[:i])}' "
                f"while resolving '{dotted}'"
            )
        if key not in node:
            raise ManifestError(f"Missing manifest key: {dotted}")
        node = node[key]
    return node


def has(tree: dict[str, Any], dotted: str) -> bool:
    try:
        lookup(tree, dotted)
        return True
    except ManifestError:
        return False
