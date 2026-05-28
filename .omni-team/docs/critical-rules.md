# Critical Rules

Rules that must never be silently relaxed. Each rule names *what* and *why* — when in doubt, escalate to the user rather than work around.

1. **Templates stay project-agnostic.** [`templates/*.md`](../templates/) capture **Layer 1 (Role)** + **Layer 2 (Process)** only. Anything stack-, framework-, or product-specific belongs in a manifest under [`manifests/`](../manifests/). If you find yourself writing "FastAPI" or "Next.js" in a template, stop and add a placeholder. See [architecture.md](architecture.md) §3-layer-model.

2. **Decision matrix is data, not code.** All routing logic (which agents fire for which change) lives under `decision_matrix:` in the manifest. [`lib/decision.py`](../lib/decision.py) only *evaluates* the predicates — it never *embeds* them. Adding a new project-specific rule = edit YAML, not Python. See [decision-matrix.md](decision-matrix.md).

3. **`bootstrap.py` must fail loudly on missing keys.** A missing `{{dotted.path}}` is a contract violation, not an empty string. If a key is *intentionally* empty, the manifest sets it to the literal string `(none)`. Never paper over with silent defaults.

4. **`orchestrator.py` never bypasses verdict parsing.** Verdicts (`APPROVE` / `REQUEST_CHANGES` / `BLOCK` / `NOT_APPLICABLE`) are regex-matched from agent stdout. Never infer from "looks like it passed" — that defeats the audit trail.

5. **Never auto-commit / auto-push / auto-merge from `orchestrator.py`.** The human gate (`ready_for_human` → Codex crosscheck → manual `git commit`) is load-bearing. The framework's whole value proposition is that ship is a human decision.

6. **`templates/*.md` placeholders are the public contract.** Adding, renaming, or removing a `{{key.path}}` is a breaking change to every existing manifest. If you must change one: (a) update [`manifests/_starter.yaml`](../manifests/_starter.yaml) which is the schema spec; (b) update [`manifests/example.yaml`](../manifests/example.yaml) and every file under [`examples/`](../examples/); (c) note in [manifest.md](manifest.md).

7. **No secrets in checked-in files.** API keys (`ANTHROPIC_API_KEY`, etc.) flow through environment variables only. Manifests are committed and reviewed in PRs — treat any field there as world-readable.

8. **Reviewer agents run serially, never in parallel.** They read disk state (other agents' artifacts under `agent-pow/`) and must observe a deterministic order. `orchestrator.py` enforces this — do not work around it.

9. **Retry budget is numeric, not aspirational.** Three `BLOCK` verdicts on the same scope → halt and log to `_post-ship-escapes.md`. No "let me try one more time."

10. **Quality limits apply to this repo too.** 500 LoC/file, 100 LoC/function, 8 parameters, 4 nesting levels — the same limits the reviewers enforce on host-project code. See [code-quality.md](code-quality.md).
