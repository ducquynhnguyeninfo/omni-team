# Repository Layout

```
omni-team/                          THE baseline automated-agent coding repo
├── CLAUDE.md                       Root index — thin, links into docs/
├── README.md                       Consumer-facing intro + quick-start
├── .gitignore
│
├── .claude/                        ALL framework code lives here
│   ├── LICENSE
│   ├── bootstrap.py                Render templates + manifest → .claude/agents/
│   ├── orchestrator.py             Classify / run / run-gate / status entrypoints
│   │
│   ├── lib/                        Pure modules — no side effects at import time
│   │   ├── __init__.py
│   │   ├── manifest.py             YAML loader + dotted-key lookup
│   │   ├── render.py               {{key.path}} substitution + missing-key reporter
│   │   ├── decision.py             Decision-matrix evaluator (base + add_if)
│   │   ├── state.py                RunState / GateState + JSON persistence
│   │   └── runner.py               `claude -p` subprocess wrapper + verdict regex
│   │
│   ├── templates/                  Layer 1 (Role) + Layer 2 (Process) — agent prompts
│   │   ├── tech-lead.md
│   │   ├── dba.md
│   │   ├── backend-reviewer.md
│   │   ├── frontend-reviewer.md
│   │   ├── qa-engineer.md
│   │   ├── qa-lead.md
│   │   ├── perf-engineer.md
│   │   ├── security-engineer.md
│   │   └── ui-smoke-engineer.md
│   │
│   ├── manifests/                  Layer 3 (Project conventions) — data
│   │   ├── _starter.yaml           Copy-paste skeleton; schema spec for new projects
│   │   └── example.yaml            Reference: fully-populated example manifest
│   │
│   ├── examples/                   Reference manifests for other stacks
│   │   ├── django-postgres.yaml
│   │   └── nextjs-prisma.yaml
│   │
│   └── agents/                     OUTPUT of bootstrap.py — Claude Code auto-loads from here
│                                    (created after first render; do not hand-edit)
│
└── docs/                           Split sub-guides — linked from CLAUDE.md
    ├── critical-rules.md
    ├── repository-layout.md        (this file)
    ├── architecture.md
    ├── manifest.md
    ├── agents.md
    ├── decision-matrix.md
    ├── workflow.md
    ├── code-quality.md
    ├── definition-of-done.md
    └── when-to-load.md
```

## Why `.claude/`?

Claude Code auto-discovers `.claude/agents/`, `.claude/commands/`, `.claude/settings.json` in any project. By placing the *framework* under `.claude/` too, a host project can adopt omni-team by copying or submoduling that single directory — no separate `.omni-team/` to track. The rendered agent prompts land in `.claude/agents/` exactly where Claude Code expects them.

## What goes where (mental model)

- **Generic role behavior** ("a Senior BE Engineer reviews layer discipline") → [`.claude/templates/`](../.claude/templates/).
- **Project-specific facts** ("our error contract is `LeanApiError`") → [`.claude/manifests/<project>.yaml`](../.claude/manifests/).
- **Routing logic** ("which agents fire for a given diff") → `decision_matrix:` section of the same manifest.
- **Engine** (load, render, classify, run) → [`.claude/lib/`](../.claude/lib/).
- **Entrypoints** (CLI surface) → [`.claude/bootstrap.py`](../.claude/bootstrap.py), [`.claude/orchestrator.py`](../.claude/orchestrator.py).
- **Sample / reference manifests** → [`.claude/examples/`](../.claude/examples/).
- **Working on the framework itself** → [`docs/`](.) (this directory).

## Files NOT to hand-edit

- `_state.json` — written by `orchestrator.py`; delete with `--fresh` if you need to reset.
- `.claude/agents/*` — these are *outputs* of `bootstrap.py`. Edit the template + re-render.
