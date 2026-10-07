# Workflow (host project)

How a project that vendors omni-team moves one work item from request to ship. The condensed version lives in [../AGENTS.md](../AGENTS.md); this file adds rationale and detail.

## Phases

```
Classify ─► Plan ─► Implement ─► Review ─► Accept ─► Hand off ─► HUMAN GATE
                         ▲          │         │
                         └─ fix ◄───┴─────────┘   REQUEST_CHANGES / BLOCK (≤ 3 rounds per gate)
```

| Phase | Who | Output |
|---|---|---|
| Classify | main agent (+ `orchestrator.py classify`) | task id, trivial vs non-trivial, gate list |
| Plan | `tech-lead` (+ `pm` TASKING for team delivery) | `runs/<id>/tech-lead.md` — phases, acceptance criteria, open questions; `runs/<id>/tasks/` — assignable tickets |
| Implement | main agent or human | code + green project checks |
| Review | routed gates, serially | `runs/<id>/<role>.md` per gate |
| Accept | `qa-lead`, then `smoke-tester` | acceptance table, smoke evidence |
| Hand off | main agent | `runs/<id>/_summary.md`, message to the human |
| Ship | **human only** | commit, push, merge |

## Project management (`pm`)

`pm` sits beside the pipeline, not in it: it is never routed as a gate. Use it

- after `tech-lead`, in **TASKING** mode, when the work is delivered by several people — it produces `runs/<id>/tasks/_board.md` (allocation, MECE traceability, critical path) and one file per ticket;
- on demand via the `pm` skill (`/pm` in Claude Code) for a charter, roadmap, status or weekly report, RAID review, backlog prioritisation or retrospective. Project-level artifacts go where `conventions.md` → *Project management* says, else `runs/pm/`.

Its status reports read gate verdicts in `runs/` as evidence, so the review pipeline doubles as the project's progress signal.

## Choosing a task id

Use the ticket/spec id when there is one (`PROJ-123`, `MP-04A`); otherwise a short kebab-case slug of the request. Allowed characters: letters, digits, `.`, `_`, `-`. The id names the artifacts folder and is how `qa-lead` finds the spec under `work_unit.spec_root`.

## Trivial vs non-trivial

Trivial (no plan, no gates): ≲15 changed lines, docs-only, formatting, or a pure rename — **and** nothing security-, data- or contract-related. Everything else goes through routing. When unsure, run `classify`: if it returns no gates, you are in trivial territory.

## Planning

`tech-lead` is not a review gate; it runs before code exists. Skip it only for small fixes whose shape is obvious. Its acceptance-criteria list becomes `qa-lead`'s fallback acceptance source when there is no spec, so it is worth running for any feature.

## Review gates

- **Serial, in `routing.order`.** Later gates read earlier reports (e.g. `qa-lead` checks that P0 test gaps were closed). Running them in parallel races on artifacts and produces inconsistent verdicts.
- **Fresh context per gate.** A sub-agent or separate process, not the implementer's own context — independence is the point. The in-session role-play fallback is allowed but must be flagged in the summary.
- **Persist verbatim.** Append each report to `runs/<id>/<role>.md` with a timestamp heading. Under the report, add an `### Actions taken by implementer` list: fixed / deferred (with reason) / disputed (with reason).

## Retry budget

| Event | Limit (default) | On limit |
|---|---|---|
| `REQUEST_CHANGES` on one gate | 3 | halt, append to `runs/<id>/_escapes.md`, escalate to the user |
| `BLOCK` on one gate | 3 | same |
| `NEEDS_CLARIFICATION` / `BLOCKED` | — | stop immediately, ask the user |

Hitting the budget means the direction or the scope is wrong — a human decision, not another loop. Budgets: `orchestrator.retry_budget` in [../defaults.yaml](../defaults.yaml), overridable in the profile.

## Artifacts

```
.omni-team/runs/<task-id>/
├── tech-lead.md          plan (append-only; re-plans append)
├── <role>.md             one file per gate, every attempt appended
├── smoke/                smoke-tester evidence (screenshots, logs)
├── _state.json           orchestrator state (gates, attempts, verdicts)
├── _summary.md           hand-off summary
└── _escapes.md           budget exhaustions
```

Per-role files keep each gate's history clean and let a later agent load just the report it needs. The folder location is `artifacts_dir` in the profile. Commit it for an audit trail, or add `.omni-team/runs/` to `.gitignore`.

## Orchestrator (headless)

`orchestrator.py` automates Review/Accept for terminals and CI: compute the diff, route, run each gate through an engine CLI (`claude -p`, `codex exec`, or your own), parse verdicts, persist state, enforce the budget, stop at the human gate.

| Command | Purpose |
|---|---|
| `classify --task <id>` | scope + matched rules + gate list; no AI calls |
| `run --task <id> [--fresh]` | run pending gates; resumes from `_state.json`; adds newly-routed gates |
| `run-gate <role> --task <id>` | force one gate |
| `status --task <id>` | print state |
| `prompt <role> --task <id>` | print the full prompt for a manual/fresh-session run |

Useful flags: `--engine`, `--base <ref>`, `--committed-only`, `--spec <path>`, `--request "<text>"`, `--dry-run`, `--timeout <s>`. Exit codes: 0 ready · 1 paused for fixes · 2 config error · 3 REQUEST_CHANGES budget · 4 BLOCK budget · 5 unparseable verdict · 6 needs a human.

CI sketch:

```yaml
- run: pip install -r .omni-team/requirements.txt
- run: python3 .omni-team/orchestrator.py run --task "pr-${{ github.event.number }}" --base "origin/${{ github.base_ref }}" --committed-only
  env: { ANTHROPIC_API_KEY: "${{ secrets.ANTHROPIC_API_KEY }}" }
```

## Learning loop

After each work item, note in your project's log which gates fired, what they caught, and what the human (or a second-tool cross-check) caught that they missed. Every few items, tune `conventions.md` (missed rules) and routing (gates that fire uselessly or not at all).
