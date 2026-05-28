# omni-team — Portable, Auto-Runnable Review-Gate Team

A baseline framework for portable, project-agnostic automated-agent code review.
Extracts the 9-role team concept into templates (universal) and manifests (project-specific).
Two key properties:

1. **Portable** — agent prompts are templated; project-specific facts live in a
   YAML manifest. Switch projects by swapping the manifest.
2. **Auto-runnable** — an orchestrator picks the right agents for a given diff,
   runs them headless via `claude -p`, retries on `REQUEST_CHANGES`, halts on
   `BLOCK` after a retry budget, and stops at the human gate (Codex
   crosscheck). No agent ever auto-commits.

```
omni-team/                       ← repo root
├── README.md
├── CLAUDE.md
├── LICENSE
├── requirements.txt
├── .claude/agents/              ← OUTPUT of bootstrap.py (auto-loaded by Claude Code)
└── .omni-team/                  ← THE framework
    ├── templates/               ← Layer 1+2: universal role + process (9 agents)
    ├── manifests/
    │   ├── example.yaml         ← Layer 3: reference project facts
    │   └── _starter.yaml        ← copy-paste skeleton for new projects
    ├── examples/
    │   ├── django-postgres.yaml
    │   └── nextjs-prisma.yaml
    ├── lib/                     ← manifest, render, decision, state, runner
    ├── bootstrap.py             ← render templates + manifest → ../.claude/agents/
    ├── orchestrator.py          ← classify → invoke gates → state machine
    └── docs/                    ← split sub-guides
```

## Quick start

To use this baseline as your project's starting point or to vendor into existing code:

```bash
# 0. Install dependencies (Python 3.10+; PyYAML is the only runtime dep)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1. Copy the starter manifest and fill in project-specific facts
cp .omni-team/manifests/_starter.yaml .omni-team/manifests/myproject.yaml
$EDITOR .omni-team/manifests/myproject.yaml

# 2. Render agents, settings, and commands (writes to .claude/)
python .omni-team/bootstrap.py --manifest .omni-team/manifests/myproject.yaml

# 3. (Optional) See which gates would run for the current branch's diff
python .omni-team/orchestrator.py classify \
    --manifest .omni-team/manifests/myproject.yaml \
    --mp WORK-01 --base origin/main

# 4. Run the full pipeline (in CI or locally)
python .omni-team/orchestrator.py run \
    --manifest .omni-team/manifests/myproject.yaml \
    --mp WORK-01 --base origin/main

# 5. (Optional) Inspect state any time
python .omni-team/orchestrator.py status \
    --manifest .omni-team/manifests/myproject.yaml \
    --mp WORK-01
```

### What bootstrap.py renders

After step 2, you'll have a complete Claude Code workspace:

```
.claude/
├── agents/              ← 9 agent prompts (tech-lead, backend-reviewer, etc.)
├── commands/            ← /test-be, /migrate-new, /stack-up, etc.
└── settings.json        ← Claude Code configuration (MCPs, hooks, permissions)
```

The agents are universal (from `templates/`). The commands and settings are templated
with placeholders from your manifest—edit `myproject.yaml` to customize MCP servers,
validation hooks, and command scripts.

---

## How the 3-layer model works

Every original agent prompt mixed three things. omni-team splits them:

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
`.omni-team/manifests/example.yaml` for a fully-populated reference):

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
| `claude_code` | Enabled MCPs, file validation hooks, permissions, stop reminder |
| `commands` | Custom CLI commands (test-be, migrate-new, stack-up, etc.) |
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

## Configuring Claude Code (MCPs, hooks, commands)

The `claude_code` section in your manifest controls `.claude/settings.json` and `.claude/commands/`:

### Enable MCPs

```yaml
claude_code:
  enabled_mcps:
    - chrome_devtools
    - custom_mcp_for_your_project
```

### File validation hooks

```yaml
  post_tool_use_hooks_md: |
    - path_matcher: "migrations/versions/*.py"
      reason: "Applied migrations are immutable. Create a NEW migration."
    - path_matcher: "**/generated/*.ts"
      reason: "Auto-generated file. Edit the generator instead."
```

### Stop hook reminder

```yaml
  stop_hook_reminder: "Run tests before declaring done: /test-be or /test-fe"
```

### Permission allow-list

```yaml
  permissions_allow_list: |
    Bash(ls:*), Bash(rg:*), Bash(pytest:*), Bash(ruff:*), Bash(pnpm:*)
```

### Custom commands

Define commands in the `commands:` section. Each command is templated from `.omni-team/templates/commands/`:

```yaml
commands:
  test_backend:
    description: "Run backend tests"
    script: |
      cd {{backend.root}} && {{backend.test_cmd}}
```

Bootstrap renders this to `.claude/commands/test-backend.md`, making `/test-backend` available in Claude Code.

---

## Decision matrix

The matrix in `.omni-team/manifests/<project>.yaml` is data, not code. It has two parts:

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
    python .omni-team/bootstrap.py --manifest .omni-team/manifests/<your>.yaml
    python .omni-team/orchestrator.py run \
        --manifest .omni-team/manifests/<your>.yaml \
        --mp "${{ github.event.pull_request.title }}" \
        --base "${{ github.base_ref }}"
```

The orchestrator exits non-zero on `REQUEST_CHANGES` / `BLOCK` budget hits,
giving CI a natural gate.

---

## Differences vs a hand-rolled `.claude/agents/` set

| Aspect | Hand-rolled `.claude/agents/` | omni-team |
|---|---|---|
| Prompts | Templated (universal role + process) | Templated + manifest-injected |
| Decision matrix | Data-driven via manifest | Structured YAML data |
| Invocation | Manual per-agent calls | `orchestrator.py run` (automatic gate selection) |
| State | Implicit (per-agent markdown only) | Explicit `_state.json` + per-agent markdown |
| Retry budget | Manual re-invocation | Enforced numerically + escape log |
| Human gate | Implicit (Codex crosscheck) | Explicit terminal state `ready_for_human` |
| Port to new project | Rewrite prompts + logic | Swap manifest + run `bootstrap.py` |

---

## Differences vs `agents/.agent/` (the legacy orchestrator)

| Aspect | Baseline framework | Legacy `agents/.agent/` |
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
| `.omni-team/templates/<agent>.md` | Universal role + process prompt with `{{placeholders}}` |
| `.omni-team/templates/settings.json.jinja2` | Claude Code config template (MCPs, hooks, permissions) |
| `.omni-team/templates/commands/*.md` | Command templates (test-be, migrate-new, stack-up, etc.) |
| `.omni-team/manifests/example.yaml` | Fully-populated reference manifest |
| `.omni-team/manifests/_starter.yaml` | Copy-paste skeleton with `TODO_*` markers |
| `.omni-team/examples/*.yaml` | Reference manifests for other stacks |
| `.omni-team/lib/manifest.py` | YAML loader + dotted-key lookup |
| `.omni-team/lib/render.py` | `{{key.path}}` substitution |
| `.omni-team/lib/decision.py` | Decision matrix evaluator |
| `.omni-team/lib/state.py` | `RunState` / `GateState` + JSON persistence |
| `.omni-team/lib/runner.py` | `claude -p` subprocess + verdict classifier |
| `.omni-team/bootstrap.py` | Render templates → `.claude/agents/`, `.claude/commands/`, `.claude/settings.json` |
| `.omni-team/orchestrator.py` | Classify, run, run-gate, status |

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
