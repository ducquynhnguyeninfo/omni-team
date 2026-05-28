# Manifest schema

The manifest is **Layer 3** in the [3-layer model](architecture.md) — project-specific facts injected into Layer 1+2 templates at bootstrap time.

Canonical reference: [`.claude/manifests/example.yaml`](../.claude/manifests/example.yaml) (fully populated). Schema spec: [`.claude/manifests/_starter.yaml`](../.claude/manifests/_starter.yaml). Other stacks: [`.claude/examples/`](../.claude/examples/).

## Top-level sections

| Section | Purpose |
|---|---|
| `project` | `name`, `short_name`, `description` |
| `work_unit_label` | Vocabulary: "Mini Package", "Story", "Ticket", … (used in agent prompts) |
| `spec_root` | Where work-unit specs live (passed to `tech-lead` and `qa-lead`) |
| `artifact_dir` | Where each agent's verbatim output is appended (per-MP folder) |
| `models` | Claude model per agent (`opus` / `sonnet` / `haiku`) |
| `quality_limits` | File/function/param/depth caps used by reviewer agents |
| `backend` | Stack, paths, layer rules, error contract, soft-delete pattern |
| `frontend` | Stack, paths, locales, i18n hook, UI lib, proxy helper |
| `database` | Engine, migration tool + commands, RLS file |
| `llm` | Enabled/disabled + provider config |
| `conventions` | Idempotency helper, audit fields |
| `performance` | Tier table + baseline doc |
| `security` | Trigger paths, PII fields, cookie flags |
| `cross_cutting_invariants_md` | Multi-line markdown block surfaced by `tech-lead` |
| `project_rules` | Per-agent extra rules (use `(none)` if empty) |
| `decision_matrix` | Base rules + `add_if` overlays — see [decision-matrix.md](decision-matrix.md) |
| `orchestrator` | Retry budgets, spawn mode, state file, human gate |

## Placeholder syntax

Templates use Mustache-style placeholders. `.claude/bootstrap.py` resolves them via dotted-key lookup against the manifest.

```
{{backend.error_contract.name}}      ← scalar (string / number)
{{cross_cutting_invariants_md}}      ← multi-line markdown block
{{performance.tier_table_md}}        ← pre-rendered table
```

Rules:

- **Missing keys are NOT silent.** `.claude/bootstrap.py` exits non-zero and lists every unresolved path. See [critical-rules.md](critical-rules.md) §3.
- **Intentionally empty?** Set the key to the literal string `(none)` — this is the contract for "no project-specific extra rules here."
- **Multi-line values** use YAML block scalars (`|` or `>`). They are inserted verbatim into the rendered prompt — formatting is your responsibility.
- **Pre-rendered tables** are a convenience: render markdown once in the manifest, reference once in the template.

## Adding a new placeholder

Breaking change. Procedure:

1. Update [`.claude/manifests/_starter.yaml`](../.claude/manifests/_starter.yaml) — this is the schema spec, every new key goes here first.
2. Update [`.claude/manifests/example.yaml`](../.claude/manifests/example.yaml) — the canonical reference must stay populated.
3. Update every file under [`.claude/examples/`](../.claude/examples/).
4. Update the section table above.
5. Bump anything that documents the manifest schema externally.

If you skip step 1–3, existing manifests will fail bootstrap with a missing-key error.

## Validation tips

- `python .claude/bootstrap.py --manifest <file>` and read the missing-key report — fastest way to catch typos.
- `python .claude/bootstrap.py --manifest <file> --dry-run` (if implemented) prints rendered output without writing.
- For new projects, copy [`_starter.yaml`](../.claude/manifests/_starter.yaml) verbatim and search for `TODO_` to find every field that must be filled.
