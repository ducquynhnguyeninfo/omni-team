"""
Review benchmark library — cases with seeded defects, isolated repos, contender runs, scoring.

A case is a tiny codebase (`base/`) plus a change (`change/`) that contains known defects.
The answer key (`case.yaml`) never enters the repository the reviewer sees: every run gets a
fresh temporary git repo with `base/` committed and `change/` applied as uncommitted work.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

BENCH = Path(__file__).resolve().parent
FRAMEWORK = BENCH.parent / ".omni-team"
sys.path.insert(0, str(FRAMEWORK))

from lib.roles import load_protocol, role_by_name  # noqa: E402
from lib.runner import build_prompt  # noqa: E402

LINE_TOLERANCE = 3
GIT_ENV = ["-c", "user.email=bench@omni-team", "-c", "user.name=bench", "-c", "core.hooksPath=/dev/null"]
LOCATION_RE = re.compile(r"(?P<path>[A-Za-z0-9_./\\-]+\.[A-Za-z0-9]+):(?P<line>\d+)(?:\s*[-–]\s*(?P<end>\d+))?")


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

@dataclass
class Defect:
    id: str
    file: str
    start: int
    end: int
    severity: str
    summary: str
    keywords: List[str]
    also: List[Tuple[str, int, int]] = field(default_factory=list)  # other locations that also count

    @property
    def locations(self) -> List[Tuple[str, int, int]]:
        return [(self.file, self.start, self.end)] + self.also


@dataclass
class Case:
    id: str
    language: str
    request: str
    defects: List[Defect]
    root: Path

    @property
    def changed_files(self) -> List[str]:
        change = self.root / "change"
        return sorted(str(p.relative_to(change)) for p in change.rglob("*") if p.is_file())

    @property
    def known_files(self) -> List[str]:
        files = set(self.changed_files)
        base = self.root / "base"
        files |= {str(p.relative_to(base)) for p in base.rglob("*") if p.is_file()}
        return sorted(files)


def load_case(folder: Path) -> Case:
    raw = yaml.safe_load((folder / "case.yaml").read_text(encoding="utf-8"))
    defects = [Defect(d["id"], d["file"], d["lines"][0], d["lines"][1], d["severity"], d["summary"],
                      list(d.get("keywords", [])),
                      [(a["file"], a["lines"][0], a["lines"][1]) for a in d.get("also", [])])
               for d in raw.get("defects") or []]
    return Case(raw["id"], raw["language"], raw["request"], defects, folder)


def load_cases(names: Optional[List[str]] = None) -> List[Case]:
    cases = [load_case(p.parent) for p in sorted((BENCH / "cases").glob("*/case.yaml"))]
    if names:
        unknown = sorted(set(names) - {c.id for c in cases})
        if unknown:
            raise SystemExit(f"unknown case(s): {', '.join(unknown)}")
        cases = [c for c in cases if c.id in names]
    return cases


def materialize(case: Case, workdir: Path) -> Path:
    """Fresh git repo: base committed, change applied as uncommitted work. No answer key inside."""
    repo = workdir / case.id
    shutil.copytree(case.root / "base", repo)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", *GIT_ENV, "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", *GIT_ENV, "commit", "-qm", "base"], cwd=repo, check=True)
    shutil.copytree(case.root / "change", repo, dirs_exist_ok=True)
    return repo


# ---------------------------------------------------------------------------
# Contenders
# ---------------------------------------------------------------------------

@dataclass
class Contender:
    name: str
    kind: str                       # omni-role | prompt | agent-file
    cmd: List[str]
    model: str
    role: str = ""
    prompt: str = ""
    path: str = ""                  # agent-file: a Claude agent definition (.md) used verbatim
    replace: Dict[str, str] = field(default_factory=dict)  # agent-file: path mapping onto the case layout

    def describe(self) -> str:
        what = {"omni-role": f"omni-team role `{self.role}`", "prompt": f"prompt `{self.prompt}`",
                "agent-file": f"agent file `{Path(self.path).name}`"}[self.kind]
        return f"{what} · model {self.model}"


def load_contenders(path: Path) -> Tuple[Dict[str, Contender], List[str]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    default_model = (raw.get("defaults") or {}).get("model", "sonnet")
    contenders = {}
    for name, spec in raw["contenders"].items():
        if spec["kind"] not in ("omni-role", "prompt", "agent-file"):
            raise SystemExit(f"contender {name}: kind must be omni-role, prompt or agent-file")
        contenders[name] = Contender(name, spec["kind"], list(spec["cmd"]), spec.get("model", default_model),
                                     spec.get("role", ""), spec.get("prompt", ""), spec.get("path", ""),
                                     dict(spec.get("replace") or {}))
    return contenders, list(raw.get("default_contenders") or contenders)


def omni_invocation(case: Case) -> str:
    files = "\n".join(f"  - {f}" for f in case.changed_files)
    return (
        f"- Task id: bench-{case.id}\n"
        f"- Request: {case.request}\n"
        f"- Diff: uncommitted changes in the working tree against HEAD (`git diff HEAD` plus untracked files)\n"
        f"- Changed files:\n{files}"
    )


def agent_file_prompt(contender: Contender, case: Case) -> str:
    """A third-party agent definition, verbatim except for path mapping, plus the same invocation block."""
    text = Path(os.path.expandvars(contender.path)).expanduser().read_text(encoding="utf-8")
    body = text.split("---", 2)[2] if text.startswith("---") else text
    for old, new in contender.replace.items():
        body = body.replace(old, new)
    return (f"{body.strip()}\n\n---\n\n## This invocation\n\n{omni_invocation(case)}\n\n"
            "Produce your full report using your Output format, ending with your verdict line.")


def contender_io(contender: Contender, case: Case) -> Tuple[List[str], str]:
    argv = [arg.replace("{model}", contender.model) for arg in contender.cmd]
    if contender.kind == "omni-role":
        return argv, build_prompt(role_by_name(contender.role), load_protocol(), omni_invocation(case))
    if contender.kind == "agent-file":
        return argv, agent_file_prompt(contender, case)
    if "{prompt}" not in argv:
        raise SystemExit(f"contender {contender.name}: cmd needs a \"{{prompt}}\" element")
    return [contender.prompt if arg == "{prompt}" else arg for arg in argv], ""


# ---------------------------------------------------------------------------
# Runs and scoring
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    file: str
    line: int
    end: int
    text: str


@dataclass
class RunResult:
    contender: str
    case: str
    run: int
    ok: bool
    error: str = ""
    text: str = ""
    cost_usd: float = 0.0
    duration_s: float = 0.0
    turns: int = 0
    caught_strict: List[str] = field(default_factory=list)
    caught_lenient: List[str] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)
    extra: List[Finding] = field(default_factory=list)


def _map_path(raw: str, known: List[str]) -> Optional[str]:
    raw = raw.strip("`'\"[](){}").lstrip("./")
    for prefix in ("a/", "b/"):
        if raw.startswith(prefix) and raw[2:] in known:
            raw = raw[2:]
    for k in known:
        if raw == k or raw.endswith("/" + k) or k.endswith("/" + raw):
            return k
    return None


# Report-template header lines that cite a location without being a finding (e.g. omni-team's
# "**Pattern reference**: src/x.ts:1"). Excluded so templates are not mistaken for findings.
METADATA_RE = re.compile(r"^\s*[-*>]*\s*\**\s*(pattern reference|scope|stack lens|sources read|artefacts|engine / tool)\b",
                         re.IGNORECASE)
JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```", re.DOTALL)


def _json_items(text: str) -> List[Dict[str, Any]]:
    """Findings emitted as JSON (fenced block or the whole output), e.g. headless /code-review."""
    candidates = [m.group(1) for m in JSON_BLOCK_RE.finditer(text)] + [text.strip()]
    items: List[Dict[str, Any]] = []
    for blob in candidates:
        try:
            data = json.loads(blob)
        except ValueError:
            continue
        data = data.get("findings", data) if isinstance(data, dict) else data
        items += [d for d in data if isinstance(d, dict)] if isinstance(data, list) else []
    return items


def extract_findings(text: str, known: List[str]) -> List[Finding]:
    seen, findings = set(), []
    for item in _json_items(text):
        path = _map_path(str(item.get("file") or item.get("path") or ""), known)
        try:
            start = int(item.get("line") or item.get("start_line") or 0)
        except (TypeError, ValueError):
            start = 0
        if path and start and (path, start) not in seen:
            seen.add((path, start))
            summary = str(item.get("summary") or item.get("description") or "")
            findings.append(Finding(path, start, int(item.get("end_line") or start), summary))
    for line_text in text.splitlines():
        if METADATA_RE.match(line_text):
            continue
        for m in LOCATION_RE.finditer(line_text):
            path = _map_path(m.group("path"), known)
            if not path:
                continue
            start = int(m.group("line"))
            end = int(m.group("end") or start)
            if (path, start) not in seen:
                seen.add((path, start))
                findings.append(Finding(path, start, max(start, end), line_text.strip()))
    return findings


def _hits(defect: Defect, finding: Finding) -> bool:
    return any(finding.file == file and finding.line <= end + LINE_TOLERANCE and finding.end >= start - LINE_TOLERANCE
               for file, start, end in defect.locations)


def score(case: Case, result: RunResult) -> None:
    findings = extract_findings(result.text, case.known_files)
    result.findings = findings
    result.caught_strict = [d.id for d in case.defects if any(_hits(d, f) for f in findings)]
    lowered = result.text.lower()
    lenient = set(result.caught_strict)
    for d in case.defects:
        name_seen = any(Path(file).name.lower() in lowered for file, _, _ in d.locations)
        if name_seen and any(k.lower() in lowered for k in d.keywords):
            lenient.add(d.id)
    result.caught_lenient = [d.id for d in case.defects if d.id in lenient]
    result.extra = [f for f in findings if not any(_hits(d, f) for d in case.defects)]


def run_one(contender: Contender, case: Case, run: int, workdir: Path, timeout_s: int) -> RunResult:
    repo = materialize(case, workdir)
    argv, stdin = contender_io(contender, case)
    result = RunResult(contender.name, case.id, run, ok=False)
    started = time.monotonic()
    try:
        done = subprocess.run(argv, cwd=repo, input=stdin, capture_output=True, text=True,
                              timeout=timeout_s, check=False)
    except FileNotFoundError:
        result.error = f"`{argv[0]}` not found"
        return result
    except subprocess.TimeoutExpired:
        result.error, result.duration_s = f"timeout after {timeout_s}s", float(timeout_s)
        return result
    result.duration_s = time.monotonic() - started
    try:
        payload: Dict[str, Any] = json.loads(done.stdout)
    except ValueError:
        result.error = f"non-JSON output (exit {done.returncode}): {(done.stdout or done.stderr)[:300]}"
        return result
    result.text = str(payload.get("result", ""))
    result.cost_usd = float(payload.get("total_cost_usd") or 0.0)
    result.turns = int(payload.get("num_turns") or 0)
    result.ok = not payload.get("is_error", False) and done.returncode == 0
    if not result.ok:
        result.error = f"engine reported an error: {result.text[:300]}"
    score(case, result)
    return result
