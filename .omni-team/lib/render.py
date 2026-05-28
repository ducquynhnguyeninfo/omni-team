"""
Template renderer.

Replaces {{dotted.key}} placeholders with values from the manifest.
Lists become comma-separated unless overridden by a *_csv key.
"""

from __future__ import annotations

import re
from typing import Any

from .manifest import ManifestError, lookup

_PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    if isinstance(value, dict):
        raise ManifestError(
            "Cannot render a mapping into a template placeholder; "
            "provide a *_md or *_csv string field instead."
        )
    return str(value)


def render(template_text: str, manifest: dict[str, Any]) -> tuple[str, list[str]]:
    """
    Substitute all {{key.path}} placeholders.

    Returns (rendered_text, missing_keys). Missing keys do NOT raise — they
    leave the placeholder in place AND are reported, so bootstrap can warn the
    user without corrupting the output.
    """
    missing: list[str] = []

    def _sub(match: re.Match[str]) -> str:
        key = match.group(1)
        try:
            value = lookup(manifest, key)
        except ManifestError:
            missing.append(key)
            return match.group(0)
        return _stringify(value)

    rendered = _PLACEHOLDER.sub(_sub, template_text)
    return rendered, sorted(set(missing))
