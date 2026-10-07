# When to load which guide

## Using omni-team in a project

| Situation | Read |
|---|---|
| Running a task with the team | [../AGENTS.md](../AGENTS.md) (enough on its own) |
| First time in a repo | [../README.md](../README.md), then the `omni-setup` skill |
| Writing `profile.yaml` / `conventions.md` | [profile.md](profile.md) + [../examples/](../examples/) |
| A gate fires too often / not at all | [routing.md](routing.md) |
| Detailed flow, artifacts, retry budget, CI | [workflow.md](workflow.md) |
| What each role owns | [roles.md](roles.md) |
| Tool specifics (Claude, Codex, Gemini, others), engines | [adapters.md](adapters.md) |

## Changing the framework

| Situation | Read |
|---|---|
| Any change | [maintaining.md](maintaining.md) → [critical-rules.md](critical-rules.md) |
| Editing or adding a role | [roles.md](roles.md) + [critical-rules.md](critical-rules.md) §1, §10 |
| `lib/routing.py`, signals, predicates | [routing.md](routing.md) + [critical-rules.md](critical-rules.md) §2 |
| `lib/runner.py`, verdict tokens | [architecture.md](architecture.md) + [critical-rules.md](critical-rules.md) §4 |
| `install.py`, `lib/adapters.py` | [adapters.md](adapters.md) + [critical-rules.md](critical-rules.md) §8, §9 |
| `orchestrator.py`, state machine | [architecture.md](architecture.md) + [workflow.md](workflow.md) |
| Profile keys, conventions sections | [profile.md](profile.md) + [critical-rules.md](critical-rules.md) §10 |
| File approaching 500 lines | [code-quality.md](code-quality.md) |
| "Where does X live?" | [repository-layout.md](repository-layout.md) |
| Before declaring done | [definition-of-done.md](definition-of-done.md) |
