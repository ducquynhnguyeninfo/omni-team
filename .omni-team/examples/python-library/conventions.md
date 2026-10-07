# Project conventions — tidyframe

## All roles

- The public API is everything re-exported from `src/tidyframe/__init__.py` plus `src/tidyframe/api/`. Anything else is private even without a leading underscore.
- Versioning is SemVer; breaking the public API requires a major version and a deprecation period of one minor release.

## Architecture

- `api/` — thin public functions; `core/` — engine-independent logic; `adapters/pandas.py`, `adapters/polars.py` — engine specifics, imported lazily so the extras stay optional.
- `core/` **MUST NOT** import pandas or polars.
- Reference implementation: `api/validate.py` → `core/validation.py` → `adapters/*`.

## Cross-cutting invariants

- No I/O or global state at import time.
- Public functions are fully type-annotated; `py.typed` ships in the wheel.
- Errors: subclasses of `tidyframe.errors.TidyError` only; messages name the offending column.

## Tech lead

- Changes to the public API or the schema format need an RFC in `docs/rfcs/` first — flag missing RFCs as an open question.

## Code review

- **CRITICAL**: a public signature changed incompatibly without a `DeprecationWarning` shim; `core/` importing an engine.
- **WARNING**: public function without a docstring example (rendered by mkdocstrings); new runtime dependency (must be an optional extra unless agreed).

## Testing

- `tests/` mirrors `src/`; both engines tested via the `engine` fixture (`tests/conftest.py`).
- **P0**: every public function has a test per engine; every deprecation shim has a test asserting the warning.
- Hypothesis property tests for normalisers (`tests/property/`).

## Data & migrations

- `schema/` defines the JSON format users save schemas in (`schema_version` field). Readers must accept the previous major `schema_version`; removing a field is a wire-format break (DR-6).

## Security

- `schema.load()` parses untrusted files: no `eval`, no `yaml.load` without `SafeLoader`, size limits enforced.

## Performance

- No tiers; budget: validation of 1M rows × 20 columns ≤ 2 s on the benchmark (`benchmarks/`); no per-row Python loops in adapters.

## Acceptance

- `CHANGELOG.md` entry; docs page or docstring example for new public API; `__all__` updated.

## Smoke testing

- Build the wheel (`hatch build`), install it into a fresh temp venv with each extra (`[pandas]`, `[polars]`), and run the docstring example of the new API in a throwaway script.

## Project management

- Two core maintainers (review capacity ~5 h/week each); roadmap in `docs/roadmap.md`, one minor release per quarter.
- Prioritise with RICE; deprecations must be scheduled one minor release ahead. Reports in English, audience = contributors.

## Glossary

- **Engine** — the dataframe backend (pandas or polars). **Normaliser** — a pure function column → column.
