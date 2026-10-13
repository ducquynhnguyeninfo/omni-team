# Upstream

Third-party skill vendored into omni-team with one change.

- **Changed**: the `description` in the `SKILL.md` frontmatter, which decides when an agent picks the skill. Upstream it covers any new or reshaped UI; here it is narrowed to marketing-facing pages (landing, product, campaign, brand, portfolio, event) and points screens inside a web app to a web-app UI skill. The skill's rules aim at a distinctive identity per page, which suits a landing page and works against the consistency an app's screens need. The body is unmodified.

- Source: https://github.com/anthropics/skills (folder `skills/frontend-design/`)
- Commit: `dbd4588f9e1033efb41dad4bef2f7947c8993d44`
- License: Apache-2.0 — see [LICENSE.txt](LICENSE.txt)
- Requirements: none; screenshot self-critique works when a browser tool (e.g. a Playwright or Chrome DevTools MCP) is configured

To update: export the same folder from a newer upstream commit, keep `LICENSE.txt` and this file, re-apply the `description` change and its notice comment, update the commit above.
