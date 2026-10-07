---
name: omni-setup
description: One-time onboarding of omni-team to this repository — inspect the codebase and draft .omni-team/project/profile.yaml (components, stacks, commands, URLs, spec location) and .omni-team/project/conventions.md (architecture, invariants, per-role rules) from what the repo actually does, then optionally register the native sub-agents. Use after copying .omni-team/ into a project, or when the user says "omni-setup" or "set up the team".
---

# omni-setup — profile this project for the team

Goal: replace `auto` values with verified facts, so every role starts with accurate context. Everything you write must be backed by something you read in the repo; mark anything uncertain with `# TODO verify`.

1. **Survey** (read-only): root instruction files (`AGENTS.md`, `CLAUDE.md`, `README*`, `CONTRIBUTING*`), build manifests and task runners, CI workflows, container/compose files, top-level folder layout, test configs, migration folders, locale catalogues, docs/ADR folders.
2. **Draft `profile.yaml`** (edit `.omni-team/project/profile.yaml` in place, keep its comments):
   - `project.name`, `project.description` (2–3 sentences: what, stack, domain).
   - `work_unit.label` / `example_id` / `spec_root` — from how the repo tracks work (docs/specs, tickets in commit messages); `none` if there is no spec folder.
   - `components` — one entry per independently built part: `name`, `path`, `kind`, `stack` (with major versions), `commands` (setup/lint/typecheck/test/build/run — copy them from the task runner or CI, don't invent), `urls` for anything served.
   - `checks` — the repo-wide gate CI runs, if there is one.
   - Only add `signals` / `routing` overrides when the defaults clearly miss this repo's layout (e.g. migrations in an unusual folder).
3. **Draft `conventions.md`** — keep the section headings; fill each with rules you can point to in code or docs: layering and where code lives, error contract, naming, soft-delete/tenancy/idempotency invariants, i18n locales and catalogue paths, design system, auth guard helpers, PII fields, performance budgets, test layout, how to start the stack for smoke tests. Cite files (`see src/errors.ts`). Leave `(none)` where nothing applies.
4. **Validate** — if Python + PyYAML are available: `python3 .omni-team/orchestrator.py classify --task setup-check` must exit 0.
5. **Check registration** — if `.claude/agents/` / `.codex/agents/` lack the omni-team roles, tell the user to run the omni-team installer — `python3 <omni-team checkout>/.omni-team/install.py --dir <project>` (the checkout path is `source` in `.omni-team/.vendor.json`) (add `--tools all` for Gemini / generic `AGENTS.md`). Do not run it yourself unless asked.
6. **Report** — what you filled, what you inferred (with evidence), and the `TODO verify` items for the human.

Do not modify anything outside `.omni-team/project/`. Do not commit.
