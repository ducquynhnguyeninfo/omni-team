---
name: ba
description: Invoke the omni-team Business Analyst — write a testable specification from a rough request or notes (stories, use cases, business rules, Given/When/Then acceptance criteria, NFRs, open questions), refine an existing spec against the Definition of Ready, or fill the business content of pm tickets. Use when the user types /ba, says "write the spec", "requirements", "user stories", "acceptance criteria", or when a task has no usable spec.
---

# /ba — requirements on demand

The request is in `$ARGUMENTS` (or the user's message). Mode: **SPEC** (default for a new request), **REFINE** (a spec path is given), **FILL** (pm ticket files are given).

1. Pick a task id (ticket id or short slug). Inputs to pass: the verbatim request/notes, any spec or ticket paths, and the spec location from `.omni-team/project/profile.yaml` (`work_unit.spec_root`).
2. Invoke the **`ba`** role as a sub-agent (Claude Code: Agent tool, `subagent_type: "ba"`; Codex: the `ba` custom agent; otherwise a sub-agent told to read `.omni-team/team/_protocol.md` and `.omni-team/team/ba.md`).
3. If it ends `NEEDS_CLARIFICATION`, put its questions to the user (with its proposed defaults), then re-invoke with the answers.
4. Save verbatim: SPEC/REFINE → `<spec_root>/<task-id>.md` when the project keeps specs there (ask before overwriting an existing spec), else `.omni-team/runs/<task-id>/spec.md`; FILL → write the business content back into each ticket file. Append a short log entry to `.omni-team/runs/<task-id>/ba.md`.
5. Report: path, number of stories / ACs, open questions that still need the user. Suggest the next step: `omni-plan <task-id>` (or `/architect` first if the spec implies a structural change).

Never write code; never commit.
