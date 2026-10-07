# Repository layout

```
.omni-team/                       the whole framework — copy this folder into any project
├── AGENTS.md                     operating manual for any AI agent (entry point)
├── CLAUDE.md                     Claude Code entry: imports AGENTS.md + Claude specifics
├── GEMINI.md                     Gemini CLI entry: imports AGENTS.md + Gemini specifics
├── README.md                     human quick start
├── VERSION                       framework version (semver)
├── requirements.txt              PyYAML — orchestrator only
├── defaults.yaml                 default signals, routing, engines, limits (framework data)
│
├── team/                         canonical role definitions (tool-agnostic)
│   ├── _protocol.md              shared rules: context, scope, severity, verdict, read-only
│   ├── ba.md  architect.md  pm.md  tech-lead.md  code-reviewer.md  test-engineer.md
│   ├── data-reviewer.md  security-engineer.md  perf-engineer.md  qa-lead.md
│   └── smoke-tester.md  release-manager.md
│
├── skills/                       workflow entry points (SKILL.md works in Claude Code and Codex)
│   └── omni-setup/  omni-task/  omni-plan/  omni-review/  omni-ship/  ba/  architect/  pm/  release/
│
├── project/                      ← the ONLY folder a host project edits
│   ├── profile.yaml              structured facts (auto by default)
│   └── conventions.md            rulebook, one section per role
│
├── examples/                     sample project/ folders: web-fastapi-nextjs, go-cli, python-library
│
├── install.py                    adapters: .claude/, .codex/, .agents/, pointer blocks (stdlib)
├── orchestrator.py               headless runner: classify / run / run-gate / status / prompt
├── lib/                          roles, adapters, profile, diffscope, routing, checks, pipeline, runner, state
├── tests/                        unittest suite
│
├── docs/                         workflow, roles, profile, routing, adapters (users)
│                                 architecture, critical-rules, definition-of-done,
│                                 code-quality, repository-layout, when-to-load, maintaining (maintainers)
│
└── runs/                         artifacts per task (created on first use)
```

Generated in the **host project root** by `install.py` (build output — edit the sources instead):

```
.claude/agents/<role>.md   .claude/skills/<skill>/SKILL.md   CLAUDE.md  (pointer block)
.codex/agents/<role>.toml  .agents/skills/<skill>/SKILL.md   AGENTS.md  (pointer block)
                                                              GEMINI.md  (pointer block)
```

## What a project receives (`install.py --dir`)

```
<project>/.omni-team/                 slim copy — RUNTIME_SET in lib/vendor.py
├── AGENTS.md  CLAUDE.md  GEMINI.md   agent entry points
├── VERSION  requirements.txt  .gitignore  .vendor.json (manifest: version, source, files)
├── defaults.yaml  orchestrator.py
├── lib/                              orchestrator modules only (no adapters.py / vendor.py)
├── team/                             roles + protocol (orchestrator prompts, fallback invocation)
├── docs/                             workflow, roles, profile, routing, adapters
├── skills/                           only for tools without native skills (gemini, agents-md)
├── project/                          the project's profile.yaml + conventions.md (never overwritten)
└── runs/                             artifacts (never overwritten)
```

Not shipped: `install.py`, `lib/adapters.py`, `lib/vendor.py`, `tests/`, `examples/`, `README.md`, maintainer docs. `--full` ships everything.

## What goes where

| Kind of knowledge | Location |
|---|---|
| What a role checks and how it reports | `team/<role>.md` |
| Behaviour shared by all roles | `team/_protocol.md` |
| How the main agent runs the team | `AGENTS.md`, `skills/` |
| Facts about one project | `project/profile.yaml` |
| Rules of one project | `project/conventions.md` |
| Which gates fire for which diff | `defaults.yaml` → `signals`, `routing` (override in profile) |
| How to call a tool headless | `defaults.yaml` → `orchestrator.engines` (override in profile) |
| Native tool formats | `lib/adapters.py` |

## Upgrading a vendored copy

`python3 <omni-team checkout>/.omni-team/install.py upgrade --dir <project>` replaces every framework file, removes stale ones, keeps `project/` and `runs/`, and regenerates the adapters. Because defaults live in `defaults.yaml` and projects only override, upgrades never require merging your profile.
