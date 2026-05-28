---
description: Run frontend quality gate — linter + type check + tests
---

Run the full frontend quality gate from `{{frontend.root}}/`:

```bash
cd {{frontend.root}} && {{frontend.test_cmd}}
```

Report which step failed (lint / typecheck / tests) and the first 20 lines of the relevant output. If everything passes, report "frontend gate: ✅ green".

Argument (optional): `$ARGUMENTS` — a test file path or glob selector. When empty, runs the full suite.
