@./AGENTS.md

## Gemini CLI specifics

Gemini CLI has no omni-team sub-agent adapter. Run each gate in an independent process — `python3 .omni-team/orchestrator.py run-gate <role> --task <id> --engine <claude|codex|your-engine>` — or print its prompt with `orchestrator.py prompt <role> --task <id>` and run it in a fresh session. To use Gemini itself as a headless engine, add it under `orchestrator.engines` in `project/profile.yaml` (see `docs/adapters.md`). `python3 .omni-team/install.py --tools gemini` adds a pointer to this team in the root `GEMINI.md`.
