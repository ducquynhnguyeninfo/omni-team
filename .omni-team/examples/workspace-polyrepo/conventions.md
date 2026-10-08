# Project conventions — Acme Marketplace (workspace)

## All roles

- This is a private workspace. `backend/` and `mobile/` are separate git repositories that are delivered to the client; never add AI files, agent reports or AI-related ignore rules inside them.
- Read diffs per repository (`git -C backend diff …`, `git -C mobile diff …`); commit and push each repository separately (humans only).
- Specs, ADRs and PM documents live in `docs/` of the workspace, not in the product repos.

## Requirements

- Stories in `docs/stories/ACME-*.md` with Given/When/Then acceptance criteria.

## Architecture

- Backend: see `backend/docs/architecture.md` (apps per bounded context; services hold business logic, views stay thin).
- Mobile: see `mobile/docs/architecture.md` (feature folders; server state via TanStack Query hooks only).
- The mobile app talks to the backend only through the public REST API (`backend/openapi.yaml`); a contract change needs both repos updated in the same story.
- ADRs: `docs/adr/NNNN-*.md`.

## Cross-cutting invariants

- API errors: `{"code", "message", "details"}` (`backend/api/errors.py`).
- Money in integer minor units; currencies ISO 4217.
- All user-visible mobile strings through i18next (`mobile/locales/{en,de}.json`).

## Tech lead

- A story touching both repos lists backend phases first, then mobile, with the API contract change as the boundary.

## Code review

(none beyond Architecture and invariants)

## Testing

- Backend: pytest with factories in `backend/tests/factories.py`; P0: permission denial per new endpoint.
- Mobile: jest + React Native Testing Library; P0: loading / error / empty state per new screen.

## Data & migrations

- Django migrations only (`python manage.py makemigrations`); never edit an applied migration.

## Security

- JWT access tokens (15 min) + rotating refresh tokens; the mobile app stores tokens in the OS secure store only.

## Performance

(none)

## Acceptance

- Contract changes: `backend/openapi.yaml` updated and the mobile client regenerated in the same story.

## Smoke testing

- Backend: `docker compose up -d` in `backend/`; smoke via HTTP requests. Mobile: not automated — return BLOCKED with manual steps.

## Project management

(none)

## Release

- Each repository is versioned and released on its own; the workspace is never tagged or delivered.

## Glossary

- **Workspace** — the private repo holding tooling and documents; **product repo** — a delivered repository.
