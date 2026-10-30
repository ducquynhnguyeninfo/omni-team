---
name: omni-ship
description: Final acceptance for a finished work item with omni-team — qa-lead walks every acceptance criterion against code and tests, smoke-tester exercises the running feature when applicable, then a hand-off summary for the human gate. Use when implementation and reviews are done and the user says "omni-ship", "acceptance check", or "is this ready to ship?". Never merges; commits or pushes only per the project's automation level.
---

# omni-ship — acceptance and hand-off

Input: task id (and spec path if not discoverable) — `$ARGUMENTS` or the user's message.

1. Confirm the artifacts folder `.omni-team/runs/<task-id>/` exists; read earlier gate reports. If a gate's last verdict is not `APPROVE`/`NOT_APPLICABLE`, tell the user and stop unless they say to proceed.
2. Invoke **`qa-lead`** with the task id, the acceptance source (spec path, or `tech-lead.md` in the artifacts folder, or the original request) and the artifacts folder. Persist the report with `python3 .omni-team/orchestrator.py record qa-lead --task <id> < report.md`. Fix-and-recheck on `REQUEST_CHANGES` (max 3 rounds) if the user wants fixes.
3. If the change has runnable user-facing behaviour (UI, API, CLI, library surface) or routing selected it, invoke **`smoke-tester`**. It needs the app running: if it returns `BLOCKED`, show the user the command it suggests and wait.
4. Write `.omni-team/runs/<task-id>/_summary.md`: gate → verdict table, fixes made, deferred items, open questions, and the human gate from the profile (`human_gate`).
5. Tell the user it is ready for **their** review. Commit or push only when the user asks or `automation.pr_fix` allows it (`orchestrator.py automation --task <id> --action commit|push` exits 0) — on a work branch, never the default or a protected one: from there, switch to the work branch it names, push it and open a pull request (`.omni-team/AGENTS.md` §8). Never merge or tag.
