# Definition of Done

Before marking any change to omni-team complete:

- [ ] **Templates touched?** Re-render against [`.claude/manifests/example.yaml`](../.claude/manifests/example.yaml) and at least one file under [`.claude/examples/`](../.claude/examples/). Both must produce sensible output with zero missing-key errors.
- [ ] **New placeholder added?** Updated [`.claude/manifests/_starter.yaml`](../.claude/manifests/_starter.yaml), [`.claude/manifests/example.yaml`](../.claude/manifests/example.yaml), and every file under [`.claude/examples/`](../.claude/examples/). See [manifest.md](manifest.md) §adding-a-new-placeholder.
- [ ] **`.claude/lib/decision.py` touched?** Added or updated unit coverage for the predicate. Predicates are pure functions — there is no excuse.
- [ ] **`.claude/lib/runner.py` verdict regex changed?** Smoke-test against a real `claude -p` invocation, not just unit test. Verdict parsing is load-bearing.
- [ ] **New agent role added?** Followed the procedure in [agents.md](agents.md) §adding-a-new-agent: template + manifest schema entries + this file's checklist updated.
- [ ] **Decision matrix changed?** Ran `python .claude/orchestrator.py classify` against a representative diff and confirmed the new agent sequence makes sense.
- [ ] **README / docs touched?** Cross-checked links — every `[text](path)` in changed files still resolves.
- [ ] **No secrets** introduced into checked-in files. Manifests are world-readable; `ANTHROPIC_API_KEY` and friends flow through env vars only.
- [ ] **Quality limits respected** — see [code-quality.md](code-quality.md). 500/100/8/4.
- [ ] **No auto-commit / auto-push** added anywhere. The human gate is load-bearing. See [critical-rules.md](critical-rules.md) §5.

## Smoke test (suggested minimal)

```bash
# Renders all templates against the example manifest. Must exit 0.
python .claude/bootstrap.py --manifest .claude/manifests/example.yaml --dry-run

# Classify against a representative diff. Must print a non-empty agent sequence.
python .claude/orchestrator.py classify --manifest .claude/manifests/example.yaml --mp TEST --base HEAD~1
```

If `--dry-run` is not implemented yet, run the real render into a scratch directory and diff against the previous output.

## What "done" does NOT mean

- It does not mean every link in every doc points somewhere — `[[broken-link]]` style placeholders are deliberate when surfacing a TODO.
- It does not mean every host-project's manifest renders — third-party manifests are their problem, not ours.
- It does not mean PRs in host projects are unblocked — the framework can be valid while a host's manifest is stale.
