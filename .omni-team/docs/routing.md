# Routing — which gates run for a diff

Routing is **data**: named *signals* detect what a diff touches; *rules* map signals and size to gates. Defaults live in [`../defaults.yaml`](../defaults.yaml); projects override them in `project/profile.yaml` ([merge rules](profile.md#merge-rules)). [`../lib/routing.py`](../lib/routing.py) only evaluates — it never contains a pattern or a stack name.

## The diff

`orchestrator.py` builds the scope from git:

- base: `--base`, else `orchestrator.base_ref` (`auto` → first of `origin/HEAD`, `origin/main`, `origin/master`, `main`, `master`);
- compared from the merge-base of base and `HEAD` **to the working tree** (staged, unstaged and untracked files included) unless `--committed-only` or `include_uncommitted: false`;
- `orchestrator.exclude_paths` removed (default: `.omni-team/**` — the vendored framework and its run artifacts are not project code; see [maintaining.md](maintaining.md) for reviewing the framework itself).

"LoC" means **added lines**.

## Predicates

Usable in signals and in rule `when:` blocks. All predicates in one mapping must match (AND).

| Predicate | Value | Matches when |
|---|---|---|
| `loc_min` / `loc_max` | int | added lines ≥ / ≤ value |
| `files_min` / `files_max` | int | changed file count ≥ / ≤ value |
| `paths` | glob list | **any** changed path matches any glob |
| `only_paths` | glob list | **every** changed path matches some glob (and at least one changed) |
| `added_lines` | regex list | any added line matches any regex (Python `re`, `search`) |
| `keywords` | string list | any keyword appears, case-insensitive, in added or removed lines |
| `components` | list | **all** listed component names/kinds are touched (from profile `components`) |
| `any_component` | list | at least one listed component name/kind is touched |
| `signals` | list | **all** listed signals fired (rules only — not inside signals) |

Globs use `fnmatch` semantics (`*` also crosses `/`), and a leading `**/` additionally matches at the repo root, so `**/auth/**` matches both `auth/x.py` and `src/auth/x.py`.

`{}` (empty `when`) always matches — use it for a catch-all base rule.

## Signals

```yaml
signals:
  schema_change:                 # mapping → all predicates must match
    paths: ["**/migrations/**", "**/*.sql"]
  security_sensitive:            # list → any alternative may match (OR of ANDs)
    - paths: ["**/auth/**"]
    - keywords: ["password", "api_key"]
```

Default signals: `docs_only`, `ui_change`, `schema_change`, `api_surface_change`, `security_sensitive`, `architecture_change`, `dependency_change`, `perf_sensitive`. Their patterns cover common layouts and route/command declarations across Python, JS/TS, JVM, .NET, Go, Rust, Ruby, PHP, Elixir, gRPC and GraphQL. Override a signal in your profile when your layout differs — signals are merged by name.

## Rules

```yaml
routing:
  stages:                        # stages run in order; gates inside one stage run concurrently
    - [ba, tech-lead, pm]
    - [architect, data-reviewer, code-reviewer, test-engineer, security-engineer, perf-engineer]
    - [qa-lead]
    - [smoke-tester]
    - [release-manager]
  base:                          # FIRST match sets the initial gate list
    - name: docs-only
      when: { signals: [docs_only] }
      agents: []
      final: true                # skip add_if entirely
    - name: small-change
      when: { loc_max: 150 }
      agents: [code-reviewer]
    - name: large-change
      when: {}
      agents: [code-reviewer, test-engineer, qa-lead]
  add_if:                        # EVERY match appends gates
    - name: security-sensitive
      when: { signals: [security_sensitive] }
      agents_add: [security-engineer]
```

Evaluation: compute all signals → first matching `base` rule → unless it is `final`, append `agents_add` of every matching `add_if` rule → de-duplicate → group by `stages` (gates missing from the layout run alone at the end, in selection order).

`stages` replaces the older `order:` list (still accepted: one gate per stage). Use one or the other, never both. Put a gate in a later stage only if it must read an earlier gate's report; everything independent belongs in the same stage. Concurrency inside a stage is capped by `orchestrator.max_parallel`.

The same routing decides when an **approval expires**: on re-run, the change since a gate approved is routed on its own, and the gate re-opens if that delta selects it.

Default behaviour in words:

| Change | Gates |
|---|---|
| docs only, or ≤ 15 added lines | none (run the checks) |
| ≤ 150 added lines | `code-reviewer` |
| larger | `code-reviewer`, `test-engineer`, `qa-lead` |
| + schema / data model / wire format | + `data-reviewer`, `test-engineer` |
| + new API/CLI surface | + `test-engineer`, `perf-engineer` |
| + data-access/jobs paths (≥ 40 lines) | + `perf-engineer` |
| + auth, secrets, input handling, infra/CI | + `security-engineer` |
| + dependency manifests | + `security-engineer` |
| + infra/CI/containers, API/event contracts, ADRs, ≥ 25 files, or ≥ 1500 added lines | + `architect` |
| + UI files (≥ 40 lines) | + `smoke-tester` |

## Recipes

```yaml
# Always run security on a sensitive module
routing:
  extra_add_if:
    - name: payments
      when: { paths: ["src/payments/**"] }
      agents_add: [security-engineer, perf-engineer]

# Teach the defaults your migration folder
signals:
  schema_change: { paths: ["db/changes/**", "src/**/entities/*.ts"] }

# Only the frontend component triggers smoke tests
routing:
  add_if:
    - name: web-ui
      when: { components: [web], loc_min: 20 }
      agents_add: [smoke-tester]
```

## Debugging

```bash
python3 .omni-team/orchestrator.py classify --task dbg [--base <ref>]
```

Prints the scope, fired signals, matched base rule, matched add rules and the final gate order. Run it after every routing change.

## Extending the predicate set

A new predicate is a code change in `lib/routing.py` (`PREDICATES`) plus a unit test in `tests/test_routing.py` and a row in the table above. Before adding one, check whether `paths` / `added_lines` / `keywords` with a new signal already express it — a stack-specific predicate ("is a Django model") is always the wrong answer.
