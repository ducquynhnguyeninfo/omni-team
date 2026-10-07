# Roles

Each role is one Markdown file in [`../team/`](../team/) plus the shared [`../team/_protocol.md`](../team/_protocol.md). Roles are **stack-agnostic**: they hold the *role* (who you are) and the *process* (how you review and report). Project facts come from [`../project/`](../project/) at run time; stack idioms come from the model's own expertise, applied through the protocol's "stack lens".

## Roster

| Role | Phase | Owns | Tier | Access |
|---|---|---|---|---|
| [`pm`](../team/pm.md) | Coordinate (on demand) | scope, schedule, RAID, prioritisation, ticket decomposition (TASKING), status/weekly reports | deep | read-only |
| [`tech-lead`](../team/tech-lead.md) | Plan | phased plan, acceptance criteria, sequencing, open questions | deep | read-only |
| [`data-reviewer`](../team/data-reviewer.md) | Review | migrations, data models, persisted/wire formats | standard | read-only |
| [`code-reviewer`](../team/code-reviewer.md) | Review | correctness, boundaries, conventions, idioms, UI code quality | standard | read-only |
| [`test-engineer`](../team/test-engineer.md) | Review | missing tests for changed behaviour (P0/P1/P2), E2E scenario list | standard | read-only |
| [`security-engineer`](../team/security-engineer.md) | Review | authN/Z, secrets, injection, PII, supply chain | standard | read-only |
| [`perf-engineer`](../team/perf-engineer.md) | Review | tiers/budgets, query and I/O patterns, resource use | standard | read-only |
| [`qa-lead`](../team/qa-lead.md) | Accept | acceptance criteria vs implementation and tests | deep | read-only |
| [`smoke-tester`](../team/smoke-tester.md) | Accept | running the change for real, evidence | standard | run |

`tier` maps to a model per tool (Claude: opus/sonnet/haiku; Codex: reasoning effort high/medium/low) — see [adapters.md](adapters.md). `access: run` lets the role execute the app and write evidence under the artifacts folder; every other role is read-only.

## What stays human

- Scope decisions: splitting a work item, dropping a requirement, changing acceptance criteria.
- Disputed findings and anything that exhausts the retry budget.
- Authorization *policy* (who may do what) — roles flag ambiguity, they do not invent policy.
- Commit, push, merge, release.

## Role file format

```markdown
---
name: code-reviewer            # must equal the file name
description: One paragraph: what the role does and WHEN to invoke it (tools use this to auto-select).
tier: standard                 # deep | standard | fast
access: read-only              # read-only | run
---

# Role: …
Purpose, inputs, checklist with stable ids (CR-1 …), output template ending with the VERDICT line, "do not" list.
```

The frontmatter is deliberately flat `key: value` so `install.py` can parse it with the standard library.

## Writing rules for role files

1. **No stack names in rules.** Say "data-access layer", "entry point", "UI string catalogue", "migration tool" — not "repository class", "FastAPI router", "next-intl", "Alembic". Examples in parentheses are fine when they span several stacks.
2. **Stable rule ids** (`CR-3`, `SE-11`). Findings cite them; renumbering breaks audit trails, so append new ids.
3. **Project rules are pulled, not pasted.** Point to the `conventions.md` section the role reads (`conventions.md → Security`). Never hard-code a project's rule into a role.
4. **Every role ends with the protocol's `VERDICT:` line** and uses only the tokens listed there.
5. **Ownership is exclusive.** If a check belongs to another role (see the protocol's table), reference it in one line instead of duplicating it.

## Adding a role

1. Create `team/<name>.md` with the frontmatter above. Model it on the closest existing role.
2. Add it to the ownership table in `team/_protocol.md` and to the roster tables here and in `../AGENTS.md` / `../README.md`.
3. Add it to a stage in `routing.stages` in `../defaults.yaml` (same stage as the gates it is independent of) and to at least one routing rule (or document that it is invoked manually).
4. Add a `conventions.md` section name for it in `../project/conventions.md` and the examples if it reads project rules.
5. `python3 .omni-team/install.py --dry-run` must list it; run `python3 -m unittest discover -s .omni-team/tests`.

## Removing or renaming a role

Update the same places. `install.py` automatically removes generated files for roles that no longer exist (it only deletes files carrying its marker).
