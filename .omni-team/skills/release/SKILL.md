---
name: release
description: Invoke the omni-team Release Manager — PREPARE a release from the changes since the last tag (semver recommendation, changelog entry, release notes, upgrade notes, deploy plan, rollback plan and triggers, post-deploy verification), or run the READINESS go/no-go check. Use when the user types /release, says "cut a release", "prepare release notes", "changelog", "version bump", "are we ready to deploy?", or "go/no-go". Never tags, publishes or deploys.
---

# /release — prepare and gate a release

The request is in `$ARGUMENTS` (or the user's message). Mode: **PREPARE** (default) or **READINESS** ("ready?", "go/no-go"). Optional: target version, range (`<from>..<to>`), environment.

1. Determine the range: from the caller, else from the last tag (`git describe --tags --abbrev=0`) to `HEAD`. Release id = the proposed version or `next` (artifacts: `.omni-team/runs/release-<id>/`).
2. Invoke the **`release-manager`** role as a sub-agent (Claude Code: `subagent_type: "release-manager"`; Codex: the `release-manager` custom agent; otherwise a sub-agent told to read `.omni-team/team/_protocol.md` and `.omni-team/team/release-manager.md`) with the mode, range, target environment, and the path to `.omni-team/runs/`.
3. Save the report verbatim to `.omni-team/runs/release-<id>/release-manager.md`.
4. PREPARE: show the version recommendation, the changelog entry and release notes, and **offer** to apply them (version files, `CHANGELOG`) — apply only after the user agrees. READINESS: show the go/no-go table; on `BLOCK`/`REQUEST_CHANGES` list exactly what is missing.
5. Tagging, publishing and deploying stay with the humans. Print the commands from `conventions.md` → `Release` for them to run; never run them yourself.
