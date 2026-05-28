---
description: Run backend quality gate — linter + formatter + tests
---

Run the full backend quality gate from `{{backend.root}}/`:

```bash
cd {{backend.root}} && source .venv/bin/activate && {{backend.test_cmd}}
```

Report which step failed (lint / format / tests) and the first 20 lines of the relevant output. If everything passes, report "backend gate: ✅ green".

Argument (optional): `$ARGUMENTS` — a path or `tests/test_X.py::test_name` selector to run pytest against. When empty, runs the full suite.
