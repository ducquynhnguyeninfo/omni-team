# Review benchmark

Measures code reviewers on changes with **seeded defects**, so "is omni-team's reviewer worth it compared with Claude Code's built-in `/code-review`?" is answered with numbers instead of opinions. Development tool for this repository — not shipped to projects.

## How it works

- `cases/<id>/` — a tiny codebase (`base/`), a change (`change/`) and the answer key (`case.yaml`: defect id, file, line range, severity, keywords). Clean cases have `defects: []` and measure noise.
- Every run gets a **fresh temporary git repo**: `base/` committed, `change/` applied as uncommitted work. The answer key never enters that repo.
- `contenders.yaml` — who competes. `agent-file` contenders run any Claude agent definition verbatim (with a path mapping onto the case layout), e.g. a project's hand-written reviewers. `omni-role` contenders receive the omni-team role prompt on stdin exactly like the headless orchestrator; `prompt` contenders run a literal prompt such as `/code-review medium`. All use `claude -p --output-format json` with the same model and the same read-only tool allow-list, so cost and turns are measured.
- Scoring (`benchlib.py`): findings are extracted from `file:line` citations or JSON findings.
  - **strict** — a finding cites the defect's file within ±3 lines;
  - **lenient** — strict, or the output names the file and a defect keyword (catches right diagnosis / wrong line);
  - **extra findings** — citations outside the key; read them, some are real issues;
  - **findings on clean cases** — noise or judgement calls.

```bash
pip install pyyaml                                     # plus the `claude` CLI
python3 bench/run.py --dry-run                         # plan + prompt sizes, no AI calls
python3 bench/run.py --runs 2 --parallel 4             # default contenders, all cases
python3 bench/run.py --contenders omni-security-engineer,cc-security-review --cases py-search,ts-invoices
python3 bench/run.py --rescore bench/results/<run>     # re-score saved outputs after changing the scorer
python3 -m unittest discover -s bench/tests            # scorer and answer-key tests
```

Results land in `bench/results/<timestamp>/`: `report.md`, `results.json`, raw outputs per case/contender/run.

## Cases

| Case | Lang | What is seeded | Kind |
|---|---|---|---|
| py-pagination | Python | off-by-one slice, floor-division page count | logic |
| py-search | Python | SQL injection, connection leak on error | security / resources |
| py-settings | Python | mutable default argument, falsy-zero check | language pitfall |
| py-caller-break | Python | signature change breaks a caller in an **unchanged** file | cross-file |
| ts-sync | TypeScript | async `forEach` not awaited, error swallowed as success | async |
| ts-invoices | TypeScript | IDOR (no ownership check), stack trace returned | authz |
| ts-convention | TypeScript | float dollars and ad-hoc error JSON, both forbidden by the repo's `CLAUDE.md` | project conventions |
| go-copy | Go | ignored `io.Copy` error, `defer Close` in a loop | error handling |
| go-cache | Go | unlocked map access, unstoppable goroutine | concurrency |
| py-invariant-scope | Python + SQL | role names unique per scope instead of globally → bare-name lookup and `ON CONFLICT (name)` seed break, both in **unchanged** files | invariant change |
| py-invariant-scope-large | Python + SQL | the same, with ~30 unrelated modules and the dependents buried in `app/admin/access/` and `scripts/seed/` | invariant change |
| py-clean-refactor | Python | — (behaviour-preserving refactor) | clean |
| ts-clean-feature | TypeScript | — (small correct feature with tests) | clean |

## Results — 2026-10-08 (`results/20261008-012241`)

11 cases (17 seeded defects, 2 clean) × 2 runs, model sonnet for both.

| | omni-team `code-reviewer` | Claude Code `/code-review medium` |
|---|---|---|
| Defects found (lenient) | **34/34 (100%)** | **34/34 (100%)** |
| Defects found (strict, line within ±3) | 32/34 (94%) — found `io.Copy` both times but cited line 24/25 instead of 30 | 34/34 (100%) |
| Hard cases (cross-file, CLAUDE.md conventions, data race) | 10/10 | 10/10 |
| Findings on clean changes (2 cases × 2 runs) | 3 (mostly hedged INFO) | 7 (nits: perf, missing tests, negative-zero) |
| Extra findings on seeded cases | 16 | 15 |
| Severity + machine-readable verdict | yes (22/22 runs end with `VERDICT:`) | no (findings only; JSON at `medium`, plain text at `low`) |
| Cost per run | **$0.094** | **$0.052** (−45%) |
| Mean time per run | 18 s | 17 s |

### Reading

- **Detection quality is a tie** on these cases, including the ones designed to be hard for diff-only review. Claude Code's reviewer cites lines more precisely.
- **omni costs ~1.8× more** per review, mostly because its prompt (role + shared protocol + invocation, ~13k characters) is sent every time.
- **omni is quieter on clean code and gates**: severities plus a `VERDICT` line are what the orchestrator's stages, retry budget and CI exit codes run on. `/code-review` gives no verdict, and its headless output format changes with the effort level, which makes it a fragile building block for automation.
- **Not measured here**: everything that is not single-diff code review — routing, staged gates, approvals that expire, `qa-lead` acceptance against a spec, `data-reviewer`, `pm`, `ba`, `release-manager`, multi-tool use. Those have no built-in Claude Code counterpart.

### Caveats

Small synthetic cases (≤ 50 changed lines), one model, two runs, the author of omni-team also wrote the cases. Treat the numbers as a first signal, then add real diffs from your projects (with known bugs from history) before deciding.

## Experiment — invariant sweep rule (2026-10-08)

Question: a client project's workflow log records four misses of one class — an invariant change (name uniqueness scope, non-delegable permissions, permission-split reuse) broke **unchanged** code that per-diff gates did not re-review; Codex's whole-repo cross-check caught them. Does an explicit "sweep dependents" rule help?

| Contender (3 runs each) | py-invariant-scope | py-invariant-scope-large | "Invariants changed" section |
|---|---|---|---|
| omni `code-reviewer`, before the rule | 6/6 | 6/6 | 0/6 reports |
| omni `data-reviewer`, before the rule | 6/6 | 6/6 | 0/6 reports |
| Claude Code `/code-review medium` | 5/6 strict, 6/6 lenient | 6/6 | — |
| client project's v1 `backend-reviewer` (verbatim, `agent-file`) | — | 5/6 strict, 6/6 lenient | — |
| client project's v1 `dba` (verbatim, `agent-file`) | — | 6/6 | — |
| omni `code-reviewer`, **after** the rule | 6/6 | 6/6 | **6/6 reports** |
| omni `data-reviewer`, **after** the rule | 6/6 | 6/6 | **6/6 reports** |

Regression over all other cases (2 runs): recall unchanged, extra findings 19 → 16, cost $0.094 → $0.098 per run.

Findings:

- **The synthetic cases do not reproduce the miss.** Every reviewer, including the client project's own scope-restricted agents, searched the repo and found both broken dependents. The real misses therefore depend on things a small repo lacks — scale (thousands of files), indirect consequences, a main agent that hands the gate a narrow file list. A faithful test needs a real historical diff replayed on the real repository.
- **What the rule does buy, measurably:** the sweep becomes **auditable** — every report states which invariant changed, how dependents were searched and what was found — at no measurable cost in recall, noise or price.
- **Side discovery:** in one run the model filed its findings through Claude Code's `ReportFindings` tool, so `claude -p` returned only a one-line verdict and the report was lost. Fixed in the protocol (final message = full report) and by disabling that tool for omni engines (`go-cache` re-run: 8/8, every report complete).

## Adding a case

1. `cases/<id>/base/…` and `cases/<id>/change/…` (only changed or new files in `change/`).
2. `cases/<id>/case.yaml` with `id`, `language`, `request`, `defects` (`file`, `lines: [start, end]`, `severity`, `summary`, `keywords`). A defect may live in an unchanged base file (cross-file cases).
3. No hints in the code (no "BUG" comments). `python3 -m unittest discover -s bench/tests` checks every answer key points at non-blank lines.
