# Workspace layout — use omni-team without putting it in delivered code

When the product repositories (backend, frontend, mobile, …) are handed over to a client or another team, AI tooling should not live in them: no `CLAUDE.md`, no `.claude/`, no agent reports, no `.gitignore` lines about AI. The answer is a **private workspace repository** that holds the tooling and the team's working documents, with each product repository cloned inside it as an independent git repository.

```
acme/                              ← WORKSPACE repo (private, team-internal, never delivered)
├── AGENTS.md                      instructions for every agent (single source)
├── CLAUDE.md                      "@AGENTS.md" + Claude Code specifics
├── .omni-team/                    slim omni-team (install.py --dir .)
│   ├── project/profile.yaml       components → backend/, frontend/ (nested repos)
│   ├── project/conventions.md     ALL project rules for the agents (per component)
│   └── runs/                      agent reports
├── .claude/ .codex/ .agents/      generated adapters + workspace-only commands, skills, hooks
├── .mcp.json                      MCP servers (${VAR} references only)
├── docs/                          specs, PM documents, ADRs, design notes (internal)
├── repos.txt                      product repos to clone (name, URL, default branch)
├── scripts/bootstrap.sh           clone repos, install omni-team, check tools
├── .gitignore                     backend/  frontend/  (the product repos)
├── backend/                       ← delivered repo: own .git, own remote, product code only
└── frontend/                      ← delivered repo
```

## Rules

1. **Delivered repositories contain the product only** — code, tests, CI, and tool-neutral engineering docs people use too (`README`, architecture, database, coding guide). No AI instruction files, adapters or agent reports.
2. **Agent rules live in the workspace.** `project/conventions.md` points into the product docs ("layer rules: see `backend/ARCHITECTURE.md`") instead of copying them; the root `AGENTS.md` carries the cross-repo rules.
3. **Start agents at the workspace root.** Claude Code loads `CLAUDE.md` and `.claude/` from the folder it is opened in; Codex looks for `AGENTS.md` from the git root of the folder it is started in — inside `backend/` (its own repo) it would not see the workspace instructions.
4. **Product repos are plain clones, ignored by the workspace.** Avoid half-submodules (gitlinks without `.gitmodules`) and symlink chains. To pin versions, record commits in `repos.txt`; real submodules work too, at the cost of pointer bumps.
5. **Commit per repository.** A change can span several repos; each is committed and pushed in its own history. The orchestrator's summary lists which repositories have changes.
6. **Hand over** the product repositories (plus a knowledge-base repo if the contract requires one). The workspace never leaves the team.

## Profile

Declare each product repo as a component. A component whose folder contains `.git` is treated as a nested repository automatically (`repo: true/false` forces it). Each may have its own base branch:

```yaml
components:
  - name: backend
    path: backend
    kind: backend
    base_ref: origin/develop        # feature branches start from develop in this repo
    commands: { lint: "ruff check .", test: "pytest -q" }
  - name: frontend
    path: frontend
    kind: frontend
    base_ref: origin/develop
    commands: { typecheck: "pnpm typecheck", lint: "pnpm lint", test: "pnpm test && pnpm build" }
```

What the orchestrator does with it:

- diffs and snapshots **each** repository on its own (merge-base with that repo's base → working tree, untracked files included) and prefixes its paths with the component path, so routing globs (`backend/app/**`), Gate 0 and component detection work unchanged;
- diffs the workspace repo itself (specs, conventions, scripts) with the nested repos excluded — gitlinks included;
- tells every gate where each part of the diff lives (`git -C backend diff <merge-base>`) and lists the repositories with changes in `_summary.md`;
- keeps approvals per repository: a fix in `frontend/` only re-opens gates the frontend delta routes.

Base resolution per repository: the component's `base_ref`, else `--base` / `orchestrator.base_ref`, else the first existing ref in `orchestrator.base_candidates`.

## Bootstrap script (example)

```bash
#!/usr/bin/env bash
# scripts/bootstrap.sh — clone the product repos and install omni-team into this workspace.
set -euo pipefail
cd "$(dirname "$0")/.."
while read -r name url branch; do
  [[ -z "$name" || "$name" == \#* ]] && continue
  [[ -d "$name/.git" ]] || git clone --branch "$branch" "$url" "$name"
done < repos.txt
python3 "${OMNI_TEAM:?set OMNI_TEAM to your omni-team checkout}/.omni-team/install.py" --dir .
```

```text
# repos.txt — name  url  default-branch
backend   git@github.com:acme/backend.git   develop
frontend  git@github.com:acme/frontend.git  develop
```

## Moving an existing setup

1. Create the workspace repo; move AI files out of the product repos into it (`CLAUDE.md` content → `project/conventions.md` sections and the root `AGENTS.md`).
2. In each product repo: `git rm` agent reports or AI files that were committed, and drop `.gitignore` lines that only existed to hide AI files.
3. Replace gitlinks and symlinked folders with plain clones listed in `repos.txt`; add them to the workspace `.gitignore`.
4. `python3 <omni-team>/.omni-team/install.py --dir <workspace>`, then `orchestrator.py classify --task check` and confirm every repository appears under "Repositories".
