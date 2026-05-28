# When to load which guide

Quick triggers → which file holds the answer. The same table is mirrored (shorter) at the root of [CLAUDE.md](../CLAUDE.md).

## Working on omni-team itself

| Trigger | Read |
|---|---|
| Adding a new agent role | [agents.md](agents.md) §adding-a-new-agent + [manifest.md](manifest.md) §adding-a-new-placeholder |
| Editing [`templates/*.md`](../templates/) (any agent prompt) | [critical-rules.md](critical-rules.md) §1, §6 + [manifest.md](manifest.md) |
| Touching [`lib/decision.py`](../lib/decision.py) or matrix predicates | [decision-matrix.md](decision-matrix.md) + [critical-rules.md](critical-rules.md) §2 |
| Touching [`lib/runner.py`](../lib/runner.py) (verdict parsing) | [architecture.md](architecture.md) §state-machine + [critical-rules.md](critical-rules.md) §4 |
| Touching [`orchestrator.py`](../orchestrator.py) (CLI / state file) | [architecture.md](architecture.md) §state-machine + [workflow.md](workflow.md) |
| Touching [`bootstrap.py`](../bootstrap.py) (placeholder substitution) | [manifest.md](manifest.md) §placeholder-syntax + [critical-rules.md](critical-rules.md) §3 |
| Adding a new manifest section / key | [manifest.md](manifest.md) §adding-a-new-placeholder |
| Changing the retry budget / state machine | [architecture.md](architecture.md) §state-machine + [workflow.md](workflow.md) §retry-budget |
| File getting close to 500 lines | [code-quality.md](code-quality.md) §split-strategies |
| Anything before commit | [definition-of-done.md](definition-of-done.md) |
| "Where does X live?" | [repository-layout.md](repository-layout.md) |

## Adopting omni-team in a new project

| Trigger | Read |
|---|---|
| First-time onboarding — writing a manifest | [README.md](../README.md) §Quick-start + [manifest.md](manifest.md) + [`examples/`](../examples/) |
| Choosing which agents to enable | [agents.md](agents.md) |
| Tuning which agents fire on which diff | [decision-matrix.md](decision-matrix.md) |
| Tuning per-agent extra rules | [manifest.md](manifest.md) §project_rules + [agents.md](agents.md) |
| Running the orchestrator locally / in CI | [workflow.md](workflow.md) + [README.md](../README.md) §CI |

## "I just want to fix one thing"

Single-file changes don't need a full read-through. Suggested minimum:

- **Editing a single template** — skim [critical-rules.md](critical-rules.md) §1, §6. Render against example.yaml + one other manifest before declaring done.
- **Editing a single `lib/` function** — skim [code-quality.md](code-quality.md). Type-check the public surface.
- **Editing the README** — no extra reads, but confirm links resolve.
- **Adding an example manifest** — [manifest.md](manifest.md) + copy [`_starter.yaml`](../manifests/_starter.yaml).
