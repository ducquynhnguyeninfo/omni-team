# Code quality limits

The same limits the reviewer agents enforce on host-project code apply to this repo. The framework's credibility depends on it eating its own dog food.

| Rule | Limit |
|------|-------|
| Lines per file | 500 |
| Lines per function | 100 |
| Function parameters | 8 |
| Nesting depth | 4 |

## Split strategies

**File too long** → split by responsibility, not by line count.

- [`lib/runner.py`](../lib/runner.py) getting big? Extract the verdict parser into `lib/verdict.py`. Don't dump 200 lines into a `_helpers.py`.
- A new `lib/` module that only one entrypoint uses can live next to that entrypoint until a second caller appears.

**Function too long** → extract by *what the chunk decides*, not by sequence.

- A 120-line function that does "validate → render → write" → three functions named after their decisions.
- A 120-line function that's mostly one straight-line algorithm is fine — limits exist to surface buried complexity, not to fragment readable code. If splitting hurts clarity, leave it and note the deliberate exception.

**Too many parameters** → introduce a small dataclass / TypedDict. Don't reach for `**kwargs`.

**Nesting too deep** → invert the condition (early return) or extract the inner block.

## Style conventions

- **No comments that restate the code.** Reviewer agents flag this; we should too. Comments explain *why*, never *what*.
- **No dead code.** Remove unused parameters, unused imports, unused helpers. If you're unsure whether something is used, grep it.
- **Type hints on public surface.** Every function in [`lib/`](../lib/) exposed to `bootstrap.py` / `orchestrator.py` gets parameter and return types. Internal helpers can skip them if obvious.
- **No silent fallbacks.** A missing manifest key fails loudly; an unrecognised verdict fails loudly. Silent defaults mask bugs — see [critical-rules.md](critical-rules.md) §3, §4.
- **Errors carry context.** When `bootstrap.py` reports an unresolved placeholder, it names the template file *and* the manifest path it tried. Same for any new failure mode.

## Tools

We don't pin a formatter/linter here yet — keep changes minimal and consistent with surrounding code. If you add one, document the command in [definition-of-done.md](definition-of-done.md).
