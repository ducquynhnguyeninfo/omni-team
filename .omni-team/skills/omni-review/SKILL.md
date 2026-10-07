---
name: omni-review
description: Review the current change (working tree vs the default branch, or a given base/PR) with the omni-team review gates selected by the routing rules — code-reviewer, test-engineer, data-reviewer, security-engineer, perf-engineer — run serially, with a fix-and-recheck loop. Use when the user says "omni-review", "review with the team", or asks for a multi-angle review before commit.
---

# omni-review — routed review gates for the current change

Input (optional): task id, base ref, focus paths (`$ARGUMENTS`).

1. **Scope** — default: everything changed since the merge-base with the default branch, including uncommitted and untracked files. Pick a task id (branch name slug if none given).
2. **Route** — preferred: `python3 .omni-team/orchestrator.py classify --task <id> [--base <ref>]` and use the printed gate list. Without Python/PyYAML: evaluate the `signals` and `routing` sections of `.omni-team/defaults.yaml` (plus overrides in `.omni-team/project/profile.yaml`) against `git diff` yourself and state which rules matched.
3. **Gate 0, then stages.** Run `python3 .omni-team/orchestrator.py checks --task <id>` (or the project's checks by hand) — stop on red. Then run the gates stage by stage: all gates of one stage together, the next stage only after the previous passed. Each gate is a fresh sub-agent given: task id, base ref, changed-file list, artifacts folder `.omni-team/runs/<id>/`, and the attempt number. Append each report verbatim to `.omni-team/runs/<id>/<role>.md`.
4. **Loop** — on `REQUEST_CHANGES` / `BLOCK`: if the user asked you to fix, fix, re-run Gate 0 and re-invoke that gate (max 3 rounds), plus any approved gate whose area the fix touched; otherwise collect the findings and continue to the next gate. `NEEDS_CLARIFICATION` / `BLOCKED` → stop and ask.
5. **Report** — a table of gate → verdict → top findings, plus the path to each report. Never commit or push.

Headless alternative (separate processes, no context sharing): `python3 .omni-team/orchestrator.py run --task <id> --engine claude|codex`.
