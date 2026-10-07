# Project conventions

<!--
This file is the project-specific rulebook every omni-team role reads at run
time (after profile.yaml). It is intentionally free-form Markdown: write the
rules the way you would explain them to a new senior engineer.

- Keep the section headings below: each role looks for its own section.
- Leave a section as "(none)" if it does not apply. Empty is fine — roles then
  fall back to patterns in the existing code plus general best practice.
- Mark severity where it matters: "MUST NOT" / "CRITICAL" → the role blocks;
  "SHOULD" → request changes.
- Point to files instead of copying them ("error type: src/errors.ts").
- Run the `omni-setup` skill to have an agent draft this from the repository.
See ../examples/*/conventions.md for filled-in samples.
-->

## All roles

(none)

## Architecture

<!-- Components, layers and allowed dependency directions; where each kind of
code lives; the reference feature new work should mirror. -->

(none)

## Cross-cutting invariants

<!-- Rules that hold everywhere: error contract, soft-delete, tenancy,
idempotency, i18n locales, logging policy, feature flags … -->

(none)

## Tech lead

<!-- Design docs worth reading, preferred phase ordering, split thresholds. -->

(none)

## Code review

<!-- Must-not rules and preferred patterns per component/stack. -->

(none)

## Testing

<!-- Test layout, mandatory test types (P0), fixtures/factories, what must be
integration-tested, frameworks per component. -->

(none)

## Data & migrations

<!-- Engine, migration tool + commands, naming, required columns, vendor-owned
schemas never to touch, rules for unique indexes / constraints. -->

(none)

## Security

<!-- Auth mechanism and guard helpers, cookie/token rules, PII field list and
storage pattern, extra trigger paths, secret management. -->

(none)

## Performance

<!-- Tier table / budgets, cache helpers, known hot paths, slow-path
registration rules. -->

(none)

## Acceptance

<!-- Extra checks qa-lead must run on every work item (docs, changelog,
wireframe parity, feature flags …). -->

(none)

## Smoke testing

<!-- How to start the stack (command), test accounts (never real secrets —
point to where they live), wireframe/prototype location, whether the
smoke-tester may start services itself. -->

(none)

## Project management

<!-- For the pm role: delivery team (person/role, seniority, skills, capacity
h/week, focus factor, WIP limit), cadence (sprints, milestones, release dates),
stakeholders and report audience, report language, estimation unit, where the
tracker and PM documents live (e.g. docs/pm/), reporting template. -->

(none)

## Glossary

<!-- Domain terms and abbreviations agents should understand. -->

(none)
