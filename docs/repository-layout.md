# Repository Layout

```
omni-team/                          THE baseline automated-agent coding repo
├── CLAUDE.md                       Root index — thin, links into docs/
├── README.md                       Consumer-facing intro + quick-start
├── LICENSE
├── .gitignore
│
├── bootstrap.py                    Render templates + manifest → .claude/agents/
├── orchestrator.py                 Classify / run / run-gate / status entrypoints
│
├── lib/                            Pure modules — no side effects at import time
│   ├── __init__.py
│   ├── manifest.py                 YAML loader + dotted-key lookup
│   ├── render.py                   {{key.path}} substitution + missing-key reporter
│   ├── decision.py                 Decision-matrix evaluator (base + add_if)
│   ├── state.py                    RunState / GateState + JSON persistence
│   └── runner.py                   `claude -p` subprocess wrapper + verdict regex
│
├── templates/                      Layer 1 (Role) + Layer 2 (Process) — agent prompts
│   ├── tech-lead.md
│   ├── dba.md
│   ├── backend-reviewer.md
│   ├── frontend-reviewer.md
│   ├── qa-engineer.md
│   ├── qa-lead.md
│   ├── perf-engineer.md
│   ├── security-engineer.md
│   └── ui-smoke-engineer.md
│
├── manifests/                      Layer 3 (Project conventions) — data
│   ├── _starter.yaml               Copy-paste skeleton; schema spec for new projects
│   └── example.yaml                Reference: fully-populated example manifest
│
├── examples/                       Reference manifests for other stacks
│   ├── django-postgres.yaml
│   └── nextjs-prisma.yaml
│
├── .claude/                        OUTPUT zone — Claude Code auto-loads from here
│   └── agents/                     Written by bootstrap.py; do not hand-edit
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

## Why framework files at root, agents under `.claude/`?

`.claude/` is Claude Code's auto-load convention — it watches `.claude/agents/`, `.claude/commands/`, `.claude/settings.json`. The framework (templates, manifests, lib, bootstrap.py, orchestrator.py) is a *tool* that produces `.claude/agents/`; it is not itself auto-loaded. Keeping framework sources at the root makes the split explicit: edit sources at the root, render output lands in `.claude/agents/`.

For "vendored into an existing project" consumption, copy the framework files under `.omni-team/` (or any non-`.claude/` directory) in the host project, then run `python .omni-team/bootstrap.py …` — output still lands in the host's `.claude/agents/`.

## What goes where (mental model)

- **Generic role behavior** ("a Senior BE Engineer reviews layer discipline") → [`templates/`](../templates/).
- **Project-specific facts** ("our error contract is `LeanApiError`") → [`manifests/<project>.yaml`](../manifests/).
- **Routing logic** ("which agents fire for a given diff") → `decision_matrix:` section of the same manifest.
- **Engine** (load, render, classify, run) → [`lib/`](../lib/).
- **Entrypoints** (CLI surface) → [`bootstrap.py`](../bootstrap.py), [`orchestrator.py`](../orchestrator.py).
- **Sample / reference manifests** → [`examples/`](../examples/).
- **Working on the framework itself** → [`docs/`](.) (this directory).

## Files NOT to hand-edit

- `_state.json` — written by `orchestrator.py`; delete with `--fresh` if you need to reset.
- `.claude/agents/*` — these are *outputs* of `bootstrap.py`. Edit the template + re-render.
