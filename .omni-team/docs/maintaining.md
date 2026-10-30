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

Roles are stack-agnostic prose; project facts are read at run time from `project/`; routing is YAML; `install.py` is stdlib-only and touches only its own output; verdicts come from the `VERDICT:` line; gates run serially; no script or reviewer commits, the implementer only per `automation.pr_fix` (default `off`), and merge stays human.

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

## Compatibility notes (v2.8 → v2.9)

Selected practices from other agent toolkits (superpowers, gstack, Claude Code's `/security-review`, Anthropic's `frontend-design`); their auto-fixing reviewers and push/merge commands were deliberately left out.

| Change | Impact |
|---|---|
| `AGENTS.md` §5 Implement gains working rules for the implementer: verify each phase before the next, reproduce a bug with a failing test first, debug from evidence (stop after 3 failed fixes), claim "done"/"passes" only with output from a command that ran | `omni-task` skill points to them; no role or routing change |
| `security-engineer`: explicit non-findings (trusted config inputs, fields of authenticated messages, robustness-only defects → `code-reviewer`) and "report problems only" | fewer judgement-call extras; recall unchanged on the security bench (see `bench/README.md`) |
| Library skill `frontend-design` (Apache-2.0, upstream anthropics/skills, pinned in `skills/frontend-design/UPSTREAM.md`) | installed with the other skills; `--skills` can deselect it |
| Third-party skills may ship `LICENSE`, `LICENSE.txt` or `LICENSE.md` | — |

## Compatibility notes (v2.9 → v2.10)

| Change | Impact |
|---|---|
| `smoke-tester` step 5 **Layout probe** (web UI): `tools/ui-probe.mjs` renders the changed screens at 375/768/1280/1440 plus a width sweep and reports horizontal scroll, clipped text, wrapped button labels, crowded targets under 24 px (WCAG 2.2 SC 2.5.8 with its spacing exception), contrast below WCAG AA, broken images, missing `alt`, unnamed controls; `tools/ui-probe-page.js` is the same measurement for any browser tool's evaluate | new evidence section *4. Layout probe* in the smoke report; confirmed findings on changed UI → `REQUEST_CHANGES`. The runner needs Node 18+ and Playwright outside the project (exit 3 prints how) or an installed Chrome/Edge; without either the step is skipped and noted |
| `tools/` added to `RUNTIME_SET` | shipped by the slim install |
| `frontend-design`: frontmatter `description` narrowed to marketing-facing pages (body unchanged; notice in the file and `UPSTREAM.md`); `AGENTS.md` §5 picks the design skill by surface — app screens → a web-app UI skill, evon `ui-ux` recommended | re-apply the description change when updating the skill from upstream |

## Compatibility notes (v2.10 → v2.11)

| Change | Impact |
|---|---|
| Task journal `runs/<task-id>/_journal.md`: the implementer appends one `## Session <time>` per working session (done / open / next / waiting on) with `orchestrator.py journal --task <id>`; rotates like role files (`_archive/_journal.md`, index of sessions) | `AGENTS.md` §5 and `omni-task` read it when resuming a task and write it when a session ends; artifacts are not split per day and not summarised by an agent |
| `orchestrator.py status --since <YYYY-MM-DD\|today\|yesterday\|<n>d> [--task <id>]`: activity by day across tasks, from report and journal timestamps (index rows of rotated files included); read-only (`lib/activity.py`) | `--task` is optional for `status` only when `--since` is given; `pm` STATUS / WEEKLY use it |

## Compatibility notes (v2.11 → v2.12)

| Change | Impact |
|---|---|
| After `pm` TASKING each ticket is its own work item: `runs/<ticket-id>/` with the ticket file as `--spec`; the epic folder keeps only spec, ADR, `tech-lead.md`, `pm.md`, `tasks/`; group QA passes get their own id. Ticket template gains a `Task id` line | projects that recorded every ticket under the epic id keep working; new tickets go to their own folders (moving old reports is the project's call) |
| Every role report is persisted with `orchestrator.py record` (tech-lead, pm, ba, architect REVIEW, qa-lead, release-manager included); hand edits only without Python | skills `omni-task`, `omni-plan`, `omni-review`, `omni-ship`, `architect`, `ba`, `pm`, `release` updated |
| **Fix**: `artifacts.append` used to drop text it had not written (a hand-written report) when it rewrote the hot file; that text now moves verbatim to `_archive/<role>.md` with an index row, and `record`/`journal`/`run` say so. `status --task` warns about role files written by hand | earlier hand-written role files lost nothing until a `record` hit them; check `_archive/` if one did |
| Repository / workspace layout is an owner decision: `omni-setup` asks for it when the repo has no product code or no recorded layout and writes it to `conventions.md` → `Architecture` + component paths; `architect` follows the recorded layout and returns `NEEDS_CLARIFICATION` instead of choosing one; `AGENTS.md`: standing owner decisions go into `project/`, a task's `decisions.md` binds that task only | a project whose layout was agreed only in chat should record it in `conventions.md` |
| Toolset in `.omni-team/.venv` (`lib/bootstrap.py`, in `RUNTIME_SET`): new `orchestrator.py setup [--ui-probe]` installs the Python environment (PyYAML) and, with `--ui-probe`, Playwright under `.venv/node` plus Chromium when no Chrome/Edge starts; `omni-setup` runs it as step 1 (steps renumbered 1–8). Every orchestrator command re-runs under the venv when it exists, and creates it when PyYAML is missing; `.venv/` is git-ignored and never touched by upgrades; `OMNI_TEAM_NO_BOOTSTRAP=1` keeps the current interpreter. `ui-probe.mjs` gains `--check` and looks in `.venv/node`. `AGENTS.md` / `omni-setup`: agents run `.omni-team/` commands themselves instead of handing them to the user | run `setup` once per project (or `/omni-setup`); CI with `pip install -r` keeps working. Offline machines: install PyYAML by hand or set the opt-out |

## Compatibility notes (v2.12 → v2.13)

| Change | Impact |
|---|---|
| Coordinator mode: the main agent delegates long work (plan phases, tickets, long suites, smoke runs) to background implementer sub-agents with a work order (`AGENTS.md` §5, template block) and stays responsive; it verifies the diff and Gate 0 before review, keeps the journal and `record`s reports. Non-negotiable #1: implementer sub-agents may edit code, review roles never. `CLAUDE.md`: Agent tool / fork, `isolation: "worktree"`, `run_in_background`. `omni-task` step 5 and `docs/workflow.md` updated | none; trivial work is still done directly, and tools without background sub-agents implement in-session |

## Compatibility notes (v2.13 → v2.14)

| Change | Impact |
|---|---|
| The repository is a Claude Code plugin marketplace: `.claude-plugin/marketplace.json` + `plugin.json` (plugin `omni-team` = repository root) with two skills, `/omni-team:install` and `/omni-team:upgrade`, that run `install.py --dir <git root>` / `install.py upgrade` from the plugin, then `orchestrator.py setup`. `plugin.json` → `version` follows `VERSION` (enforced by `tests/test_plugin.py`; definition-of-done updated). README, `docs/adapters.md`, `docs/repository-layout.md`, `AGENTS.md` §0 and `omni-setup` step 7 mention the plugin | none; installing from a checkout works as before. Claude Code users can switch to `/plugin install omni-team --marketplace ducquynhnguyeninfo/omni-team`; a team can enable it for a repository in `.claude/settings.json` (README) |

## Compatibility notes (v2.14 → v2.15)

| Change | Impact |
|---|---|
| Opt-in automation ([automation.md](automation.md), shipped). New profile key `automation` (`pr_fix: off \| commit \| push`, `protected_branches`, `branch_prefix` default `omni/`), merged key by key, validated loudly; default `off`. Never to the default or a protected branch, whoever asks: on one, `automation` exits 6 with the way forward (`git switch -c <prefix><task-id>`, push it, `gh pr create`); after an allowed push it prints the pull-request step. New `orchestrator.py automation --task <id> --action commit\|push` checks the boundaries before an unasked commit/push (work branch, Gate 0 green on the snapshot, no halted run; for a push every routed gate passed — pending or not run blocks — and a push target that is not the default or a protected branch) and exits 0 / 6; `classify` and `_summary.md` print the level. Critical rule §5, `AGENTS.md` §8 + non-negotiable 5, `_protocol.md` ownership table, `omni-task`, `omni-ship`, the generated pointer block and README now read "merge stays human; commit/push only when asked or per `automation.pr_fix`". `omni-setup` asks the user for the level | **none by default**: without an `automation` key the agent commits or pushes only when asked, as before. To opt in, add `automation: {pr_fix: commit}` (or `push`, with server-side protection of the default branch) to `project/profile.yaml` |
| Production control bands: optional `project/bands.yaml` and `orchestrator.py bands --metrics <file.json>` (`lib/bands.py`, deterministic; exit 0 normal/log · 1 diagnose · 6 propose); a breach enters the normal flow through `ba` | none; only projects that add `bands.yaml` and a scheduled job use it |
| Organisation enforcement examples: `examples/automation/managed-settings.json` (enable the plugin, deny force-push/merge, `git-guard.py` PreToolUse hook) and `examples/automation/pr-fix.yml` (GitHub Actions fix loop). `install.py` never writes managed-settings paths | none; admins deploy them deliberately |
| `orchestrator.py` argument parser moved to `lib/cli.py`; new runtime files `lib/automation.py`, `lib/bands.py`, `lib/cli.py`, `docs/automation.md` in `RUNTIME_SET` | none; `install.py upgrade` ships them |
