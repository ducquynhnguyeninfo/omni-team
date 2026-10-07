---
name: pm
description: Invoke the omni-team Project Manager for a standalone PM task — project charter, work breakdown + roadmap, status or weekly report, RAID review, backlog prioritisation, TASKING (tech-lead plan → MECE assignable tickets) or retrospective. Use when the user types /pm, says "pm", "project manager", "status report", "weekly report", "RAID", "prioritize the backlog", "break this into tickets", or "retro".
---

# /pm — Project Manager on demand

The request is in `$ARGUMENTS` (or the user's message). If it is empty, ask which artifact they want — charter · plan (WBS + roadmap) · status · weekly report · RAID · prioritise · tasking · retro — and for which project / release / task.

## Steps

1. **Pick the subject and artifact location** (relative to the project root; `artifacts_dir` in the profile, default `.omni-team/runs/{task_id}`):
   - Tied to one work item (the request names a task/ticket id) → `.omni-team/runs/<task-id>/pm.md` (append). For **TASKING**, the board and tickets go to `.omni-team/runs/<task-id>/tasks/`.
   - Project / release / sprint level → the PM documents location from `.omni-team/project/conventions.md` → `Project management`, else `.omni-team/runs/pm/<mode>-<topic>-<YYYY-MM-DD>.md`.
2. **Gather inputs for the PM**: for TASKING, make sure `.omni-team/runs/<task-id>/tech-lead.md` exists — if not, run the `tech-lead` role first (or ask the user). For STATUS/WEEKLY, point it at the relevant `runs/` folders and the period to cover.
3. **Invoke the `pm` role** as a sub-agent (Claude Code: Agent tool, `subagent_type: "pm"`; Codex: the `pm` custom agent; otherwise a sub-agent told to read `.omni-team/team/_protocol.md` and `.omni-team/team/pm.md`). The prompt contains:
   - the verbatim user request and the mode if known;
   - the subject (project / release / sprint / task id), period and audience if stated;
   - paths to the inputs from step 2;
   - the reminder: owns scope, schedule, risk, dependencies and communication; routes the technical "how" to `tech-lead`; never writes code; returns one artifact with owners, dates and decisions-needed.
4. **Persist verbatim** (mandatory): append the report to the file from step 1 under a heading with the timestamp and mode. For TASKING, split the output on the `<!-- file: … -->` markers into `tasks/_board.md` and `tasks/<n>.<slug>.md`. Add an `### Actions taken by implementer` note (what you actioned vs deferred).
5. **Report back** in 3–5 lines: the artifact, its path, the health verdict if any, and every **decision needed** that requires the user.

## Notes

- If the PM ends with `VERDICT: NEEDS_CLARIFICATION`, ask the user its question and re-invoke.
- Management-facing artifacts (charter, status, weekly) must stay at business altitude — if the output leaks commit hashes, file paths or agent names, ask the PM to rewrite it.
- `/pm` is separate from the delivery pipeline (`omni-task`); it never commits, pushes or changes code.
- Headless alternative: `python3 .omni-team/orchestrator.py prompt pm --task <id> --request "<request>"` prints the full prompt for any tool; `run-gate pm --task <id> --request "…"` runs it through an engine.
