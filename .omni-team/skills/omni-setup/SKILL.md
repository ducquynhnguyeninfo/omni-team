---
name: omni-setup
description: One-time onboarding of omni-team to this repository — install the toolset into .omni-team/.venv, inspect the codebase and draft .omni-team/project/profile.yaml (components, stacks, commands, URLs, spec location) and .omni-team/project/conventions.md (architecture, invariants, per-role rules) from what the repo actually does, then optionally register the native sub-agents. Use after copying .omni-team/ into a project, or when the user says "omni-setup" or "set up the team".
---

# omni-setup — profile this project for the team

Goal: replace `auto` values with verified facts, so every role starts with accurate context. Everything you write must be backed by something you read in the repo; mark anything uncertain with `# TODO verify`.

1. **Install the toolset** — run it yourself, never hand it to the user: `python3 .omni-team/orchestrator.py setup`, with `--ui-probe` when the project serves a browser UI (a web framework in its manifests; if step 2 turns one up later, re-run with the flag). It creates `.omni-team/.venv` (git-ignored, kept on upgrade): the Python environment every orchestrator command then runs under, and with `--ui-probe` Playwright plus a browser for `smoke-tester`'s layout probe. Each part prints ✅ or ❌ with the reason. Re-running is safe and fast. A ❌ you cannot fix (no Python 3.8+, no network, no Node.js for the probe) goes into the report with its output; carry on with the other steps.
2. **Survey** (read-only): root instruction files (`AGENTS.md`, `CLAUDE.md`, `README*`, `CONTRIBUTING*`), build manifests and task runners, CI workflows, container/compose files, top-level folder layout, test configs, migration folders, locale catalogues, docs/ADR folders.
3. **Layout — ask when it is not settled.** If the repo has no product code yet, or its layout is not recorded anywhere, ask the user before drafting where code and documents should live:
   - **workspace** (recommended when product code is delivered to a client or another team; see `.omni-team/docs/workspace.md`): the root holds agent tooling and working documents, each product repository is its own git repo in a folder such as `codebase/<repo>/`, documents in a folder such as `document/`;
   - **single repository**: code at the root.

   Record the answer as a rule in `conventions.md` → `Architecture` (folder names, which folders are separate repositories, where specs, ADRs and PM documents go) and as component `path`s in the profile, so `architect` and `tech-lead` build into it instead of choosing again.
4. **Draft `profile.yaml`** (edit `.omni-team/project/profile.yaml` in place, keep its comments):
   - `project.name`, `project.description` (2–3 sentences: what, stack, domain).
   - `work_unit.label` / `example_id` / `spec_root` — from how the repo tracks work (docs/specs, tickets in commit messages); `none` if there is no spec folder.
   - `components` — one entry per independently built part: `name`, `path`, `kind`, `stack` (with major versions), `commands` (setup/lint/typecheck/test/build/run — copy them from the task runner or CI, don't invent), `urls` for anything served.
   - `checks` — the repo-wide gate CI runs, if there is one.
   - Only add `signals` / `routing` overrides when the defaults clearly miss this repo's layout (e.g. migrations in an unusual folder).
   - `automation` — **ask the user** which level the agent gets, and write it: `pr_fix: "off"` (default — commit/push only when asked), `commit` (commit its own fixes on the work branch), or `push` (commit and push them to its work branch and open the pull request; recommend only with a pull-request flow and server-side protection of the default branch). At every level the agent never commits or pushes to the default or a protected branch. Add `protected_branches` when the repo has long-lived branches beyond `main`/`master`/`develop`/`release/*`/`hotfix/*`, and `branch_prefix` when the team names work branches other than `omni/<task-id>`. Merge stays human at every level; see `.omni-team/docs/automation.md`. If the project runs in production and wants metrics to start the flow, mention the optional `project/bands.yaml`; do not create it unasked.
5. **Draft `conventions.md`** — keep the section headings; fill each with rules you can point to in code or docs: layering and where code lives, error contract, naming, soft-delete/tenancy/idempotency invariants, i18n locales and catalogue paths, design system, auth guard helpers, PII fields, performance budgets, test layout, how to start the stack for smoke tests. Cite files (`see src/errors.ts`). Leave `(none)` where nothing applies.
6. **Validate** — run `python3 .omni-team/orchestrator.py classify --task setup-check` yourself; it must exit 0. A profile error → fix the profile and re-run.
7. **Check registration** — if `.claude/agents/` / `.codex/agents/` lack the omni-team roles, offer to run the omni-team installer — `/omni-team:install` when the omni-team Claude Code plugin is installed, otherwise `python3 <omni-team checkout>/.omni-team/install.py --dir <project>` (the checkout path is `source` in `.omni-team/.vendor.json`; add `--tools all` for Gemini / generic `AGENTS.md`). It writes outside `.omni-team/` (`.claude/`, `.codex/`, `.agents/`, pointer blocks in root instruction files), so ask first; on a yes, run it yourself.
8. **Report** — the toolset lines from step 1, what you filled, what you inferred (with evidence), and the `TODO verify` items for the human.

Do not modify anything outside `.omni-team/project/` (the toolset in `.omni-team/.venv` excepted). Do not commit.
