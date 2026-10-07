---
name: architect
description: Invoke the omni-team Architect — DESIGN mode writes an Architecture Decision Record (options, trade-offs, decision, consequences, diagram) before a structural change; REVIEW mode checks the current change for architectural drift (new components, dependencies, integrations, infrastructure, contract or data-flow changes). Use when the user types /architect, asks for an ADR, a design decision, "should we use X or Y", or an architecture review.
---

# /architect — architecture decisions and reviews

The request is in `$ARGUMENTS` (or the user's message). Mode: **DESIGN** when a decision or new design is asked for; **REVIEW** when the user asks to check the current change.

1. Pick a task id. Gather inputs: the spec (`<spec_root>/<id>.md` or `.omni-team/runs/<id>/spec.md`), any `tech-lead.md` notes, and — for REVIEW — the scope (`python3 .omni-team/orchestrator.py classify --task <id>` prints it; otherwise `git diff --stat` against the default branch plus untracked files).
2. Invoke the **`architect`** role as a sub-agent (Claude Code: `subagent_type: "architect"`; Codex: the `architect` custom agent; otherwise a sub-agent told to read `.omni-team/team/_protocol.md` and `.omni-team/team/architect.md`). Tell it the mode.
3. Save verbatim:
   - DESIGN → the project's ADR folder from `conventions.md` → `Architecture` (else `docs/adr/` if it exists) as `NNNN-<slug>.md` with the next number — **ask the user before creating files outside `.omni-team/`**; otherwise `.omni-team/runs/<id>/adr.md`. The ADR status stays *Proposed* until a human accepts it.
   - REVIEW → append to `.omni-team/runs/<id>/architect.md`.
4. Report: the decision (or verdict), trade-offs accepted, decisions the user must confirm. After an accepted ADR, the next step is `omni-plan <id>`.

Never write code; never commit.
