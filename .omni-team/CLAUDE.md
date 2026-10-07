@AGENTS.md

## Claude Code specifics

- After `python3 .omni-team/install.py --tools claude` the roles are native sub-agents (`.claude/agents/<role>.md`) and the workflows are skills (`/omni-setup`, `/omni-task`, `/omni-plan`, `/omni-review`, `/omni-ship`, `/ba`, `/architect`, `/pm`, `/release` in `.claude/skills/`). Re-run the installer after editing anything in `team/` or `skills/`.
- Invoke gates with the Agent tool, `subagent_type: "<role>"`. Launch all gates of **one stage** in the same message (they run in parallel); never mix stages — wait until a stage has passed before starting the next.
- Sub-agents return their report as text; **you** append it to `.omni-team/runs/<task-id>/<role>.md`.
- `smoke-tester` inherits all tools so it can use whatever browser MCP the project has configured (Chrome DevTools, Playwright, …).
- Model per tier (default deep→opus, standard→sonnet, fast→haiku) can be changed with `install.py --claude-models deep=opus,standard=sonnet,fast=haiku`.
