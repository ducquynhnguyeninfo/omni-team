import json
import unittest
from pathlib import Path

FRAMEWORK = Path(__file__).resolve().parent.parent
PLUGIN = FRAMEWORK.parent / ".claude-plugin"     # only in the omni-team repository, not in vendored copies


@unittest.skipUnless(PLUGIN.is_dir(), "not the omni-team repository")
class PluginManifestTest(unittest.TestCase):
    def load(self, name):
        return json.loads((PLUGIN / name).read_text(encoding="utf-8"))

    def test_plugin_version_follows_framework_version(self):
        version = (FRAMEWORK / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(self.load("plugin.json")["version"], version,
                         "bump .claude-plugin/plugin.json together with .omni-team/VERSION")

    def test_marketplace_lists_the_plugin_at_the_repository_root(self):
        market, plugin = self.load("marketplace.json"), self.load("plugin.json")
        entries = {p["name"]: p for p in market["plugins"]}
        self.assertEqual(entries[plugin["name"]]["source"], "./")
        self.assertNotIn("version", entries[plugin["name"]], "plugin.json carries the version")

    def test_plugin_skills_exist_and_reach_the_installer(self):
        for skill in ("install", "upgrade"):
            text = (FRAMEWORK.parent / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn(f"name: {skill}", text)
            self.assertIn("${CLAUDE_PLUGIN_ROOT}", text)
            self.assertIn("/.omni-team/install.py", text)
        self.assertTrue((FRAMEWORK / "install.py").is_file())


if __name__ == "__main__":
    unittest.main()
