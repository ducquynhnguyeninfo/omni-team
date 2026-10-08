@AGENTS.md

## Claude Code specifics

- After the omni-team installer ran (`install.py --dir <project>` from the omni-team checkout; Claude Code is a default tool) the roles are native sub-agents (`.claude/agents/<role>.md`) and the workflows are skills (`/omni-setup`, `/omni-task`, `/omni-plan`, `/omni-review`, `/omni-ship`, `/ba`, `/architect`, `/pm`, `/release` in `.claude/skills/`). Do not edit those generated files — they are rebuilt on every install/upgrade.
- Invoke gates with the Agent tool, `subagent_type: "<role>"`. Launch all gates of **one stage** in the same message (they run in parallel); never mix stages — wait until a stage has passed before starting the next.
- Sub-agents return their report as text; **you** persist it with `python3 .omni-team/orchestrator.py record <role> --task <id> < report.md` (rotates long files, updates `_state.json`), or by hand per `.omni-team/AGENTS.md`.
- `smoke-tester` inherits all tools so it can use whatever browser MCP the project has configured (Chrome DevTools, Playwright, …).
- Model per tier (default deep→opus, standard→sonnet, fast→haiku) can be changed with the installer's `--claude-models deep=opus,standard=sonnet,fast=haiku`.
