---
name: omni-plan
description: Ask the omni-team tech-lead for a phased implementation plan of a request, ticket or spec before writing code — acceptance criteria, existing partial work, files in dependency order, edge cases, open questions. Use when the user says "omni-plan", "plan this with the team", or wants a plan only.
---

# omni-plan — plan a work item with the tech-lead

Input: a request, a ticket/spec id, or a spec path (`$ARGUMENTS` or the user's message).

1. Choose a task id (ticket id or short slug). Artifacts folder: `.omni-team/runs/<task-id>/`.
2. Invoke the **`tech-lead`** role as a sub-agent (see `.omni-team/AGENTS.md` §"Invoking a role") with:
   - the task id and the request text or spec path,
   - any constraints the user stated.
3. Append the report verbatim to `.omni-team/runs/<task-id>/tech-lead.md` (create folders as needed).
4. Show the user: the acceptance criteria, the phase list, and every open question. If the verdict is `NEEDS_CLARIFICATION`, ask those questions and re-plan once answered.
5. Do **not** start implementing unless the user asked for it (then continue with `omni-task` from step 4).
