@AGENTS.md

## Claude Code specifics

- After the omni-team installer ran (`install.py --dir <project>` from the omni-team checkout; Claude Code is a default tool) the roles are native sub-agents (`.claude/agents/<role>.md`) and the workflows are skills (`/omni-setup`, `/omni-task`, `/omni-plan`, `/omni-review`, `/omni-ship`, `/ba`, `/architect`, `/pm`, `/release` in `.claude/skills/`). Do not edit those generated files — they are rebuilt on every install/upgrade.
- Invoke gates with the Agent tool, `subagent_type: "<role>"`. Launch all gates of **one stage** in the same message (they run in parallel); never mix stages — wait until a stage has passed before starting the next.
- Sub-agents return their report as text; **you** persist it with `python3 .omni-team/orchestrator.py record <role> --task <id> < report.md` (rotates long files, updates `_state.json`), or by hand per `.omni-team/AGENTS.md`.
- Implementer work (AGENTS.md §5): dispatch it with the Agent tool — general-purpose with the work order, or a fork when it needs this conversation's context. It runs in the background, so the session stays open; you are notified when it finishes, so do not poll. Parallel writers: `isolation: "worktree"`. Long commands (test suites, Gate 0, dev servers): Bash `run_in_background`.
- Before committing or pushing anything the user did not ask for, run `python3 .omni-team/orchestrator.py automation --task <id> --action commit|push` (AGENTS.md §8); exit 6 means don't — on the default or a protected branch it prints the way forward (work branch, push, pull request). Even when the user asks, never commit or push to the default or a protected branch: take that way forward and say so. Organisations can enforce the same limits with managed settings (`docs/automation.md`).
- `smoke-tester` inherits all tools so it can use whatever browser MCP the project has configured (Chrome DevTools, Playwright, …).
- Model per tier (default deep→opus, standard→sonnet, fast→haiku) can be changed with the installer's `--claude-models deep=opus,standard=sonnet,fast=haiku`.
