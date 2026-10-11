# Project rules

- Multi-tenant SaaS: one database, every tenant-owned row carries `tenant_id`. Every read or write of a
  tenant-owned model (`Customer`, `Order`, `Invoice`) goes through `scoped(session, Model, ctx)` from
  `app/tenancy.py`, which adds the tenant filter. Never call `session.query(...)` on those models directly.
- Never log credentials, tokens or whole request headers; log `safe_headers(headers)` from
  `app/logging_utils.py` if headers are needed.
