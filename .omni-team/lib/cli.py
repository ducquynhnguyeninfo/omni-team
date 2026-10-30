"""Command-line parser of orchestrator.py (kept here so the orchestrator stays within its size limit)."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from . import activity


def since_arg(value: str) -> str:
    try:
        return activity.since_date(value, dt.date.today())
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, today, yesterday or <n>d, got '{value}'") from None


def build_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    def common(p: argparse.ArgumentParser, task_required: bool = True) -> None:
        p.add_argument("--task", required=task_required, help="work-unit id, e.g. TASK-12 (used for the artifacts folder)")
        p.add_argument("--profile", type=Path, help="profile path (default: .omni-team/project/profile.yaml)")
        p.add_argument("--base", help="git base ref (default: orchestrator.base_ref)")
        p.add_argument("--committed-only", action="store_true", help="ignore uncommitted / untracked changes")
        p.add_argument("--spec", help="spec / ticket path passed to the roles")
        p.add_argument("--request", help="plain-language task statement passed to the roles")
        p.add_argument("--engine", help="engine name under orchestrator.engines (default: orchestrator.engine)")
        p.add_argument("--timeout", type=int, help="per-gate timeout in seconds")
        p.add_argument("--dry-run", action="store_true", help="no AI calls and no checks; synthetic APPROVE verdicts")

    for name, helptext in (("classify", "show scope, Gate 0 checks and routed stages"),
                           ("checks", "run Gate 0 (project checks) only"),
                           ("run", "Gate 0, then pending gates stage by stage"), ("status", "show state")):
        p = sub.add_parser(name, help=helptext)
        common(p, task_required=name != "status")
        if name == "status":
            p.add_argument("--since", type=since_arg, help="activity by day since YYYY-MM-DD, today, yesterday or <n>d "
                                                           "(all tasks unless --task)")
        if name == "run":
            p.add_argument("--fresh", action="store_true", help="discard existing state and start over")
            p.add_argument("--skip-checks", action="store_true", help="skip Gate 0 (project checks)")
            p.add_argument("--serial", action="store_true", help="one gate at a time, even inside a stage")
    for name, helptext in (("run-gate", "run one named gate"), ("prompt", "print a role's full prompt"),
                           ("record", "persist a report produced elsewhere (stdin or --file)")):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("role")
        common(p)
        if name == "record":
            p.add_argument("--file", help="report file (default: read stdin)")
    p = sub.add_parser("journal", help="append a working session to the task journal (stdin or --file)")
    common(p)
    p.add_argument("--file", help="session notes file (default: read stdin)")
    p = sub.add_parser("automation", help="may the agent commit/push its fixes now? (profile `automation`)")
    common(p)
    p.add_argument("--action", choices=("commit", "push"), required=True)
    p = sub.add_parser("bands", help="classify production metrics against project/bands.yaml (no AI calls)")
    p.add_argument("--metrics", required=True, help="JSON object of metric name → number")
    p.add_argument("--bands", type=Path, help="bands file (default: .omni-team/project/bands.yaml)")
    p = sub.add_parser("setup", help="install the toolset into .omni-team/.venv (Python; --ui-probe: Playwright)")
    p.add_argument("--ui-probe", action="store_true", help="also Playwright and a browser for tools/ui-probe.mjs")
    return parser
