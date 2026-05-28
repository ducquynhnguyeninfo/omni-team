---
description: Create a new database migration
---

Create a new migration in `{{backend.root}}/{{database.migrations.versions_dir}}`:

```bash
cd {{backend.root}} && source .venv/bin/activate && {{database.migrations.cmd_new}} "$ARGUMENTS"
```

The `$ARGUMENTS` parameter is the migration description (required). Example:

```bash
/migrate-new "Add users table with email unique constraint"
```

After creating the migration, review the generated SQL in `{{database.migrations.versions_dir}}/` to ensure it matches your schema changes. Then commit and merge.
