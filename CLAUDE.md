# CLAUDE.md

**omni-team** — the baseline automated-agent coding repo. The whole framework lives under [.claude/](.claude/) so any project that copies (or starts from) this repo gets the 9-role reviewer team plus orchestrator out of the box. See [README.md](README.md) for the consumer-facing intro and quick-start.

This file is the **workspace root** instruction. Sub-guides under [docs/](docs/) carry the deep rules — Claude Code auto-loads the nearest `CLAUDE.md`, but should follow links into `docs/` for any topic listed below.

## Critical Rules (must read)

See [docs/critical-rules.md](docs/critical-rules.md) for the full list. Top-3 invariants:

1. **Templates stay project-agnostic.** Anything stack-specific belongs in a manifest, never hardcoded in [`.claude/templates/*.md`](.claude/templates/).
2. **Decision matrix is data, not code.** Modify [`.claude/manifests/*.yaml`](.claude/manifests/), never branch on stacks/paths inside [`.claude/lib/decision.py`](.claude/lib/decision.py).
3. **Never auto-commit / auto-push from [`.claude/orchestrator.py`](.claude/orchestrator.py).** The human gate (Codex crosscheck → manual commit) is load-bearing.

## When to load which guide

| Trigger | Read |
|---|---|
| Touching [`.claude/templates/*.md`](.claude/templates/) or adding placeholders | [docs/manifest.md](docs/manifest.md) + [docs/critical-rules.md](docs/critical-rules.md) |
| Touching [`.claude/lib/decision.py`](.claude/lib/decision.py) or matrix predicates | [docs/decision-matrix.md](docs/decision-matrix.md) |
| Touching [`.claude/orchestrator.py`](.claude/orchestrator.py) / state machine / retry budget | [docs/architecture.md](docs/architecture.md) + [docs/workflow.md](docs/workflow.md) |
| Adding/changing an agent role | [docs/agents.md](docs/agents.md) + [docs/manifest.md](docs/manifest.md) |
| Onboarding a new project (writing a manifest) | [README.md](README.md) §Quick-start + [docs/manifest.md](docs/manifest.md) + [.claude/manifests/example.yaml](.claude/manifests/example.yaml) as reference |
| Anything before commit | [docs/definition-of-done.md](docs/definition-of-done.md) |
| Lines/function-size/complexity questions | [docs/code-quality.md](docs/code-quality.md) |
| "Where does X live?" | [docs/repository-layout.md](docs/repository-layout.md) |
| Full file map of when-to-read-what | [docs/when-to-load.md](docs/when-to-load.md) |

## Two ways to consume this baseline

**A) Clone-as-starting-point.** Use the repo itself as your project root — everything in [.claude/](.claude/) is already there. Write your manifest, run `python .claude/bootstrap.py --manifest .claude/manifests/<your>.yaml`, develop normally.

**B) Vendored-into-existing-project.** Copy or git-submodule the [.claude/](.claude/) directory into your existing project. Same commands. The directory is intentionally named `.claude/` so Claude Code picks up rendered agents from [`.claude/agents/`](#) automatically once `bootstrap.py` runs.

For deeper rationale see [docs/architecture.md](docs/architecture.md). For the full manifest schema see [docs/manifest.md](docs/manifest.md).
