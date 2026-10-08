# Maintaining omni-team

For agents and humans changing the framework itself (anything under `.omni-team/` except `project/` and `runs/`). Using the team in a project? Read [../AGENTS.md](../AGENTS.md) instead.

## Read first

1. [critical-rules.md](critical-rules.md) — the invariants.
2. [architecture.md](architecture.md) — layers, modules, state machine.
3. [definition-of-done.md](definition-of-done.md) — what to run before you finish.

Then the topic guide from [when-to-load.md](when-to-load.md).

## Reviewing framework changes with the team

The defaults exclude `.omni-team/**` from review scope (in host projects it is vendored code). To dog-food the team on the framework itself, pass a profile that narrows the exclusion, e.g. a scratch file outside `.omni-team/`:

```yaml
# omni-dev-profile.yaml
orchestrator:
  exclude_paths: [".omni-team/runs/**"]
```

```bash
python3 .omni-team/orchestrator.py classify --task fw-change --profile omni-dev-profile.yaml
```

## Golden rules in one breath

Roles are stack-agnostic prose; project facts are read at run time from `project/`; routing is YAML; `install.py` is stdlib-only and touches only its own output; verdicts come from the `VERDICT:` line; gates run serially; nothing commits.

## Compatibility notes (v1 → v2)

v2 replaced the render-time manifest with run-time project context.

| v1 | v2 |
|---|---|
| `templates/*.md` with `{{placeholders}}` | `team/*.md` (static) + `team/_protocol.md` |
| `manifests/<project>.yaml` (100+ required keys) | `project/profile.yaml` (all `auto`) + `project/conventions.md` |
| `examples/*.yaml` | `examples/<name>/{profile.yaml,conventions.md}` |
| `bootstrap.py` → `.claude/agents` only | `install.py` → Claude, Codex, Gemini, AGENTS.md |
| `decision_matrix` with `stacks`, `new_route`, `schema_change`, `pii_fields` | `signals` + `routing`; predicates `paths`, `only_paths`, `added_lines`, `keywords`, `components`, `signals`, … |
| `backend-reviewer` + `frontend-reviewer` | `code-reviewer` (UI checks are conditional) |
| `dba` | `data-reviewer` (any storage, wire formats) |
| `qa-engineer` | `test-engineer` |
| `ui-smoke-engineer` | `smoke-tester` (browser, API, CLI, library) |
| verdict words anywhere in the last 60 lines | strict last `VERDICT: <TOKEN>` line |
| `orchestrator.py` → `claude -p` only; diff `base...HEAD` | engines (claude, codex, custom); working tree incl. uncommitted |
| `--mp`, `--sprint` | `--task` |

Migrating a v1 manifest: move stack facts (paths, commands, URLs) into `components`, and every `*_md` rule block into the matching `conventions.md` section (`backend.layer_rules_md` → *Architecture*, `project_rules.dba.*` → *Data & migrations*, `security.*` → *Security*, `performance.tier_table_md` → *Performance*, …). Port `decision_matrix.add_if` path globs into `signals` or `routing.extra_add_if`.

## Compatibility notes (v2.0 → v2.1)

| v2.0 | v2.1 |
|---|---|
| `routing.order` (strictly serial gates) | `routing.stages` — independent gates share a stage and run concurrently (`orchestrator.max_parallel`). `order` is still accepted as one gate per stage; never set both |
| checks were an instruction to the implementer | **Gate 0**: `orchestrator.py checks` / `run` execute `checks` (or component `lint`/`typecheck`/`test`) and stop with exit 7 when red |
| a passed gate stayed passed until `--fresh` | approvals store the working-tree snapshot; the delta since approval is routed and re-opens the gate when it selects it |
| `_state.json` gates without `approved_tree` | treated as "approval snapshot unknown" → re-opened once on the next run |

## Compatibility notes (v2.1 → v2.2)

| Change | Impact |
|---|---|
| New roles `ba` (Define), `architect` (Design + review gate), `release-manager` (Release) and skills `/ba`, `/architect`, `/release` | re-run `install.py`; nothing to migrate |
| New signal `architecture_change`; add rules `architecture-change`, `very-large-change` → `architect` | infra/CI/contract/ADR changes, ≥ 25 files or ≥ 1500 added lines now get an architecture review |
| Default `routing.stages` now `[ba, tech-lead, pm] → [architect, data, code, test, security, perf] → [qa-lead] → [smoke-tester] → [release-manager]` | projects that override `stages` should add `architect` to their review stage |
| `conventions.md` gains `Requirements` and `Release` sections | add them to existing project files (empty is fine) |
| `qa-lead` acceptance source order: spec → `runs/<id>/spec.md` (ba) → `tech-lead.md` → request | — |

## Compatibility notes (v2.2 → v2.3)

| Change | Impact |
|---|---|
| `install.py --dir <project>` vendors the framework (fresh or upgrade) and installs in one step; commands `install`/`init`/`upgrade`/`uninstall` | manual `cp -R` no longer needed; `--project-root` keeps its old meaning (adapters only) |
| `upgrade` preserves `project/` and `runs/`, removes stale framework files, refuses downgrades without `--force` | local edits to framework files (e.g. `defaults.yaml`) are overwritten — put overrides in `project/profile.yaml` |

## Compatibility notes (v2.3 → v2.4)

| Change | Impact |
|---|---|
| `install.py --dir` vendors a **slim** runtime set (`RUNTIME_SET` in `lib/vendor.py`); `--full` keeps the old behaviour | projects no longer carry the installer, tests, examples or maintainer docs; install/upgrade from the omni-team checkout |
| `.omni-team/.vendor.json` manifest; upgrades remove only files the previous install shipped (pre-2.4 copies without a manifest are slimmed: everything except `project/` and `runs/` not in the new set is removed) | files you add inside `.omni-team/` survive upgrades |
| Runtime docs no longer link to `README.md`, `docs/maintaining.md`, `examples/` | they name the omni-team repository instead |

## Compatibility notes (v2.4 → v2.5)

| Change | Impact |
|---|---|
| Skills are installed as whole folders (scripts, data, licences copied byte-for-byte); managed skill folders are cleaned file by file | multi-file skills work in Claude Code and Codex |
| `install.py --skills a,b,c` selects skills (default `all`) | deselected managed skills are removed from the project |
| Library skill `drawio-skill` (MIT, upstream Agents365-ai, pinned in `skills/drawio-skill/UPSTREAM.md`) | needs the draw.io desktop CLI; Graphviz optional |
| Third-party skills must ship `LICENSE` + `UPSTREAM.md` (a test enforces it) and have a licence that allows redistribution | do not add proprietary skills to this repository |

## Compatibility notes (v2.5 → v2.6)

| Change | Impact |
|---|---|
| Protocol scope rule "the diff is where you start, not where you stop" + `CR-19` (code-reviewer), `DR-14` (data-reviewer), `SE-16` (security-engineer): when a change alters an invariant, dependents in unchanged files are searched and reported under **Invariants changed** | new rule ids appended; reports gain one header line. Benchmarked: same recall and cost, the sweep is now visible in 100% of reports (was 0%) |
| Protocol: the final message must be the complete report; Claude engine runs with `--disallowedTools ReportFindings` | fixes a headless failure where the report was filed through a tool and lost from the artifact |
| `install.py --dir` accepts a pre-seeded `.omni-team/` holding only `project/` (and `runs/`) — profile written before installing; existing project files are never overwritten | write `project/profile.yaml` + `conventions.md` first, then install |

## Compatibility notes (v2.6 → v2.7)

| Change | Impact |
|---|---|
| Components that are nested git repositories (folder contains `.git`, or `repo: true`) are diffed/snapshotted per repository with path prefixes; the workspace repo excludes them (gitlinks too); workspaces need not be git repos themselves | private workspace + delivered product repos now work with classify / run / approvals — see `docs/workspace.md` |
| `components[].base_ref`, `orchestrator.base_candidates` (data, was hard-coded) | repos branching from `develop` can set their base |
| **Fix**: snapshots copy the index with its mtime (`shutil.copy2`). Since v2.1 a same-size edit made in the same second as the last index write, snapshotted a second later, could be missed (git's racy-clean check was defeated) — affecting review scope, the Gate 0 green cache and approval re-opening | re-run `classify` on open work after upgrading |
| `install.py` records the adapter files it manages in `.omni-team/.generated`; the orchestrator keeps them out of review scope (pointer files stay in) | a fresh install no longer floods the first review with generated agents and skills |
| Composite snapshot `"<repo>:<tree>|…"` in `_state.json` | single-repo projects keep plain tree ids; a workspace's first run after adding a repo re-opens approvals once |

## Compatibility notes (v2.7 → v2.8)

| Change | Impact |
|---|---|
| Role report files rotate beyond `orchestrator.artifact_max_kb` (default 40 KB): older reports → `_archive/<role>.md`, hot file = index + newest report (`lib/artifacts.py`) | existing files are parsed as-is and rotated on their next write; nothing is deleted |
| Findings carry stable ids `F1, F2 …`; re-reviews open with an *Earlier findings* table and repeat only open/new findings | shorter re-review reports; role templates show `- F<n> [path:line] (RULE-ID)` |
| `orchestrator.py record <role> --task <id>` persists externally produced reports (native sub-agents) through the same rotation and state | the manual flow no longer appends unbounded files |
| Task id guidance: one per work item, not per branch | — |
