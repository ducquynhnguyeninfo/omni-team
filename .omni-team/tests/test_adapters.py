import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import install  # noqa: E402
from lib import adapters  # noqa: E402
from lib.roles import RoleError, load_protocol, load_roles, load_skills, split_frontmatter  # noqa: E402

try:
    import tomllib  # type: ignore  # Python 3.11+
except ImportError:  # pragma: no cover
    tomllib = None
try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None


class CanonicalSourcesTest(unittest.TestCase):
    def test_roles_and_skills_are_valid(self):
        roles = load_roles()
        self.assertGreaterEqual(len(roles), 9)
        for role in roles:
            self.assertIn("VERDICT:", role.body, f"{role.name} must document its verdict line")
        self.assertEqual({s.name for s in load_skills()},
                         {"omni-setup", "omni-task", "omni-plan", "omni-review", "omni-ship", "pm"})

    def test_frontmatter_errors_are_loud(self):
        with self.assertRaises(RoleError):
            split_frontmatter("no frontmatter", Path("x.md"))
        with self.assertRaises(RoleError):
            split_frontmatter("---\nname: x\n", Path("x.md"))


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.protocol = load_protocol()
        self.roles = load_roles()

    @unittest.skipIf(tomllib is None, "tomllib needs Python 3.11+")
    def test_codex_toml_parses(self):
        for role in self.roles:
            text = adapters.render_codex_agent(role, self.protocol, adapters.DEFAULT_CODEX_EFFORT)
            data = tomllib.loads(text)
            self.assertEqual(data["name"], role.name)
            self.assertIn("VERDICT:", data["developer_instructions"])
            self.assertIn(data["sandbox_mode"], ("read-only", "workspace-write"))

    def test_toml_escaping(self):
        if tomllib is None:
            self.skipTest("tomllib needs Python 3.11+")
        tricky = 'a """ b \\ c\n"end"'
        self.assertEqual(tomllib.loads(f"x = {adapters.toml_multiline(tricky)}")["x"], tricky + "\n")

    @unittest.skipIf(yaml is None, "PyYAML not installed")
    def test_claude_frontmatter_parses(self):
        for role in self.roles:
            text = adapters.render_claude_agent(role, self.protocol, adapters.DEFAULT_CLAUDE_MODELS)
            meta = yaml.safe_load(text.split("---")[1])
            self.assertEqual(meta["name"], role.name)
            self.assertEqual(meta["description"], role.description)
            self.assertEqual("tools" in meta, role.access == "read-only")


class PointerBlockTest(unittest.TestCase):
    def test_upsert_is_idempotent_and_preserves_content(self):
        block = adapters.pointer_block()
        once = adapters.upsert_block("# Mine\n\nkeep me\n", block)
        twice = adapters.upsert_block(once, block)
        self.assertEqual(once, twice)
        self.assertIn("keep me", twice)
        self.assertEqual(adapters.remove_block(twice), "# Mine\n\nkeep me\n")

    def test_remove_from_block_only_file(self):
        self.assertEqual(adapters.remove_block(adapters.pointer_block()), "")


class InstallTest(unittest.TestCase):
    def run_install(self, root, *extra):
        with redirect_stdout(io.StringIO()):
            return install.main(["--project-root", str(root), "--tools", "all", *extra])

    def test_install_reinstall_uninstall(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text("# Host rules\n", encoding="utf-8")
            self.assertEqual(self.run_install(root), 0)
            self.assertTrue((root / ".claude/agents/code-reviewer.md").exists())
            self.assertTrue((root / ".codex/agents/code-reviewer.toml").exists())
            self.assertTrue((root / ".agents/skills/omni-task/SKILL.md").exists())
            self.assertTrue((root / ".claude/skills/omni-task/SKILL.md").exists())
            self.assertIn("omni-team:begin", (root / "AGENTS.md").read_text(encoding="utf-8"))
            stale = root / ".claude/agents/old-role.md"
            stale.write_text(f"<!-- {adapters.MARKER} -->", encoding="utf-8")
            self.assertEqual(self.run_install(root), 0)
            self.assertFalse(stale.exists(), "stale generated files are cleaned up")
            self.assertEqual(self.run_install(root, "--uninstall"), 0)
            self.assertFalse((root / ".claude/agents/code-reviewer.md").exists())
            self.assertEqual((root / "AGENTS.md").read_text(encoding="utf-8"), "# Host rules\n")
            self.assertFalse((root / "CLAUDE.md").exists())

    def test_refuses_to_overwrite_foreign_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mine = root / ".claude/agents/code-reviewer.md"
            mine.parent.mkdir(parents=True)
            mine.write_text("hand written", encoding="utf-8")
            with redirect_stdout(io.StringIO()), redirect_stderr_null():
                self.assertEqual(install.main(["--project-root", str(root), "--tools", "claude"]), 2)
            self.assertEqual(mine.read_text(encoding="utf-8"), "hand written")


def redirect_stderr_null():
    from contextlib import redirect_stderr
    return redirect_stderr(io.StringIO())


if __name__ == "__main__":
    unittest.main()
