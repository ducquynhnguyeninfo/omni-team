---
name: omni-task
description: Run a work item end to end with the omni-team review team — classify, plan with tech-lead, implement, run Gate 0 checks and the routed review gates stage by stage, acceptance (qa-lead, smoke-tester), then stop at the human gate. Use when the user asks to build, fix or change something non-trivial and wants it reviewed by the team, or says "omni-task", "use the team", "run omni-team".
---

# omni-task — full team flow for one work item

Input: a request, a ticket/spec id, or a spec path (from the user's message or `$ARGUMENTS`).

Follow `.omni-team/AGENTS.md` — it is the authoritative playbook. Condensed:

1. **Context** — read `.omni-team/project/profile.yaml` and `.omni-team/project/conventions.md`. Pick a task id (ticket id, or a short slug like `add-export-csv`); the artifacts folder is `.omni-team/runs/<task-id>/`.
2. **Classify** — estimate size and touched areas. Trivial (≲15 changed lines, no sensitive area): implement, run checks, report — no gates.
3. **Plan** — non-trivial: invoke the `tech-lead` role with the request/spec. Save its report verbatim to `<artifacts>/tech-lead.md`. If it ends `NEEDS_CLARIFICATION`, ask the user its open questions before coding.
4. **Implement** — you (the main agent) implement the plan phase by phase, mirroring existing patterns. Run Gate 0 until green: `python3 .omni-team/orchestrator.py checks --task <id>` (or the profile `checks` / component `commands` by hand).
5. **Review** — determine the gates: run `python3 .omni-team/orchestrator.py classify --task <id>` if Python + PyYAML are available, otherwise apply `routing` from `.omni-team/defaults.yaml` (+ overrides in the profile) by hand. Invoke the gates **stage by stage** as fresh sub-agents — all gates of one stage together, the next stage only after the previous passed; append each report to `<artifacts>/<role>.md`.
   - `APPROVE` / `NOT_APPLICABLE` → next gate.
   - `REQUEST_CHANGES` / `BLOCK` → fix the findings, re-run Gate 0, re-invoke the same gate. Max 3 rounds per gate, then stop and escalate to the user.
   - After fixes, re-run any already-approved gate whose area your fixes touched (the orchestrator calls this "re-opened").
   - `NEEDS_CLARIFICATION` / `BLOCKED` → stop and ask the user.
6. **Accept** — `qa-lead` (and `smoke-tester` if routed) run last, same loop.
7. **Hand off** — write `<artifacts>/_summary.md` (gates, verdicts, fixes made, deferred items) and tell the user it is ready for **their** review. **Never commit, push or merge.**

How to invoke a role depends on the tool — see `.omni-team/AGENTS.md` §"Invoking a role". If the role is not registered as a native sub-agent, give a general-purpose sub-agent this prompt: "Read `.omni-team/team/_protocol.md` and `.omni-team/team/<role>.md` and act as that role for: <scope>."
