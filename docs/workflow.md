# Workflow

This file describes the 5-phase workflow that *host projects* follow when using omni-team. For the workflow of **working on omni-team itself**, see [definition-of-done.md](definition-of-done.md).

## 5-phase workflow (host project)

Every change goes through **Classify → Plan → Execute → Review → Ship**. Which gates run in Review depends on the diff and the manifest's [decision matrix](decision-matrix.md).

1. **Classify**
   - Human + main Claude consult the matrix.
   - Run `python orchestrator.py classify --mp <id> --base <ref>` to preview the gate sequence.

2. **Plan**
   - For non-trivial work units: spawn `tech-lead` first. Returns phased plan.
   - For trivial work (typo, rename): main Claude inline.

3. **Execute**
   - Main Claude implements layer-by-layer per plan.
   - Use stack-specific slash commands (defined per host project, not by omni-team).

4. **Review** (gates fire serially — never in parallel; they read disk state)
   - `python orchestrator.py run --mp <id> --base <ref>` runs the full sequence.
   - Schema touched → `dba`
   - BE code → `qa-engineer` → `backend-reviewer` → `perf-engineer` (if new endpoint) → BE test gate
   - FE code → FE test gate → `frontend-reviewer`
   - Security-sensitive surface → `security-engineer`
   - End of MP → `qa-lead` (acceptance-criteria walkthrough)
   - FE-touching MP → `ui-smoke-engineer` after `qa-lead` SHIP-READY

5. **Ship** (HUMAN ONLY)
   - User runs Codex crosscheck.
   - User runs `git commit` + `git push`.
   - The orchestrator **never** auto-commits. See [critical-rules.md](critical-rules.md) §5.

## Retry budget

Three `BLOCK` verdicts on the same scope → halt, append to `_post-ship-escapes.md`, escalate to user.

Three `REQUEST_CHANGES` verdicts in a row on the same gate → halt with the same escape log; do not loop. The fix is wrong direction or scope is too large — both need human judgement.

Default budgets in [`manifests/_starter.yaml`](../manifests/_starter.yaml) under `orchestrator:`. Tunable per project.

## Decision matrix — quick reference

| Change type | LoC | Gates (typical) |
|---|---|---|
| Typo / rename / docs | <20 | test gate only |
| Bug fix, single file, no DB | <100 | one reviewer (per stack) → gate |
| New endpoint, existing tables | 100–500 | `qa-engineer` → `backend-reviewer` → `perf-engineer` → gate |
| New table + endpoint | 200–800 | `dba` → `qa-engineer` → `backend-reviewer` → `perf-engineer` → gate |
| Full-stack MP | 500–2000 | `tech-lead` → full 5-phase → `ui-smoke-engineer` |
| Any MP touching FE | any | + `qa-engineer` E2E list → `qa-lead` coverage check → `ui-smoke-engineer` after SHIP-READY |
| Touches auth / RBAC / PII / payment | any | + `security-engineer` mandatorily |

This is the *default*. Host projects override via their manifest's `decision_matrix:`.

## Outcomes logging

After each MP, append a brief entry to the project's outcomes log:

- Which agents fired
- Which blocked / requested changes
- Total token cost
- Any Codex catches the agents missed

Review every 5 MPs to tune the matrix and per-agent rules.

## Working on omni-team itself

Different workflow — there are no "MPs" here. See [definition-of-done.md](definition-of-done.md) for the checklist that applies to changes inside this repo.
