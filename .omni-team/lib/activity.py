"""
Activity across tasks — what happened on which day, read from the artifacts folders.

Every gate report and journal session carries its timestamp (`## Invocation <iso>`,
`## Session <iso>`, and the When column of a rotated file's index), so a daily view needs no
per-day folders. This module only reads. Used by `orchestrator.py status --since`.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List

from lib import artifacts

_ISO_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}")
_DAYS_AGO = re.compile(r"^(\d+)d$")


@dataclass
class Event:
    when: str        # ISO timestamp, local time, as written in the artifact
    task: str
    source: str      # role name, or "journal"
    verdict: str
    summary: str


def since_date(value: str, today: dt.date) -> str:
    """`YYYY-MM-DD`, `today`, `yesterday` or `<n>d` (n days ago) → ISO date. Raises ValueError."""
    named = {"today": 0, "yesterday": 1}
    days = _DAYS_AGO.match(value)
    if value in named or days:
        return (today - dt.timedelta(days=named.get(value) if value in named else int(days.group(1)))).isoformat()
    return dt.date.fromisoformat(value).isoformat()


def task_folders(project_root: Path, artifacts_dir: str) -> Dict[str, Path]:
    """Task id → artifacts folder, for every task folder that exists (`artifacts_dir` holds {task_id})."""
    pattern = artifacts_dir.format(task_id="*")
    slot = Path(pattern).parts.index("*") if "*" in Path(pattern).parts else None
    if slot is None:
        raise ValueError(f"artifacts_dir '{artifacts_dir}' must contain {{task_id}} as a whole path component")
    found = (p for p in sorted(project_root.glob(pattern)) if p.is_dir())
    return {p.relative_to(project_root).parts[slot]: p for p in found}


def events(task: str, folder: Path) -> List[Event]:
    """Gate reports (rotated ones through the index) and journal sessions of one task."""
    out: List[Event] = []
    for path in sorted(folder.glob("*.md")):
        if path.name.startswith("_") and path.stem != artifacts.JOURNAL:
            continue     # _summary, _checks, _escapes carry no timestamped entries
        source = "journal" if path.stem == artifacts.JOURNAL else path.stem
        rows, entries = artifacts.parse(path.read_text(encoding="utf-8"))
        for row in rows:
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            if len(cells) >= 4:
                out.append(Event(cells[1], task, source, cells[2], cells[3]))
        out.extend(Event(e.when, task, source, e.verdict, e.summary) for e in entries)
    return out


def unrecorded(folder: Path, is_role: Callable[[str], bool]) -> List[str]:
    """Role report and journal files holding text written by hand instead of through `record`/`journal`."""
    managed = (p for p in sorted(folder.glob("*.md")) if p.stem == artifacts.JOURNAL or is_role(p.stem))
    return [p.name for p in managed if artifacts.stray_text(p.read_text(encoding="utf-8"))]


def report(project_root: Path, artifacts_dir: str, day: str, task: str = "") -> str:
    """Day-by-day activity of every task (or one), for `status --since`."""
    found = [e for name, folder in task_folders(project_root, artifacts_dir).items() if not task or name == task
             for e in events(name, folder)]
    found = since(found, day)
    return render(found) if found else f"no activity since {day}"


def since(found: List[Event], day: str) -> List[Event]:
    return sorted((e for e in found if _ISO_DAY.match(e.when) and e.when[:10] >= day), key=lambda e: e.when)


def render(found: List[Event]) -> str:
    """Grouped by day, then task, in time order."""
    lines: List[str] = []
    for day in sorted({e.when[:10] for e in found}):
        lines.append(f"📅 {day}")
        today = [e for e in found if e.when[:10] == day]
        for task in sorted({e.task for e in today}):
            lines.append(f"   {task}")
            for e in (x for x in today if x.task == task):
                verdict = "" if e.verdict in ("—", "?") else f" {e.verdict}"
                lines.append(f"     {e.when[11:16]} {e.source}{verdict} — {e.summary or '…'}")
    return "\n".join(lines)
