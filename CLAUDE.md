# CLAUDE.md

**omni-team** — the baseline automated-agent coding repo. The framework lives at the repo root (`templates/`, `manifests/`, `lib/`, `bootstrap.py`, `orchestrator.py`). Running `bootstrap.py` renders agents into `.claude/agents/`, which Claude Code auto-loads. See [README.md](README.md) for the consumer-facing intro and quick-start.

This file is the **workspace root** instruction. Sub-guides under [docs/](docs/) carry the deep rules — Claude Code auto-loads the nearest `CLAUDE.md`, but should follow links into `docs/` for any topic listed below.

## Critical Rules (must read)

See [docs/critical-rules.md](docs/critical-rules.md) for the full list. Top-3 invariants:

1. **Templates stay project-agnostic.** Anything stack-specific belongs in a manifest, never hardcoded in [`templates/*.md`](templates/).
2. **Decision matrix is data, not code.** Modify [`manifests/*.yaml`](manifests/), never branch on stacks/paths inside [`lib/decision.py`](lib/decision.py).
3. **Never auto-commit / auto-push from [`orchestrator.py`](orchestrator.py).** The human gate (Codex crosscheck → manual commit) is load-bearing.

## When to load which guide

| Trigger | Read |
|---|---|
| Touching [`templates/*.md`](templates/) or adding placeholders | [docs/manifest.md](docs/manifest.md) + [docs/critical-rules.md](docs/critical-rules.md) |
| Touching [`lib/decision.py`](lib/decision.py) or matrix predicates | [docs/decision-matrix.md](docs/decision-matrix.md) |
| Touching [`orchestrator.py`](orchestrator.py) / state machine / retry budget | [docs/architecture.md](docs/architecture.md) + [docs/workflow.md](docs/workflow.md) |
| Adding/changing an agent role | [docs/agents.md](docs/agents.md) + [docs/manifest.md](docs/manifest.md) |
| Onboarding a new project (writing a manifest) | [README.md](README.md) §Quick-start + [docs/manifest.md](docs/manifest.md) + [manifests/example.yaml](manifests/example.yaml) as reference |
| Anything before commit | [docs/definition-of-done.md](docs/definition-of-done.md) |
| Lines/function-size/complexity questions | [docs/code-quality.md](docs/code-quality.md) |
| "Where does X live?" | [docs/repository-layout.md](docs/repository-layout.md) |
| Full file map of when-to-read-what | [docs/when-to-load.md](docs/when-to-load.md) |

## Two ways to consume this baseline

**A) Clone-as-starting-point.** Use the repo itself as your project root. Write your manifest, run `python bootstrap.py --manifest manifests/<your>.yaml`, develop normally. Bootstrap writes rendered agents into `.claude/agents/` for Claude Code to auto-load.

**B) Vendored-into-existing-project.** Copy or git-submodule the framework files into your existing project (e.g. under `.omni-team/`). Run `python .omni-team/bootstrap.py --manifest .omni-team/manifests/<your>.yaml`. The bootstrap target stays `.claude/agents/` in the host project, so Claude Code picks the rendered agents up automatically.

For deeper rationale see [docs/architecture.md](docs/architecture.md). For the full manifest schema see [docs/manifest.md](docs/manifest.md).
