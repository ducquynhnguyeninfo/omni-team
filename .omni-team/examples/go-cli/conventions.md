# Project conventions — logpipe

## All roles

- There are no specs; the acceptance source is the GitHub issue text the implementer passes, or `tech-lead.md`.

## Architecture

- `cmd/logpipe/` — cobra wiring only: flags, argument parsing, calling `internal/app`. **MUST NOT** contain business logic.
- `internal/app/` — use cases; depends on interfaces in `internal/ports/`.
- `internal/sink/`, `internal/source/` — adapters (S3, stdout, file, journald) implementing the ports.
- `internal/format/` — log record encoding (JSON lines, logfmt); its output is a public contract.
- Reference implementation: the `tail` command (`cmd/logpipe/tail.go` → `internal/app/tail.go`).

## Cross-cutting invariants

- Errors are wrapped with context: `fmt.Errorf("open %s: %w", path, err)`; never `panic` outside `main`.
- Every blocking operation takes a `context.Context` as first parameter and honours cancellation.
- Exit codes: 0 success, 1 runtime error, 2 usage error (see `internal/app/exitcodes.go`). Changing one is a breaking change.
- Logging via zerolog to stderr only; stdout is reserved for data.

## Tech lead

- Split work touching more than one sink into one issue per sink.

## Code review

- **CRITICAL**: goroutines without a cancellation path; ignored errors (`_ =` on an error) outside tests; writing logs to stdout.
- **WARNING**: exported identifiers without doc comments; flags without a `--help` description; interface defined on the implementer side instead of the consumer side.

## Testing

- Table-driven tests next to the code (`*_test.go`); golden files under `testdata/` for `internal/format` (update with `go test ./internal/format -update`).
- **P0**: every new flag has a test through the cobra command; every new sink has a test with a fake client.
- Race detector must pass (`go test -race`).

## Data & migrations

- No database. `internal/format/` output and the config file schema (`config.example.yaml`) are contracts: removing or renaming a field is DR-6 (wire-format break) unless the CHANGELOG has a deprecation entry.

## Security

- AWS credentials only through the SDK default chain; **MUST NOT** accept secrets as flags (they leak into shell history).
- File paths from config are cleaned with `filepath.Clean` and must not escape `--root` when set.

## Performance

- Hot path: `internal/app/pipeline.go` — no allocations per record beyond the encoder buffer; batch S3 uploads (≥ 5 MiB parts).
- Every network call has a timeout derived from the context.

## Acceptance

- `CHANGELOG.md` updated under *Unreleased* for any user-visible change.
- `README.md` usage section updated for new commands or flags.

## Smoke testing

- Build with `go build -o bin/logpipe ./cmd/logpipe`, then run in a temp dir, e.g. `printf '{"lvl":"info"}\n' | ./bin/logpipe filter --level info`.
- S3 sink: use `--sink file://$TMPDIR/out` instead of real buckets; never touch real AWS accounts.

## Project management

- Single maintainer plus occasional contributors; no sprints — milestones are tagged releases (`vX.Y.0` roughly monthly).
- Backlog = GitHub issues labelled `planned`; prioritise with value-vs-effort. Status reports go in the release-tracking issue, in English.

## Glossary

- **Sink** — output adapter. **Source** — input adapter. **Record** — one structured log line.
