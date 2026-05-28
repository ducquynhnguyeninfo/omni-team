# CLAUDE.md

**omni-team** — the baseline automated-agent coding repo. The framework lives under [.omni-team/](.omni-team/) (`templates/`, `manifests/`, `lib/`, `bootstrap.py`, `orchestrator.py`). Running `bootstrap.py` renders agents into `.claude/agents/` at the repo root, which Claude Code auto-loads. See [README.md](README.md) for the consumer-facing intro and quick-start.

This file is the **workspace root** instruction. Sub-guides under [.omni-team/docs/](.omni-team/docs/) carry the deep rules — Claude Code auto-loads the nearest `CLAUDE.md`, but should follow links into `.omni-team/docs/` for any topic listed below.

## Critical Rules (must read)

See [.omni-team/docs/critical-rules.md](.omni-team/docs/critical-rules.md) for the full list. Top-3 invariants:

1. **Templates stay project-agnostic.** Anything stack-specific belongs in a manifest, never hardcoded in [`.omni-team/templates/*.md`](.omni-team/templates/).
2. **Decision matrix is data, not code.** Modify [`.omni-team/manifests/*.yaml`](.omni-team/manifests/), never branch on stacks/paths inside [`.omni-team/lib/decision.py`](.omni-team/lib/decision.py).
3. **Never auto-commit / auto-push from [`.omni-team/orchestrator.py`](.omni-team/orchestrator.py).** The human gate (Codex crosscheck → manual commit) is load-bearing.

## When to load which guide

| Trigger | Read |
|---|---|
| Touching [`.omni-team/templates/*.md`](.omni-team/templates/) or adding placeholders | [.omni-team/docs/manifest.md](.omni-team/docs/manifest.md) + [.omni-team/docs/critical-rules.md](.omni-team/docs/critical-rules.md) |
| Touching [`.omni-team/lib/decision.py`](.omni-team/lib/decision.py) or matrix predicates | [.omni-team/docs/decision-matrix.md](.omni-team/docs/decision-matrix.md) |
| Touching [`.omni-team/orchestrator.py`](.omni-team/orchestrator.py) / state machine / retry budget | [.omni-team/docs/architecture.md](.omni-team/docs/architecture.md) + [.omni-team/docs/workflow.md](.omni-team/docs/workflow.md) |
| Adding/changing an agent role | [.omni-team/docs/agents.md](.omni-team/docs/agents.md) + [.omni-team/docs/manifest.md](.omni-team/docs/manifest.md) |
| Onboarding a new project (writing a manifest) | [README.md](README.md) §Quick-start + [.omni-team/docs/manifest.md](.omni-team/docs/manifest.md) + [.omni-team/manifests/example.yaml](.omni-team/manifests/example.yaml) as reference |
| Anything before commit | [.omni-team/docs/definition-of-done.md](.omni-team/docs/definition-of-done.md) |
| Lines/function-size/complexity questions | [.omni-team/docs/code-quality.md](.omni-team/docs/code-quality.md) |
| "Where does X live?" | [.omni-team/docs/repository-layout.md](.omni-team/docs/repository-layout.md) |
| Full file map of when-to-read-what | [.omni-team/docs/when-to-load.md](.omni-team/docs/when-to-load.md) |

## Two ways to consume this baseline

**A) Clone-as-starting-point.** Use this repo as your project root. Write your manifest under `.omni-team/manifests/`, run `python .omni-team/bootstrap.py --manifest .omni-team/manifests/<your>.yaml`, develop normally. Bootstrap writes rendered agents into `.claude/agents/` at the repo root for Claude Code to auto-load.

**B) Vendored-into-existing-project.** Copy or git-submodule the `.omni-team/` directory into your existing project. Same commands. The bootstrap target stays `.claude/agents/` in the host project root, so Claude Code picks the rendered agents up automatically.

For deeper rationale see [.omni-team/docs/architecture.md](.omni-team/docs/architecture.md). For the full manifest schema see [.omni-team/docs/manifest.md](.omni-team/docs/manifest.md).
