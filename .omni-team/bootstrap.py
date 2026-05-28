#!/usr/bin/env python3
"""
bootstrap.py — render templates/*.md with a chosen manifest and
write fully-resolved agent files into the target .claude/agents/ directory.

Usage:
    python bootstrap.py                       # uses manifests/example.yaml
    python bootstrap.py --manifest <path>     # any manifest
    python bootstrap.py --target <dir>        # override .claude/agents/
    python bootstrap.py --dry-run             # print plan, don't write

The script is idempotent — running it twice produces identical output. To
remove an agent from the rendered set, delete it from .claude/agents/ AND set
its template aside (not deleting from templates/, which is the master copy).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT
sys.path.insert(0, str(ROOT))

from lib import manifest as _manifest  # noqa: E402
from lib import render as _render      # noqa: E402

TEMPLATES_DIR = ROOT / "templates"
DEFAULT_MANIFEST = ROOT / "manifests" / "example.yaml"
DEFAULT_TARGET = PROJECT_ROOT / ".claude" / "agents"

AGENT_NAMES = [
    "tech-lead",
    "backend-reviewer",
    "frontend-reviewer",
    "dba",
    "qa-engineer",
    "qa-lead",
    "perf-engineer",
    "security-engineer",
    "ui-smoke-engineer",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--only",
        nargs="*",
        choices=AGENT_NAMES,
        help="Only render these agents (default: all)",
    )
    args = parser.parse_args()

    print(f"📋 manifest: {args.manifest}")
    print(f"🎯 target:   {args.target}")
    print()

    try:
        tree = _manifest.load(args.manifest)
    except _manifest.ManifestError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2

    project_name = tree.get("project", {}).get("name", "<unnamed>")
    print(f"   project: {project_name}")
    print()

    if not args.dry_run:
        args.target.mkdir(parents=True, exist_ok=True)

    selected = args.only or AGENT_NAMES
    all_missing: dict[str, list[str]] = {}
    rendered_count = 0

    for agent in selected:
        tpl_path = TEMPLATES_DIR / f"{agent}.md"
        if not tpl_path.exists():
            print(f"   ⚠️  template missing: {tpl_path.name} (skipping)")
            continue

        tpl_text = tpl_path.read_text(encoding="utf-8")
        rendered, missing = _render.render(tpl_text, tree)

        if missing:
            all_missing[agent] = missing

        out_path = args.target / f"{agent}.md"
        if args.dry_run:
            print(f"   [DRY] would write {out_path}  ({len(rendered):,} bytes)")
        else:
            out_path.write_text(rendered, encoding="utf-8")
            try:
                display = out_path.relative_to(PROJECT_ROOT)
            except ValueError:
                display = out_path
            print(f"   ✅ wrote {display}")
        rendered_count += 1

    print()
    if all_missing:
        print("⚠️  Unresolved placeholders (left in output as-is):")
        for agent, keys in all_missing.items():
            print(f"   • {agent}.md: {', '.join(keys)}")
        print()
        print("   Add these keys to your manifest, or set them to `(none)`.")

    print(f"🏁 Rendered {rendered_count} agent file(s).")
    return 0 if not all_missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
