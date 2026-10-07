# Code quality (framework Python)

The limits the reviewers enforce on host projects apply to this repo too.

| Rule | Limit |
|---|---|
| Lines per file | 500 |
| Lines per function | 100 |
| Function parameters | 8 (keyword-only beyond that is still a smell) |
| Nesting depth | 4 |

## Split strategies

- **File too long** → split by responsibility (e.g. move verdict parsing out of `runner.py` into `verdict.py`), not into a `_helpers.py` grab-bag.
- **Function too long** → extract by *what the chunk decides*. A long straight-line function that reads well can stay; note the exception.
- **Too many parameters** → a small dataclass, not `**kwargs`.
- **Nesting too deep** → early returns or extracted helpers.

## Style

- Comments explain *why*, never restate *what*.
- No dead code, unused imports or parameters.
- Type hints on every function used across modules. Keep runtime syntax Python 3.8-compatible (`from __future__ import annotations`, `typing.List` etc. in runtime positions; no `match`, no `X | Y` outside annotations).
- `install.py` and everything it imports (`lib/roles.py`, `lib/adapters.py`) stay stdlib-only.
- Errors carry context: name the file, key or role that is wrong and what was expected.
- No silent fallbacks (see [critical-rules.md](critical-rules.md) §3).

## Tooling

No formatter is pinned. Keep changes consistent with surrounding code. If you add a linter, document its command in [definition-of-done.md](definition-of-done.md).
