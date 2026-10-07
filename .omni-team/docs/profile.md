# Project profile and conventions

Two files in [`../project/`](../project/) hold everything project-specific. They are the only part of `.omni-team/` a host project edits.

| File | Format | Read by | Purpose |
|---|---|---|---|
| `profile.yaml` | YAML | every role at run time, `orchestrator.py` | structured facts: components, commands, URLs, spec location, overrides |
| `conventions.md` | Markdown | every role at run time | the rulebook: architecture, invariants, per-role rules |

Both work **empty**. Any `auto` value or missing section is inferred by the roles from the repository, and each report lists those inferences under *Assumptions* — your cue for what to write down. Run the `omni-setup` skill to have an agent draft both files.

## `profile.yaml`

| Key | Type | Meaning |
|---|---|---|
| `version` | int | schema version, currently `1` |
| `project.name`, `project.description` | string / `auto` | identity and 2–3 sentence summary (stack, domain) |
| `work_unit.label` | string | vocabulary used in reports: Task, Ticket, Story, Mini Package … |
| `work_unit.example_id` | string | example id, helps roles recognise ids in text |
| `work_unit.spec_root` | path / `auto` / `none` | where specs/tickets live; `qa-lead` and `tech-lead` look here |
| `components[]` | list | independently built/tested parts (empty → discovered) |
| `components[].name` | string | short id, usable in routing `components:` predicates |
| `components[].path` | path | repo-relative root (`.` for single-component repos) |
| `components[].kind` | enum | `backend` `frontend` `mobile` `desktop` `cli` `library` `worker` `data` `infra` `docs` `other` — also usable in routing |
| `components[].stack` | string | languages/frameworks with major versions |
| `components[].commands.{setup,lint,typecheck,test,build,run}` | shell | run from the component path; omit what you don't have |
| `components[].urls.{app,health,…}` | URL | for `smoke-tester` and `perf-engineer` |
| `checks` | `auto` / list of shell / `none` | **Gate 0**: list → each command at the repo root; `auto` → `lint`/`typecheck`/`test` of the touched components (all when none touched); `none` → disabled. Must pass before any AI gate |

Optional overrides of [`../defaults.yaml`](../defaults.yaml): `artifacts_dir`, `human_gate`, `quality_limits`, `signals`, `routing`, `orchestrator`.

### Merge rules

`orchestrator.py` loads `defaults.yaml`, then applies the profile:

| Key | Rule |
|---|---|
| any other top-level key | profile replaces default |
| `signals` | merged by signal name — redefine one signal without copying the others |
| `quality_limits` | merged key by key |
| `orchestrator` | merged key by key; `engines` merged by engine name; `retry_budget` merged key by key |
| `routing.stages` (or legacy `order`) / `routing.base` / `routing.add_if` | each replaces the default when present; a project `stages` or `order` replaces the default layout entirely |
| `routing.extra_add_if` | appended to the (default or replaced) `add_if` list |

Agents reading the profile directly should apply the same rules (they are simple enough to do by eye).

### Example

```yaml
version: 1
project:
  name: Acme Billing
  description: Invoicing SaaS. Go API + React SPA + PostgreSQL.
work_unit: { label: Ticket, example_id: BILL-123, spec_root: docs/specs }
components:
  - name: api
    path: api
    kind: backend
    stack: "Go 1.23 · chi · sqlc · goose · PostgreSQL 16"
    commands: { lint: "golangci-lint run", test: "go test ./...", run: "go run ./cmd/api" }
    urls: { app: "http://localhost:8080", health: "http://localhost:8080/healthz" }
  - name: web
    path: web
    kind: frontend
    stack: "TypeScript 5 · React 19 · Vite · TanStack Query · i18next"
    commands: { lint: "pnpm lint", typecheck: "pnpm tsc --noEmit", test: "pnpm vitest run", run: "pnpm dev" }
    urls: { app: "http://localhost:5173" }
signals:
  schema_change: { paths: ["api/db/migrations/**", "api/db/queries/**"] }
routing:
  extra_add_if:
    - name: money-paths
      when: { paths: ["api/internal/payments/**"] }
      agents_add: [security-engineer, perf-engineer]
```

More: [`../examples/`](../examples/).

## `conventions.md`

Free-form Markdown with **fixed section headings** — each role reads `All roles` plus its own section(s):

| Section | Read by |
|---|---|
| `All roles` | everyone |
| `Architecture`, `Cross-cutting invariants` | everyone, especially `tech-lead`, `code-reviewer`, `qa-lead` |
| `Tech lead` | `tech-lead` |
| `Code review` | `code-reviewer` |
| `Testing` | `test-engineer` |
| `Data & migrations` | `data-reviewer` |
| `Security` | `security-engineer` |
| `Performance` | `perf-engineer` |
| `Acceptance` | `qa-lead` |
| `Smoke testing` | `smoke-tester` |
| `Project management` | `pm` |
| `Glossary` | everyone |

Writing tips:

- State severity in words the roles map directly: **MUST NOT / CRITICAL** → BLOCK; **SHOULD** → REQUEST_CHANGES; "prefer" → INFO.
- Point to code rather than copying it: "error type: `src/errors.ts` (`AppError`)".
- Name the **reference implementation** new work should mirror — the single most useful line you can write.
- Use `(none)` for sections that don't apply; keep the heading.
- Never put secrets here. Test accounts: say *where* the credentials live.

## Validation

```bash
python3 .omni-team/orchestrator.py classify --task check   # parses profile + routing; exits 2 on errors
```

Errors are loud by design: unknown predicates, undefined signals, invalid regexes, malformed components and invalid YAML all fail with the file and key named.
