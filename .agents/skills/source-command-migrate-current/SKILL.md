---
name: "source-command-migrate-current"
description: "Show the current database migration version"
---

# source-command-migrate-current

Use this skill when the user asks to run the migrated source command `migrate-current`.

## Command Template

Display the currently applied migration version in `api/`:

```bash
cd api &&  pnpm typeorm migration:show -d src/database/data-source.ts
```

Use this to verify that migrations have been applied in dev/staging/prod, or to diagnose migration state conflicts.
