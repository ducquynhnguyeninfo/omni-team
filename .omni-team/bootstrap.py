#!/usr/bin/env python3
"""
bootstrap.py — render templates with a chosen manifest and write
fully-resolved agent files into the target .claude/ directory structure.

Usage:
    python bootstrap.py                       # uses manifests/example.yaml
    python bootstrap.py --manifest <path>     # any manifest
    python bootstrap.py --target <dir>        # override .claude/ (parent)
    python bootstrap.py --dry-run             # print plan, don't write

The script renders:
  - Agent prompts: templates/*.md → .claude/agents/*.md
  - Settings:      templates/settings.json.jinja2 → .claude/settings.json
  - Commands:      templates/commands/*.md → .claude/commands/*.md

The script is idempotent — running it twice produces identical output.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

from lib import manifest as _manifest  # noqa: E402
from lib import render as _render      # noqa: E402

TEMPLATES_DIR = ROOT / "templates"
DEFAULT_MANIFEST = ROOT / "manifests" / "example.yaml"
DEFAULT_TARGET = PROJECT_ROOT / ".claude"  # parent, not agents/ subdir

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

COMMAND_NAMES = [
    "test-backend",
    "test-frontend",
    "migrate-new",
    "migrate-current",
    "stack-up",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--dry-run", action="store_true")
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

    # Create directory structure
    agents_dir = args.target / "agents"
    commands_dir = args.target / "commands"

    if not args.dry_run:
        agents_dir.mkdir(parents=True, exist_ok=True)
        commands_dir.mkdir(parents=True, exist_ok=True)

    all_missing: dict[str, list[str]] = {}
    rendered_count = 0

    # =========================================================================
    # 1. Render agent prompts
    # =========================================================================
    for agent in AGENT_NAMES:
        tpl_path = TEMPLATES_DIR / f"{agent}.md"
        if not tpl_path.exists():
            print(f"   ⚠️  agent template missing: {tpl_path.name} (skipping)")
            continue

        tpl_text = tpl_path.read_text(encoding="utf-8")
        rendered, missing = _render.render(tpl_text, tree)

        if missing:
            all_missing[agent] = missing

        out_path = agents_dir / f"{agent}.md"
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

    # =========================================================================
    # 2. Render settings.json
    # =========================================================================
    settings_tpl_path = TEMPLATES_DIR / "settings.json.jinja2"
    if settings_tpl_path.exists():
        tpl_text = settings_tpl_path.read_text(encoding="utf-8")
        rendered, missing = _render.render(tpl_text, tree)

        if missing:
            all_missing["settings.json"] = missing

        out_path = args.target / "settings.json"
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

    # =========================================================================
    # 3. Render commands
    # =========================================================================
    commands_tpl_dir = TEMPLATES_DIR / "commands"
    if commands_tpl_dir.exists():
        for cmd_file in sorted(commands_tpl_dir.glob("*.md")):
            cmd_name = cmd_file.stem

            tpl_text = cmd_file.read_text(encoding="utf-8")
            rendered, missing = _render.render(tpl_text, tree)

            if missing:
                all_missing[f"command:{cmd_name}"] = missing

            out_path = commands_dir / cmd_file.name
            if args.dry_run:
                print(
                    f"   [DRY] would write {out_path}  ({len(rendered):,} bytes)"
                )
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
        for name, keys in all_missing.items():
            print(f"   • {name}: {', '.join(keys)}")
        print()
        print("   Add these keys to your manifest, or set them to `(none)`.")

    print(f"🏁 Rendered {rendered_count} file(s):")
    print(f"   • {len(AGENT_NAMES)} agents in .claude/agents/")
    print(f"   • 1 settings file at .claude/settings.json")
    if commands_tpl_dir.exists():
        cmd_count = len(list(commands_tpl_dir.glob("*.md")))
        print(f"   • {cmd_count} commands in .claude/commands/")

    return 0 if not all_missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
