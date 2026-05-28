# Architecture

omni-team has two orthogonal pieces: a **template/manifest renderer** ([`.claude/bootstrap.py`](../.claude/bootstrap.py)) and an **orchestrator state machine** ([`.claude/orchestrator.py`](../.claude/orchestrator.py)). They share a [`.claude/lib/`](../.claude/lib/) core but can be used independently.

## 3-layer model

Every agent prompt mixes three concerns. omni-team separates them so the same role definition can run against different projects.

| Layer | What it captures | Where it lives | Edit when |
|---|---|---|---|
| **1 — Role** | "You are the Senior BE Engineer doing peer review." | [`.claude/templates/*.md`](../.claude/templates/) | Adding/removing an agent role |
| **2 — Process** | "Identify scope → apply rules → emit verdict block." | [`.claude/templates/*.md`](../.claude/templates/) | Changing the review workflow |
| **3 — Project conventions** | "Error shape is `LeanApiError`. Soft-delete via `deleted_at`." | [`.claude/manifests/<project>.yaml`](../.claude/manifests/) | Onboarding a new project, or facts changed |

Templates reference Layer-3 keys with `{{dotted.path}}`. At bootstrap time `.claude/bootstrap.py` reads the manifest, substitutes every placeholder, and writes the resolved agent prompt into `.claude/agents/` — exactly where Claude Code expects to load agents from. See [manifest.md](manifest.md) for the placeholder syntax.

## Bootstrap flow

```
.claude/manifests/<project>.yaml      .claude/templates/<agent>.md
        │                                       │
        ▼                                       ▼
   .claude/lib/manifest.py  ──────────►   .claude/lib/render.py
        (load + dotted lookup)              ({{key}} → value, missing-key report)
                                                 │
                                                 ▼
                                       .claude/agents/<agent>.md
                                       (auto-loaded by Claude Code)
```

Failure modes:
- Missing key in manifest → `.claude/bootstrap.py` exits non-zero, lists every unresolved `{{path}}`.
- Manifest YAML invalid → fail fast with line number.
- Output directory not writable → fail fast.

## Orchestrator state machine

```
classify  →  review (gates loop)  →  ready_for_human  →  HUMAN GATE
                ↑   ↓
                │   REQUEST_CHANGES → pause, engineer fixes, re-run
                │   BLOCK x3       → halt, log to _post-ship-escapes.md
                │
                APPROVE / NOT_APPLICABLE → next gate
```

- `classify` reads the diff, evaluates the manifest's `decision_matrix:`, prints the gate sequence — no agent invocations.
- `run` walks that sequence serially, invoking each agent via `claude -p` (Layer 1+2 prompt rendered with Layer 3 facts), parses the verdict from stdout, persists `GateState` to `_state.json`.
- `run-gate <agent>` force-runs a single named gate (bypasses classification).
- `status` pretty-prints the current `_state.json`.

Verdict regex (in [`.claude/lib/runner.py`](../.claude/lib/runner.py)) is fixed for now — see [critical-rules.md](critical-rules.md) §4.

## State file

`_state.json` lives next to the agent artifacts under `agent-pow/<MP-ID>/` and holds:

- Per-gate verdict (`APPROVE` / `REQUEST_CHANGES` / `BLOCK` / `NOT_APPLICABLE` / `PENDING`)
- Per-gate retry count (against `orchestrator.retry_budget`)
- Pointer to verbatim agent output file
- Terminal state (`ready_for_human` or `halted`)

Reset with `--fresh`. Inspect with `python .claude/orchestrator.py status`.

## Why sequential gates

Reviewer agents read disk state — `qa-lead.md` references the previous agents' verdicts under `agent-pow/<MP-ID>/`. Running in parallel would race on the artifact files and produce non-deterministic verdicts. The orchestrator enforces serial execution; do not work around this. See [critical-rules.md](critical-rules.md) §8.

## Why no DEV agent

omni-team is a **reviewer** team, not an agile loop. Code authoring is done by the main Claude session or a human, working from the reviewers' findings. This is a deliberate departure from older "agile loop" agent setups — see [README.md](../README.md) §Differences-vs-legacy.
