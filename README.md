# omni-team

A **stack-agnostic team of AI sub-agents** — an analyst, an architect, a project manager, a technical planner, seven reviewers and a release manager — that gate every non-trivial change before a human ships it. Works with any language or framework and with Claude Code, Codex, Gemini CLI and any agent that reads `AGENTS.md`.

This repository is the development home. **The product is the [`.omni-team/`](.omni-team/) folder** — copy it into a project and it works:

```bash
python3 .omni-team/install.py --dir /path/to/your-project            # copy + register (Claude Code, Codex)
python3 .omni-team/install.py upgrade --dir /path/to/your-project    # later: upgrade, keeps project/ and runs/
```

Then ask your agent: *"omni-task: add CSV export to the reports page"* (or *"follow .omni-team/AGENTS.md for this task"*).

Full guide: **[.omni-team/README.md](.omni-team/README.md)** · Agent manual: [.omni-team/AGENTS.md](.omni-team/AGENTS.md)

## The team

```
request ─► ba · architect ─► tech-lead ─► implement ─► data · code · test · security · perf ─► qa-lead · smoke ─► HUMAN
           (define/design)  (plan)       (main agent)     (Gate 0 checks, then routed gates)   (accept)    (commit)
```

| Role | Owns |
|---|---|
| `ba` | requirements: stories, business rules, testable acceptance criteria — `/ba` |
| `architect` | ADRs for structural changes; architecture-drift review gate — `/architect` |
| `pm` | scope, schedule, RAID, prioritisation, tickets, status/weekly reports — on demand via `/pm` |
| `tech-lead` | phased plan, acceptance criteria, edge cases |
| `code-reviewer` | correctness, boundaries, conventions, idioms, UI code quality |
| `test-engineer` | missing tests (P0/P1/P2) |
| `data-reviewer` | migrations, data models, wire/persisted formats |
| `security-engineer` | authN/Z, secrets, injection, PII, supply chain |
| `perf-engineer` | budgets, query/I-O patterns, blocking calls |
| `qa-lead` | every acceptance criterion vs code and tests |
| `smoke-tester` | running the change for real |
| `release-manager` | version, changelog, release notes, deploy/rollback plan, go/no-go — `/release` |

## How it stays generic

- **Roles carry no stack knowledge** — they read the project's facts and rules from `.omni-team/project/` at run time (everything defaults to `auto` = inferred from the repo) and apply the idioms of whatever stack they find.
- **Routing is data** — named signals (UI change, schema change, API surface, security-sensitive, dependencies, perf paths) with multi-stack default patterns, overridable per project.
- **One source, many tools** — `install.py` (stdlib only) renders the same roles into `.claude/agents/*.md`, `.codex/agents/*.toml`, skills, and pointer blocks in `CLAUDE.md` / `AGENTS.md` / `GEMINI.md`.
- **Headless when needed** — `orchestrator.py` runs gates through `claude -p`, `codex exec` or any CLI you declare, with state, retry budget and CI-friendly exit codes.

## Developing the framework

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # PyYAML for orchestrator + tests
.venv/bin/python -m unittest discover -s .omni-team/tests
```

Rules: [AGENTS.md](AGENTS.md) → [.omni-team/docs/maintaining.md](.omni-team/docs/maintaining.md).

## License

[MIT](LICENSE)
