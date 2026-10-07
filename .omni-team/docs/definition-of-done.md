# Definition of done (framework changes)

Before declaring a change to omni-team itself complete:

- [ ] **Tests pass:** `python3 -m unittest discover -s .omni-team/tests` (routing/profile tests are skipped without PyYAML — run them with it installed at least once).
- [ ] **Install renders:** `python3 .omni-team/install.py --tools all --project-root <scratch dir>` succeeds; generated `.codex/agents/*.toml` parse as TOML and `.claude/agents/*.md` frontmatter parses as YAML (the tests check both).
- [ ] **Routing still sane:** `python3 .omni-team/orchestrator.py classify --task check` exits 0, and for any routing change you ran it against a representative diff and the gate list makes sense.
- [ ] **Role touched?** Still stack-agnostic ([critical-rules.md](critical-rules.md) §1), rule ids stable, ends with the protocol verdict line, ownership table in `_protocol.md` still true.
- [ ] **New predicate / signal / verdict token?** Unit test added; [routing.md](routing.md) or `_protocol.md` updated.
- [ ] **Profile key or conventions section added/renamed?** `project/` templates, every `examples/*/` folder and [profile.md](profile.md) updated.
- [ ] **Role added/removed?** Followed [roles.md](roles.md) §adding-a-role (protocol table, AGENTS.md, README, defaults order).
- [ ] **Docs links resolve** in every file you touched — and files shipped to projects (`RUNTIME_SET` in `lib/vendor.py`) link only to other shipped files.
- [ ] **New runtime file** (read by agents or imported by `orchestrator.py`)? Added to `RUNTIME_SET`.
- [ ] **No secrets**, no auto-commit/push anywhere, quality limits respected ([code-quality.md](code-quality.md)).
- [ ] `VERSION` bumped for user-visible changes (major for breaking contract changes).

## Smoke sequence

```bash
python3 -m unittest discover -s .omni-team/tests
python3 .omni-team/install.py --tools all --project-root "$(mktemp -d)"
python3 .omni-team/orchestrator.py classify --task check
python3 .omni-team/orchestrator.py run --task smoke --dry-run --fresh   # writes .omni-team/runs/smoke/
```

Delete `.omni-team/runs/smoke/` afterwards.
