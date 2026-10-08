#!/usr/bin/env python3
"""
run.py — benchmark code reviewers on cases with seeded defects.

    python3 bench/run.py                                   # default contenders, all cases, 1 run
    python3 bench/run.py --runs 3 --parallel 4             # repeat to see variance
    python3 bench/run.py --contenders omni-security-engineer,cc-security-review --cases py-search,ts-invoices
    python3 bench/run.py --dry-run                         # show the plan and prompt sizes, no AI calls

Writes bench/results/<timestamp>/{report.md, results.json, raw/<case>/<contender>-r<n>.md}.
Needs PyYAML and the `claude` CLI (or whatever contenders.yaml calls).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from statistics import mean
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchlib import (BENCH, Case, Contender, RunResult, contender_io, load_cases,  # noqa: E402
                      load_contenders, run_one, score)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--contenders", help="comma list (default: default_contenders in contenders.yaml)")
    p.add_argument("--cases", help="comma list of case ids (default: all)")
    p.add_argument("--runs", type=int, default=1, help="repetitions per case and contender (default 1)")
    p.add_argument("--parallel", type=int, default=2, help="concurrent runs (default 2)")
    p.add_argument("--timeout", type=int, default=600, help="seconds per run (default 600)")
    p.add_argument("--model", help="override the model of every contender")
    p.add_argument("--config", type=Path, default=BENCH / "contenders.yaml")
    p.add_argument("--out", type=Path, help="results folder (default bench/results/<timestamp>)")
    p.add_argument("--dry-run", action="store_true", help="print the plan; no AI calls")
    p.add_argument("--rescore", type=Path, help="re-score an existing results folder with the current scorer; no AI calls")
    return p.parse_args()


def pick_contenders(args: argparse.Namespace) -> List[Contender]:
    available, default = load_contenders(args.config)
    names = [n.strip() for n in args.contenders.split(",")] if args.contenders else default
    unknown = [n for n in names if n not in available]
    if unknown:
        raise SystemExit(f"unknown contender(s): {', '.join(unknown)} (available: {', '.join(available)})")
    chosen = [available[n] for n in names]
    if args.model:
        for c in chosen:
            c.model = args.model
    return chosen


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _pct(n: float, d: float) -> str:
    return f"{100 * n / d:.0f}%" if d else "n/a"


def summary_rows(results: List[RunResult], contenders: List[Contender], cases: List[Case], runs: int) -> List[str]:
    seeded = [c for c in cases if c.defects]
    clean = [c for c in cases if not c.defects]
    total_defects = sum(len(c.defects) for c in seeded) * runs
    rows = ["| Contender | Setup | Caught (strict) | Caught (lenient) | Extra findings on seeded cases | "
            "Findings on clean cases | Errors | Cost (USD) | Mean time |",
            "|---|---|---|---|---|---|---|---|---|"]
    for c in contenders:
        mine = [r for r in results if r.contender == c.name]
        strict = sum(len(r.caught_strict) for r in mine)
        lenient = sum(len(r.caught_lenient) for r in mine)
        extra = sum(len(r.extra) for r in mine if any(r.case == s.id for s in seeded))
        noise = sum(len(r.findings) for r in mine if any(r.case == s.id for s in clean))
        errors = sum(1 for r in mine if not r.ok)
        cost = sum(r.cost_usd for r in mine)
        duration = mean(r.duration_s for r in mine) if mine else 0
        rows.append(f"| **{c.name}** | {c.describe()} | {strict}/{total_defects} ({_pct(strict, total_defects)}) | "
                    f"{lenient}/{total_defects} ({_pct(lenient, total_defects)}) | {extra} | {noise} | {errors} | "
                    f"{cost:.2f} | {duration:.0f}s |")
    return rows


def defect_rows(results: List[RunResult], contenders: List[Contender], cases: List[Case], runs: int) -> List[str]:
    rows = ["| Case | Defect | Severity | " + " | ".join(c.name for c in contenders) + " |",
            "|---|---|---|" + "---|" * len(contenders)]
    for case in cases:
        for d in case.defects:
            cells = []
            for c in contenders:
                mine = [r for r in results if r.contender == c.name and r.case == case.id]
                strict = sum(d.id in r.caught_strict for r in mine)
                lenient = sum(d.id in r.caught_lenient for r in mine)
                mark = "✅" if strict == runs else ("🟡" if lenient else "❌")
                cells.append(f"{mark} {strict}/{runs}" + (f" (lenient {lenient})" if lenient != strict else ""))
            rows.append(f"| {case.id} | {d.id}: {d.summary} | {d.severity} | " + " | ".join(cells) + " |")
        if not case.defects:
            cells = []
            for c in contenders:
                mine = [r for r in results if r.contender == c.name and r.case == case.id]
                cells.append(f"{sum(len(r.findings) for r in mine)} finding(s)")
            rows.append(f"| {case.id} | *clean change — any finding is noise or a judgement call* | — | "
                        + " | ".join(cells) + " |")
    return rows


def extra_rows(results: List[RunResult]) -> List[str]:
    rows = []
    for r in sorted(results, key=lambda x: (x.case, x.contender, x.run)):
        if r.extra:
            rows.append(f"- **{r.contender}** on `{r.case}` (run {r.run}):")
            rows += [f"  - `{f.file}:{f.line}` — {f.text[:220]}" for f in r.extra]
        if not r.ok:
            rows.append(f"- ⚠️ **{r.contender}** on `{r.case}` (run {r.run}) failed: {r.error}")
    return rows or ["- none"]


def write_report(out: Path, results: List[RunResult], contenders: List[Contender], cases: List[Case],
                 runs: int) -> Path:
    lines = [
        f"# Review benchmark — {dt.datetime.now():%Y-%m-%d %H:%M}",
        "",
        f"{len(cases)} cases ({sum(1 for c in cases if c.defects)} with {sum(len(c.defects) for c in cases)} seeded "
        f"defects, {sum(1 for c in cases if not c.defects)} clean) × {len(contenders)} contenders × {runs} run(s).",
        "",
        "**Strict** = a finding cites the defect's file and a line within ±3 of it. **Lenient** = strict, or the "
        "output names the file and one of the defect's keywords. **Extra findings** are locations outside the answer "
        "key: some are real issues the key does not list, so read them before calling them false positives.",
        "",
        "## Summary", "", *summary_rows(results, contenders, cases, runs), "",
        "## Per defect", "", *defect_rows(results, contenders, cases, runs), "",
        "## Extra findings and failures (review by hand)", "", *extra_rows(results), "",
        "Raw outputs: `raw/<case>/<contender>-r<run>.md`.",
    ]
    report = out / "report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def save_raw(out: Path, result: RunResult) -> None:
    path = out / "raw" / result.case / f"{result.contender}-r{result.run}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (f"<!-- contender={result.contender} case={result.case} run={result.run} ok={result.ok} "
              f"cost_usd={result.cost_usd:.4f} duration_s={result.duration_s:.1f} turns={result.turns} -->\n\n")
    path.write_text(header + (result.text or result.error) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def rescore(folder: Path, args: argparse.Namespace) -> int:
    raw = json.loads((folder / "results.json").read_text(encoding="utf-8"))
    results = [RunResult(**{k: v for k, v in r.items() if k not in ("findings", "extra")}) for r in raw]
    cases = {c.id: c for c in load_cases(sorted({r.case for r in results}))}
    for r in results:
        if r.ok:
            score(cases[r.case], r)
    available, _ = load_contenders(args.config)
    names = list(dict.fromkeys(r.contender for r in results))
    contenders = [available[n] for n in names]
    runs = max(r.run for r in results)
    (folder / "results.json").write_text(json.dumps([asdict(r) for r in results], indent=2, ensure_ascii=False),
                                         encoding="utf-8")
    report = write_report(folder, results, contenders, list(cases.values()), runs)
    print("\n".join(summary_rows(results, contenders, list(cases.values()), runs)))
    print(f"\n📄 {report} (re-scored)")
    return 0


def main() -> int:
    args = parse_args()
    if args.rescore:
        return rescore(args.rescore, args)
    cases = load_cases([c.strip() for c in args.cases.split(",")] if args.cases else None)
    contenders = pick_contenders(args)
    plan = [(c, case, run) for run in range(1, args.runs + 1) for case in cases for c in contenders]
    print(f"🧪 {len(plan)} runs: {len(cases)} cases × {len(contenders)} contenders × {args.runs} run(s)")
    for c in contenders:
        print(f"   • {c.name}: {c.describe()}")
    if args.dry_run:
        for c in contenders:
            argv, stdin = contender_io(c, cases[0])
            print(f"\n[{c.name}] argv: {' '.join(argv)}\n[{c.name}] stdin prompt: {len(stdin):,} chars")
        return 0

    out = args.out or BENCH / "results" / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    results: List[RunResult] = []
    with tempfile.TemporaryDirectory(prefix="omni-bench-") as tmp:
        def job(item) -> RunResult:
            contender, case, run = item
            workdir = Path(tmp) / f"{contender.name}-r{run}"
            workdir.mkdir(exist_ok=True)
            result = run_one(contender, case, run, workdir, args.timeout)
            save_raw(out, result)
            status = "ok" if result.ok else f"FAILED ({result.error[:80]})"
            print(f"   {case.id:20s} {contender.name:24s} r{run}  caught {result.caught_strict or '-'}  "
                  f"extra {len(result.extra)}  ${result.cost_usd:.3f}  {result.duration_s:.0f}s  {status}", flush=True)
            return result
        with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as pool:
            results = list(pool.map(job, plan))

    (out / "results.json").write_text(json.dumps([asdict(r) for r in results], indent=2, ensure_ascii=False),
                                      encoding="utf-8")
    report = write_report(out, results, contenders, cases, args.runs)
    print("\n" + "\n".join(summary_rows(results, contenders, cases, args.runs)))
    print(f"\n📄 {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
