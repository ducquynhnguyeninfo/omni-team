# Decision matrix

The decision matrix decides which agents fire for a given diff. **It is data, not code** — lives in [`.claude/manifests/<project>.yaml`](../.claude/manifests/) under `decision_matrix:`, evaluated by [`.claude/lib/decision.py`](../.claude/lib/decision.py). Project-specific routing = edit YAML, not Python. See [critical-rules.md](critical-rules.md) §2.

## Structure

Two parts: `base` (first match wins) and `add_if` (every match appends).

```yaml
decision_matrix:
  base:                    # first matching rule wins
    - name: bug-fix-be
      when: { loc_max: 100, stacks: ["backend"], schema_change: false }
      agents: ["backend-reviewer"]
    - name: new-endpoint
      when: { stacks: ["backend"], new_route: true }
      agents: ["qa-engineer", "backend-reviewer", "perf-engineer"]
    # …

  add_if:                  # every matching rule appends agents
    - when: { stacks: ["frontend"] }
      agents_add: ["ui-smoke-engineer"]
    - when:
        path_globs: ["**/auth*", "**/rbac*"]
        keywords: ["password", "token", "jwt"]
      agents_add: ["security-engineer"]
```

Evaluation order:

1. Walk `base:` top-to-bottom. First rule whose `when:` matches the diff sets the initial agent list.
2. Walk `add_if:`. Every rule whose `when:` matches appends its `agents_add:` to the list (de-duplicated).
3. Order within the final list follows [`.claude/templates/`](../.claude/templates/) declaration order — reviewers run serially in a stable sequence. See [architecture.md](architecture.md) §why-sequential.

## Supported predicates

All predicates appear under `when:`. A rule matches when **all** predicates match. Combine via additional `add_if` rules rather than nesting.

| Key | Meaning |
|---|---|
| `loc_max`, `loc_min` | Lines of *added* code in the diff |
| `stacks` | Subset of `{backend, frontend, database}` — derived from changed paths |
| `new_route` | A new `@router.<verb>` (or framework equivalent) appears |
| `schema_change` | A new file appears under the migration versions dir |
| `path_globs` | fnmatch glob list — any changed path matches |
| `keywords` | Any keyword appears (case-insensitive) in the diff text |
| `pii_fields` | Any of these PII field names appears in the diff |

Stack detection, "new route" detection, and migrations dir are configured under the manifest's `backend:` / `frontend:` / `database:` sections — not hardcoded.

## Adding a new predicate

This is a code change (touches [`.claude/lib/decision.py`](../.claude/lib/decision.py)). Procedure:

1. Add the predicate evaluator in `.claude/lib/decision.py`.
2. Add unit coverage — predicates are pure functions, easy to test.
3. Update the table above + the manifest schema in [`.claude/manifests/_starter.yaml`](../.claude/manifests/_starter.yaml).
4. Document in [manifest.md](manifest.md).

If you find yourself adding a predicate that's stack-specific ("only matches Django models"), stop — the right move is usually a new manifest field that the existing `path_globs` / `keywords` predicates can match against.

## Debugging

```bash
python .claude/orchestrator.py classify --mp <id> --base origin/main
```

Prints the matched `base:` rule, every triggered `add_if:` rule, and the final agent sequence. Use this before `run` whenever you change the matrix.
