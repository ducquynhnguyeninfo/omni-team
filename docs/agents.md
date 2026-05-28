# Agents — the 9-role review team

Each agent is a reviewer gate, not an author. They emit one of four verdicts (`APPROVE` / `REQUEST_CHANGES` / `BLOCK` / `NOT_APPLICABLE`) which the orchestrator regex-matches from stdout. See [architecture.md](architecture.md) §state-machine.

## Roster + when to invoke

| Role | Template | When the orchestrator schedules it |
|---|---|---|
| Tech Lead | [`tech-lead.md`](../.claude/templates/tech-lead.md) | **Start** of every non-trivial work unit — reads spec + companions + existing code, returns phased plan |
| DBA | [`dba.md`](../.claude/templates/dba.md) | After migration generation, **before applying** — downgrade reversibility, CHECK/enum DROP+ADD, partial indexes, drift |
| Senior BE Engineer | [`backend-reviewer.md`](../.claude/templates/backend-reviewer.md) | After BE code-complete + BE gate green, **before commit** — layer discipline, soft-delete, error contract, DTO discipline |
| Senior FE Engineer | [`frontend-reviewer.md`](../.claude/templates/frontend-reviewer.md) | After FE code-complete + FE gate green, **before commit** — i18n, type quality, component/hook patterns, proxy correctness, UI-lib constraint |
| QA Engineer | [`qa-engineer.md`](../.claude/templates/qa-engineer.md) | After implementation, **before commit** — untested error paths, state transitions, soft-delete behaviour, idempotency replays. For FE-touching MPs: also emits an E2E scenario list (E0 golden / E1 negative / E2 UI-only) |
| QA Lead | [`qa-lead.md`](../.claude/templates/qa-lead.md) | **End of MP** — acceptance-criteria walkthrough; verifies each E0/E1 scenario from `qa-engineer.md` has a spec; last technical gate before the human |
| UI Smoke Engineer | [`ui-smoke-engineer.md`](../.claude/templates/ui-smoke-engineer.md) | After `qa-lead` SHIP-READY, **before the human gate** — for any FE-touching MP. Drives a real browser; field parity vs wireframe + 1 golden-path interaction |
| Security Engineer | [`security-engineer.md`](../.claude/templates/security-engineer.md) | **Only when** diff touches auth, RBAC, RLS, PII, payment, cookies, JWT, or LLM prompt-injection surfaces |
| Performance Engineer | [`perf-engineer.md`](../.claude/templates/perf-engineer.md) | **Only when** a new endpoint is added or a query path changes — classify tier, flag N+1, missing index, idempotency |

The orchestrator picks this set automatically from the diff + the manifest's `decision_matrix:`. See [decision-matrix.md](decision-matrix.md).

## What stays human (NOT delegated)

- Scope decisions (split MP, drop a feature, change acceptance criteria)
- Codex crosscheck verdict
- Any agent emitting `BLOCK` on the 3rd retry — escalate, don't loop
- Final `git commit` and `git push`

## Adding a new agent

1. Drop a new template under [`.claude/templates/<role>.md`](../.claude/templates/). Use existing templates as the structural model: role intro → process → verdict block format.
2. Reference Layer-3 facts via `{{dotted.path}}` placeholders (see [manifest.md](manifest.md)).
3. Add a corresponding entry under `models:`, `project_rules:`, and (if scheduling logic changes) `decision_matrix:` in [`.claude/manifests/_starter.yaml`](../.claude/manifests/_starter.yaml).
4. Add an `artifact_dir` convention entry (the per-agent file name under `agent-pow/<MP-ID>/`).
5. Update this file's table.
6. Test by rendering against [`.claude/manifests/centvra.yaml`](../.claude/manifests/centvra.yaml) and checking the output is sensible.

## Artifact discipline

Every invocation appends verbatim output to the per-agent file under the work unit's `agent-pow/` folder. Per-agent files (not a monolithic gates log) so:

- Each gate's audit history stays uncontaminated.
- Token-conscious re-loads can pull just one agent's history.
- Re-runs accumulate as new entries rather than diluting.

Each entry: timestamp, agent ID, token count, duration, verbatim output, plus an "Actions taken by main agent" section noting fixed vs deferred findings.
