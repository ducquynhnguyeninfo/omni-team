# .omni-team — Portable, Auto-Runnable Review-Gate Team

A port of the Centvra `.claude/agents/` 9-role team into a project-agnostic
framework. Two improvements over the original:

1. **Portable** — agent prompts are templated; project-specific facts live in a
   YAML manifest. Switch projects by swapping the manifest.
2. **Auto-runnable** — an orchestrator picks the right agents for a given diff,
   runs them headless via `claude -p`, retries on `REQUEST_CHANGES`, halts on
   `BLOCK` after a retry budget, and stops at the human gate (Codex
   crosscheck). No agent ever auto-commits.

```
.omni-team/
├── templates/           ← Layer 1+2: universal role + process (9 agents)
├── manifests/
│   ├── centvra.yaml     ← Layer 3: this project's facts
│   └── _starter.yaml    ← copy-paste skeleton for new projects
├── examples/
│   ├── django-postgres.yaml
│   └── nextjs-prisma.yaml
├── lib/                 ← manifest, render, decision, state, runner
├── bootstrap.py         ← render templates + manifest → .claude/agents/
├── orchestrator.py      ← classify → invoke gates → state machine
└── README.md
```

## Quick start (Centvra)

```bash
# 1. Render the agents (writes to .claude/agents/)
python .omni-team/bootstrap.py

# 2. See which gates would run for the current branch's diff
python .omni-team/orchestrator.py classify \
    --mp MP-A06 --sprint 4 --base origin/main

# 3. Run the full pipeline
python .omni-team/orchestrator.py run \
    --mp MP-A06 --sprint 4 --base origin/main

# 4. Inspect state any time
python .omni-team/orchestrator.py status --mp MP-A06 --sprint 4
```

## Quick start (another project)

```bash
# 1. Copy the starter manifest
cp .omni-team/manifests/_starter.yaml .omni-team/manifests/myapp.yaml

# 2. Fill every TODO_* in myapp.yaml
$EDITOR .omni-team/manifests/myapp.yaml

# 3. Render
python .omni-team/bootstrap.py --manifest .omni-team/manifests/myapp.yaml

# 4. Use orchestrator with the same manifest
python .omni-team/orchestrator.py run \
    --manifest .omni-team/manifests/myapp.yaml \
    --mp PR-101 --base main
```

See `examples/django-postgres.yaml` and `examples/nextjs-prisma.yaml` for
filled-in references.

---

## How the 3-layer model works

Every original agent prompt mixed three things. `.omni-team/` splits them:

| Layer | What it captures | Where it lives |
|---|---|---|
| **1 — Role** | "You are the Senior Backend Engineer doing peer review." | `templates/*.md` (hardcoded) |
| **2 — Process** | "Identify scope → apply rules → emit verdict block." | `templates/*.md` (hardcoded) |
| **3 — Project conventions** | "Error shape is `LeanApiError`. Soft-delete via `deleted_at`." | `manifests/<project>.yaml` (injected) |

Templates reference layer-3 keys with `{{dotted.path}}`. At bootstrap time
`bootstrap.py` reads the manifest, substitutes every placeholder, and writes
the resolved agent file into `.claude/agents/`.

---

## Manifest reference

The manifest is a single YAML file with these top-level sections (see
`manifests/centvra.yaml` for a fully-populated example):

| Section | Purpose |
|---|---|
| `project` | Name, short_name, description |
| `work_unit_label` | Vocabulary: "Mini Package", "Story", "Ticket", … |
| `spec_root` | Where specs live, passed to tech-lead/qa-lead |
| `artifact_dir` | Where each agent's verbatim output is appended |
| `models` | Claude model per agent (opus / sonnet / haiku) |
| `quality_limits` | File/function/param/depth caps used by reviewers |
| `backend` | Stack, paths, layer rules, error contract, soft-delete |
| `frontend` | Stack, paths, locales, i18n hook, UI lib, proxy helper |
| `database` | Engine, migration tool + commands, RLS file |
| `llm` | Enabled/disabled + provider config |
| `conventions` | Idempotency helper, audit fields |
| `performance` | Tier table + baseline doc |
| `security` | Trigger paths, PII fields, cookie flags |
| `cross_cutting_invariants_md` | Universal rules surfaced by tech-lead |
| `project_rules` | Per-agent extra rules (use `(none)` if empty) |
| `decision_matrix` | Base rules + add_if overlays (data, not code) |
| `orchestrator` | Retry budgets, spawn mode, state file, human gate |

### Placeholder syntax

Templates use Mustache-style placeholders:

```
{{backend.error_contract.name}}      ← scalar
{{cross_cutting_invariants_md}}      ← multi-line markdown block
{{performance.tier_table_md}}        ← pre-rendered table
```

Missing keys are NOT silent — `bootstrap.py` reports them. If a key is
intentionally empty, set it to the literal string `(none)`.

---

## Decision matrix

The matrix in `manifests/<project>.yaml` is data, not code. It has two parts:

```yaml
decision_matrix:
  base:                    # first matching rule wins
    - name: bug-fix-be
      when: { loc_max: 100, stacks: ["backend"], schema_change: false }
      agents: ["backend-reviewer"]
    # …
  add_if:                  # every matching rule appends agents
    - when: { stacks: ["frontend"] }
      agents_add: ["ui-smoke-engineer"]
    - when:
        path_globs: ["**/auth*"]
        keywords: ["password", "token"]
      agents_add: ["security-engineer"]
```

Predicates supported on `when`:

| Key | Meaning |
|---|---|
| `loc_max`, `loc_min` | Lines of added code in the diff |
| `stacks` | Subset of `{backend, frontend, database}` |
| `new_route` | A new `@router.<verb>` (or framework equivalent) appears |
| `schema_change` | A new file appears under the migration versions dir |
| `path_globs` | fnmatch glob list — any changed path matches |
| `keywords` | Any keyword appears (case-insensitive) in the diff text |
| `pii_fields` | Any of these PII field names appears in the diff |

---

## Orchestrator state machine

```
classify  →  review (gates loop)  →  ready_for_human  →  HUMAN GATE
                ↑   ↓
                │   REQUEST_CHANGES → pause, engineer fixes, re-run
                │   BLOCK x3       → halt, log to _post-ship-escapes.md
                │
                APPROVE / NOT_APPLICABLE → next gate
```

State file (per work unit): `_state.json` next to the agent artifacts.

Subcommands:

| Command | Purpose |
|---|---|
| `classify` | Print the scope + which gates would run; no invocations |
| `run` | Run all pending gates serially, persist state, halt on budget hit |
| `run-gate <agent>` | Force-run a single named gate |
| `status` | Read the state file and pretty-print |

Flags worth knowing:

- `--dry-run` — synthesise verdicts; useful for wiring CI without paying tokens
- `--fresh` — ignore the existing state file and start over
- `--base <ref>` — git ref to diff against (default `origin/main`)
- `--timeout <s>` — per-gate timeout

---

## Wiring into CI (optional)

```yaml
# .github/workflows/review.yml — pseudocode
- name: Run omni-team
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
  run: |
    python .omni-team/bootstrap.py
    python .omni-team/orchestrator.py run \
        --mp "${{ github.event.pull_request.title }}" \
        --sprint 4 \
        --base "${{ github.base_ref }}"
```

The orchestrator exits non-zero on `REQUEST_CHANGES` / `BLOCK` budget hits,
giving CI a natural gate.

---

## Differences vs `.claude/agents/` (the original Centvra team)

| Aspect | Original `.claude/agents/` | `.omni-team/` |
|---|---|---|
| Prompts | Hardcoded for Centvra | Templated + manifest-injected |
| Decision matrix | Prose in CLAUDE.md | Structured YAML data |
| Invocation | Main Claude calls `Agent` tool by hand | `orchestrator.py run` (or `claude -p`) |
| State | Implicit (per-agent markdown only) | Explicit `_state.json` + per-agent markdown |
| Retry budget | "3 BLOCK → escalate" stated in prose | Enforced numerically + escape log |
| Human gate | Implicit (Codex crosscheck) | Explicit terminal state `ready_for_human` |
| Port to new project | Rewrite prompts | Swap manifest + run `bootstrap.py` |

---

## Differences vs `agents/.agent/` (the legacy orchestrator)

| Aspect | Legacy `agents/.agent/` | `.omni-team/` |
|---|---|---|
| Roles | PO / TL / DEV / QC / PM (agile loop) | 9 reviewer gates (no DEV agent) |
| Autonomy | Loops to "every card Done" | Stops at human gate; no auto-commit |
| Code authoring | DEV agent writes freely | Main Claude / human fixes per finding |
| Guardrails | Generic agile rules | Project-specific via manifest |
| Token cost | High (5 processes, no cache) | Lower (cache-friendly, retry budget) |

---

## File map

| File | Purpose |
|---|---|
| `templates/<agent>.md` | Universal role + process prompt with `{{placeholders}}` |
| `manifests/centvra.yaml` | Fully-populated Centvra facts |
| `manifests/_starter.yaml` | Copy-paste skeleton with `TODO_*` markers |
| `examples/*.yaml` | Reference manifests for other stacks |
| `lib/manifest.py` | YAML loader + dotted-key lookup |
| `lib/render.py` | `{{key.path}}` substitution |
| `lib/decision.py` | Decision matrix evaluator |
| `lib/state.py` | `RunState` / `GateState` + JSON persistence |
| `lib/runner.py` | `claude -p` subprocess + verdict classifier |
| `bootstrap.py` | Render templates → `.claude/agents/` |
| `orchestrator.py` | Classify, run, run-gate, status |

---

## What this framework deliberately does NOT do

- **Auto-commit / auto-push** — final ship is always human.
- **Run Codex crosscheck** — explicitly the human gate.
- **Author code from a "DEV" agent** — fixer is main Claude or a human, working
  from the reviewers' findings. This keeps the guardrail value of Team 1.
- **Reorder reviewers in parallel** — sequential by design; reviewers read disk
  state and must not race.
- **Translate i18n keys** — flag only; translation pipeline owns content.

---

## Roadmap (intentionally short)

- [ ] Optional pre-commit hook that runs `orchestrator.py classify` against
      staged diff and warns if a sensitive gate (e.g. `security-engineer`)
      would be skipped.
- [ ] `outcomes.md` aggregator: tally Codex-caught issues that agents missed,
      surface per-agent precision/recall over time.
- [ ] Tunable verdict-regex per project (in case an agent's output format
      diverges).
