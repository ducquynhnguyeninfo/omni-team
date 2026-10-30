---
name: upgrade
description: Upgrade the omni-team copy in the current workspace to the plugin's version — replace the framework files in .omni-team/ (project/ and runs/ are kept), re-register its sub-agents and skills, and refresh the toolset. Use when the user says "upgrade omni-team", "update the review team", "update omni-team to the latest version", or after updating the omni-team plugin.
argument-hint: "[--tools claude,codex,gemini,agents-md|all]"
---

# upgrade — bring this workspace's omni-team up to date

Run each command yourself; never hand the user a command you can run. Arguments: `$ARGUMENTS`.

1. **Find the workspace** — `git rev-parse --show-toplevel` from the current directory. If `<workspace>/.omni-team/` does not exist, follow the plugin's `install` skill instead.
2. **Get the latest plugin** — `claude plugin marketplace update omni-team`, then `claude plugin update omni-team@omni-team`. An update installs the new version beside the one this session loaded, so read the installed path from `claude plugin list --json` (the `omni-team@omni-team` entry's install path) and use it as `<plugin>` below. When the `claude` command is missing or either step fails, use `<plugin>` = `${CLAUDE_PLUGIN_ROOT}` and say that the plugin itself was not refreshed.
3. **Compare versions** — `<workspace>/.omni-team/VERSION` against `<plugin>/.omni-team/VERSION`. Equal: say it is already current and go to step 5. Plugin older: stop; a downgrade needs the user's explicit yes, then `--force`.
4. **Upgrade** — `python3 "<plugin>/.omni-team/install.py" upgrade --dir "<workspace>"`, adding `--tools <list>` when the user named tools or the workspace already has adapters beyond Claude Code and Codex (`GEMINI.md` pointer → include `gemini`). It replaces the framework files, removes files the new version no longer ships, keeps `project/`, `runs/` and `.venv/`, and rewrites the generated sub-agents and skills.
5. **Toolset** — `python3 "<workspace>/.omni-team/orchestrator.py" setup`, adding `--ui-probe` when `<workspace>/.omni-team/.venv/node` exists. Then `python3 "<workspace>/.omni-team/orchestrator.py" classify --task upgrade-check`; it must exit 0. A profile error means the new version reads `project/profile.yaml` differently: check the upgrade notes in the framework's `docs/maintaining.md` (shipped in the plugin at `<plugin>/.omni-team/docs/maintaining.md`) and fix the profile.
6. **Report** — old → new version, the added/updated/removed counts, the toolset lines, and anything the upgrade notes ask of the project. Tell the user to start a new session so the regenerated sub-agents load, and to review and commit the changes; do not commit yourself.
