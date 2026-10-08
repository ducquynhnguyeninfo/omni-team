# Architecture

omni-team is a folder of **data and prose** (roles, protocol, skills, defaults) plus two small, optional Python entry points that adapt it to tools (`install.py`) and run it headless (`orchestrator.py`).

## Three layers, resolved at run time

| Layer | Captures | Lives in | Resolved |
|---|---|---|---|
| 1 — Role | "You are the Security Engineer; you own authN/Z, secrets, injection…" | `team/<role>.md` | static |
| 2 — Process | context loading, scope, severity, finding format, verdict line, read-only | `team/_protocol.md` (+ each role's workflow) | static |
| 3 — Project | "Errors are `AppError`; migrations in `db/changes`; never touch `auth.*`" | `project/profile.yaml`, `project/conventions.md` | **by the agent, at run time** |

Earlier versions rendered Layer 3 into templates through 100+ `{{placeholders}}`; a missing key broke the bootstrap, and every role assumed a backend/frontend/database web stack. Now Layer 3 is *read* by the role when it runs, with inference from the repository for anything not written down. Consequences:

- **Zero-config start.** Copy the folder; roles work immediately and report their assumptions.
- **Stack-agnostic roles.** Checklists talk about "entry points", "data-access layer", "UI string catalogue"; the protocol's *stack lens* tells the model to map them onto whatever stack it finds.
- **One source for every tool.** Roles are plain Markdown; adapters only change the wrapper format.

## Components

```
                ┌──────────── team/*.md, _protocol.md, skills/*/SKILL.md (canonical) ────────────┐
                │                                                                                 │
   install.py ──┤ lib/roles.py  ─► lib/adapters.py ─► .claude/agents, .claude/skills,            │
   (stdlib)     │                                     .codex/agents/*.toml, .agents/skills,       │
                │                                     pointer blocks in CLAUDE.md/AGENTS.md/GEMINI.md
                │                                                                                 │
 orchestrator ──┤ lib/profile.py (defaults.yaml ⊕ project/profile.yaml)                           │
   (PyYAML)     │ lib/diffscope.py (git → Scope) ─► lib/routing.py (signals + rules → gates)      │
                │ lib/runner.py (role+protocol+invocation → engine CLI → VERDICT) ─► runs/<id>/   │
                │ lib/state.py (_state.json)                                                      │
                └─────────────────────────────────────────────────────────────────────────────────┘
```

| Module | Responsibility | Dependencies |
|---|---|---|
| `lib/roles.py` | parse role/skill frontmatter, validate, compose role + protocol | stdlib |
| `lib/adapters.py` | render Claude agent Markdown, Codex TOML, skills; pointer blocks; managed-file marker | stdlib |
| `lib/profile.py` | load and merge `defaults.yaml` + `project/profile.yaml` | PyYAML |
| `lib/diffscope.py` | working-tree snapshot (tree object via temp index) → `Scope`; deltas between snapshots; workspaces with nested repositories (per-repo diff, prefixed paths, composite snapshot) | stdlib + git |
| `lib/checks.py` | Gate 0: resolve and run the project's checks, log | stdlib |
| `lib/pipeline.py` | verdict → state, retry budget, approval re-opening, concurrent stage execution | stdlib |
| `lib/routing.py` | evaluate predicates and signals, select and order gates | stdlib |
| `lib/runner.py` | build prompt, run engine argv, parse verdict, append artifact | stdlib |
| `lib/state.py` | `RunState` / `GateState` JSON persistence | stdlib |

`install.py` imports only stdlib modules so a freshly copied folder can register itself without `pip`. Only the orchestrator needs PyYAML.

## State machine (orchestrator)

```
classify ─► gate 0 ──red──► checks_failed (exit 7)
              │ green
              ▼
           review: stage 1 → stage 2 (gates ‖) → … ──(all passed)──► ready_for_human ─► HUMAN GATE
              │ ▲
              │ └── re-run after fixes (passed gates skipped unless re-opened by the delta; newly-routed gates added)
              ├── REQUEST_CHANGES / BLOCK within budget ─► paused (exit 1)
              ├── budget exhausted ─► halted (exit 3/4) + _escapes.md
              ├── NEEDS_CLARIFICATION / BLOCKED ─► halted (exit 6)
              └── no parseable VERDICT ─► halted (exit 5)
```

Gate statuses: `pending`, `passed`, `request_changes`, `block`, `needs_human`, `error`.

## Design decisions

- **Reviewers, not authors.** No "developer" role: the main agent or a human writes code from the findings. This keeps reviewers independent of the work they judge.
- **Staged gates.** Gates that read earlier reports sit in later stages; independent gates share a stage and run concurrently. Per-gate artifact files mean concurrent gates never write to the same file.
- **Deterministic Gate 0.** Lint/typecheck/test run before any AI gate — cheap, reproducible, and they keep reviewers from spending tokens on code that fails its own tests.
- **Snapshot-based approvals.** The working tree is captured as a git tree object through a temporary index (real index and files untouched); an approval is tied to that tree and re-opened when the delta since it re-routes the gate.
- **Strict verdict line.** `VERDICT: <TOKEN>` on the last matching line; anything else is `UNKNOWN` and halts. Inferring "looks approved" from prose defeats the audit trail.
- **Working-tree scope.** Review happens before commit, so uncommitted and untracked files are in scope by default.
- **Data-driven routing.** Signals and rules are YAML; Python only evaluates. Stack knowledge lives in signal patterns, which projects can override by name.
- **Never ship.** No component commits, pushes, merges or tags.
