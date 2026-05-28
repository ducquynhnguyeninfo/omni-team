---
description: Show the current database migration version
---

Display the currently applied migration version in `{{backend.root}}/`:

```bash
cd {{backend.root}} && source .venv/bin/activate && {{database.migrations.cmd_current}}
```

Use this to verify that migrations have been applied in dev/staging/prod, or to diagnose migration state conflicts.
