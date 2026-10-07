# Project conventions — Example Fullstack MVP

## All roles

- Specs live in `document/sprints/<sprint>/<MP-ID>/`; read the companion `plan.md` / `architecture.md` when present.
- Codex cross-check is the human gate after `qa-lead` and `smoke-tester`.

## Architecture

- Backend layer order: `models → schemas → repos → services → routers → register in main.py`.
- Call direction `router → service → repo`; reverse is forbidden.
- Routers: parse HTTP, call a service, return. **MUST NOT** run SQL or contain business logic.
- Services: business orchestration, own the transaction (`db.commit()`). **MUST NOT** run SQL directly or make HTTP calls to the frontend.
- Repos: DB queries only (`db.execute`, `select(`, `insert(`, `update(`, `delete(`). **MUST NOT** commit (exception: standalone utility scripts).
- Frontend: API clients/types under `lib/<feature>/`; state + fetching in hooks `components/<portal>/<feature>/hooks/use-*.ts`; components render only.
- Reference implementation to mirror: the `intake` feature (`app/routers/intake.py`, `app/services/intake_service.py`, `apps/web/lib/intake/`).

## Cross-cutting invariants

- **Error contract (CRITICAL)**: every `HTTPException.detail` is `LeanApiError` — `{"error_code": "...", "message": "..."}` (`app/schemas/api_error.py`).
- **Soft-delete (CRITICAL)**: every query on a `SoftDeleteMixin` model filters `.where(<Model>.deleted_at.is_(None))`; deletes go through the soft-delete helper.
- **Sorting (CRITICAL)**: never `getattr(Model, sort_by)` from client input — use the whitelisted ordering helper.
- **i18n (CRITICAL on public portal)**: every user-visible string goes through `useTranslations` / `t()` and exists in `apps/web/messages/{en,vi,fr}.json`. Admin portal (`app/admin/`, `components/admin/`) currently hardcodes English — treat i18n there as INFO.
- **UI**: shadcn/ui primitives only.
- **Schema changes**: Alembic only, via `make migrate-new msg="..."`.
- **Idempotency**: LLM, external and background side effects use `build_idempotency_key()` (`app/services/idempotency.py`).

## Tech lead

- Design docs: `docs/ARCHITECTURE.md` (domain), `docs/SESSION_MODEL.md` (session/flow data), `docs/AUTH_FLOW.md` (auth, cookies, proxy).
- Phase order: Schema → DTOs → Repo → Service → Router (+ register in `main.py`) → Tests → Frontend (api client, components, messages ×3).
- LLM endpoints: plan registration in `_LLM_PATHS` (`main.py`) and an idempotency key.

## Code review

- Backend: Pydantic v2 only (`model_config`, `@field_validator`, `.model_validate()`, `.model_dump()`); prefer `X | None` over `Optional[X]`.
- Frontend: no `any`; backend calls from proxied portals **MUST** use `apiGet` / `apiPost` (or `fetchViaProxy` in RSC) from `@/lib/admin` — exception: the public intake flow in `lib/intake/api.ts`.
- Admin detail panels: actions on the right of the title row, ordered toggle → primary → secondary → destructive (edit mode only).
- WARNING: inconsistent i18n namespaces for the same area (`intake.submit` vs `forms.submit_intake`).

## Testing

- Backend: pytest under `example-backend/tests/test_*.py`; every new repo function on a soft-delete table is tested for live-only reads and already-deleted rows (P0).
- Idempotent handlers: a replay test asserting same response and no second side effect (P0).
- Frontend has no test runner by design — coverage comes from `qa-lead` + `smoke-tester`.

## Data & migrations

- Engine PostgreSQL 16 on Supabase; tool Alembic (`example-backend/alembic/versions/`). Commands: `make migrate-new msg="..."`, `make migrate-up`, `make migrate-down`, `make migrate-current`, `make migrate-sql` (offline preview, safe to run).
- **MUST NOT** reference Supabase-owned schemas `auth.*`, `storage.*`, `realtime.*`; `app/models/_auth_reflected.py` is a read-only reflection.
- Unique indexes on soft-delete tables **MUST** be partial: `postgresql_where=text("deleted_at IS NULL")`.
- Postgres FKs cannot reference a partial unique index — when replacing a `UniqueConstraint` with a partial index, grep for FKs targeting the column and BLOCK if any exist.
- CHECK-constraint enum changes: drop and re-create, never alter.
- RLS policies live in `example-backend/scripts/rbac_public.sql` (outside Alembic); new tenant tables need a policy there.

## Security

- Auth guard: `Depends(get_current_user_id)` on every protected route.
- Auth cookies: `HttpOnly`, `SameSite=Strict`, `Secure` in production; login/refresh return user + expiry, never the JWT.
- Refresh rotates access **and** refresh tokens; logout calls Supabase `signOut` **and** clears both cookies.
- PII: email, phone, address, password, payment, government ID — never logged; email stored as `email_normalised` + `email_hash` (see `session_actor`).

## Performance

| Tier | Budget | Pattern |
|---|---|---|
| A — LLM | ≤ 15 000 ms | endpoints calling OpenRouter |
| B — DB complex | ≤ 500 ms | multi-table joins, complex pagination |
| C — DB simple | ≤ 150 ms | simple CRUD |
| D — Lightweight | ≤ 50 ms | cache hits, health |

- Tier A endpoints **MUST** be registered in `_LLM_PATHS` (`main.py`), use an idempotency key and a client timeout; prompts come from the `prompt_templates` table.
- Reference data (country, industry) goes through `mapping_service`, never re-queried.
- Async paths: `httpx.AsyncClient`, not `requests`; no blocking `time.sleep` or sync file I/O.
- Baseline: `example-backend/docs/PERFORMANCE_BASELINE.md`.

## Acceptance

- New routers registered in `main.py`; new pages have a sidebar entry.
- Wireframe parity: if `example-frontend/wireframe-prototype/<feature>.tsx` exists, every field/label/hint in it exists in the implementation (missing → MISSING).

## Smoke testing

- Start: `docker compose -f infra-dev/docker-compose.yaml up -d` (the smoke-tester must not start it itself).
- Browser tool: Chrome DevTools MCP. Wireframes: `example-frontend/wireframe-prototype/`.
- Test accounts: see `document/dev-accounts.md` (local only, not committed secrets).

## Glossary

- **MP** — Mini Package, the unit of work inside a sprint.
- **Portal** — one of: public website, customer portal, admin portal.
