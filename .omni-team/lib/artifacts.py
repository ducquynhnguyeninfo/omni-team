"""
Per-role report files with size-capped rotation.

`runs/<task-id>/<role>.md` is on the hot path: re-runs of a gate, qa-lead and pm read it. Left to
grow, every later read gets more expensive. Once the file would exceed `max_kb`, the full text of
the older reports moves to `runs/<task-id>/_archive/<role>.md` (append-only, nothing is lost) and
the hot file keeps an index (one row per older report) plus the newest report verbatim.

    # Reports — <role>
    <!-- omni-team:index:begin -->  …index table…  <!-- omni-team:index:end -->
    ---
    ## Invocation <timestamp>       ← full reports since the last rotation

Text in a hot file that this module did not write (a report pasted in by hand) is never dropped:
the next append moves it verbatim to the archive, indexes it, and says so.

The task journal (`runs/<task-id>/_journal.md`, sessions headed `## Session <timestamp>`) is the
implementer's own log — done / open / next per working session — and rotates the same way.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

INDEX_BEGIN = "<!-- omni-team:index:begin -->"
INDEX_END = "<!-- omni-team:index:end -->"
ARCHIVE_DIR = "_archive"
JOURNAL = "_journal"
SEPARATOR = "\n\n---\n\n"
_ENTRY_START = re.compile(r"^## (?:Invocation|Session) ", re.MULTILINE)
_WHEN = re.compile(r"^## (?:Invocation|Session) (\S+)", re.MULTILINE)
_VERDICT_FIELD = re.compile(r"^- verdict: \*\*([A-Z_]+)\*\*", re.MULTILINE)
_OWN_LINE = re.compile(r"^(# Reports — \S+|# Journal|---)$")
MOVED_NOTE = {
    "rotated": "older entries rotated into _archive/",
    "stray": "⚠ text not written by omni-team was moved verbatim to _archive/ — persist reports with "
             "`orchestrator.py record`, never by editing the file",
}
_VERDICT_LINE = re.compile(r"^[\s>*_`#-]*VERDICT[*_`\s]*:(.*)$", re.MULTILINE | re.IGNORECASE)


@dataclass
class Entry:
    text: str              # from "## Invocation …" to the end of the report

    @property
    def when(self) -> str:
        m = _WHEN.search(self.text)
        return m.group(1) if m else "?"

    @property
    def is_session(self) -> bool:
        return self.text.startswith("## Session ")

    @property
    def verdict(self) -> str:
        m = _VERDICT_FIELD.search(self.text)
        return m.group(1) if m else ("—" if self.is_session else "?")

    @property
    def summary(self) -> str:
        if self.is_session:     # a session has no verdict: its first line of content says what it was about
            content = (re.sub(r"[*_`]", "", ln).lstrip("-#> ").strip() for ln in self.text.splitlines()[1:])
            gist = next((ln for ln in content if ln), "")
        else:
            lines = _VERDICT_LINE.findall(self.text)
            gist = lines[-1].split("—", 1)[-1] if lines else ""
        gist = " ".join(gist.replace("|", "/").split())
        return gist[:140] + ("…" if len(gist) > 140 else "")


def format_entry(role: str, verdict: str, started: dt.datetime, duration_s: float,
                 engine_name: str, output: str) -> str:
    return (
        f"## Invocation {started.isoformat(timespec='seconds')}\n"
        f"- role: `{role}`\n- engine: `{engine_name}`\n"
        f"- verdict: **{verdict}**\n- duration: {duration_s:.1f}s\n\n### Output\n\n{output.strip()}\n"
    )


def format_session(started: dt.datetime, body: str) -> str:
    return f"## Session {started.isoformat(timespec='seconds')}\n\n{body.strip()}\n"


def parse(text: str) -> Tuple[List[str], List[Entry]]:
    """(index rows, full entries) of a hot file; files written before rotation existed parse too."""
    rows: List[str] = []
    body = text
    if INDEX_BEGIN in text and INDEX_END in text:
        block = text[text.index(INDEX_BEGIN):text.index(INDEX_END)]
        rows = [ln for ln in block.splitlines() if ln.startswith("| ") and not ln.startswith(("| # ", "|---"))]
        body = text[text.index(INDEX_END) + len(INDEX_END):]
    starts = [m.start() for m in _ENTRY_START.finditer(body)]
    entries = []
    for i, start in enumerate(starts):
        chunk = body[start:starts[i + 1] if i + 1 < len(starts) else len(body)]
        entries.append(Entry(re.sub(r"\s*\n---\s*$", "", chunk.rstrip()).rstrip() + "\n"))
    return rows, entries


def stray_text(text: str) -> str:
    """Text of a hot file outside the index and before the first entry, other than this module's own
    title and separators: content written by hand rather than through `append`."""
    body = text
    if INDEX_BEGIN in text and INDEX_END in text:
        body = text[:text.index(INDEX_BEGIN)] + text[text.index(INDEX_END) + len(INDEX_END):]
    first = _ENTRY_START.search(body)
    head = body[:first.start()] if first else body
    return "\n".join(ln for ln in head.splitlines() if not _OWN_LINE.match(ln.strip())).strip()


def _to_archive(path: Path, text: str) -> None:
    archive = path.parent / ARCHIVE_DIR / path.name
    archive.parent.mkdir(parents=True, exist_ok=True)
    with archive.open("a", encoding="utf-8") as fh:
        fh.write(text)


def _row(number: int, entry: Entry) -> str:
    return f"| {number} | {entry.when} | {entry.verdict} | {entry.summary or '—'} |"


def render(role: str, rows: List[str], entries: List[Entry]) -> str:
    journal = role == JOURNAL
    parts = ["# Journal\n" if journal else f"# Reports — {role}\n"]
    if rows:
        parts.append(
            f"{INDEX_BEGIN}\nEarlier {'sessions' if journal else 'reports'}, full text in `{ARCHIVE_DIR}/{role}.md` (append-only). "
            f"Read the archive only to check one specific old {'session' if journal else 'finding'}.\n\n"
            f"| # | When | Verdict | Summary |\n|---|---|---|---|\n" + "\n".join(rows) + f"\n{INDEX_END}\n"
        )
    return "\n".join(parts) + "".join(SEPARATOR + e.text for e in entries)


def append(path: Path, entry_text: str, max_kb: int) -> str:
    """Add one entry; rotate when the hot file would exceed max_kb (0 = never). Returns what was moved
    to the archive: "" nothing, "stray" hand-written text (takes precedence), "rotated" older entries."""
    path.parent.mkdir(parents=True, exist_ok=True)
    role = path.stem
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    rows, entries = parse(text)
    moved = ""
    stray = stray_text(text)
    if stray:
        when = dt.datetime.now().isoformat(timespec="seconds")
        _to_archive(path, f"{SEPARATOR}## Moved {when} — not written by omni-team\n\n{stray}\n")
        rows = rows + [f"| {len(rows) + 1} | {when} | ? | text not written by omni-team, moved verbatim |"]
        moved = "stray"
    new = Entry(entry_text.strip() + "\n")
    candidate = render(role, rows, entries + [new])
    if max_kb <= 0 or not entries or len(candidate.encode("utf-8")) <= max_kb * 1024:
        path.write_text(candidate, encoding="utf-8")
        return moved
    _to_archive(path, "".join(SEPARATOR + e.text for e in entries))
    rows = rows + [_row(len(rows) + i + 1, e) for i, e in enumerate(entries)]
    path.write_text(render(role, rows, [new]), encoding="utf-8")
    return moved or "rotated"
