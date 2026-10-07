import io
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

FRAMEWORK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FRAMEWORK))

import install  # noqa: E402
from lib import vendor  # noqa: E402


def quiet(fn, *args):
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        return fn(*args)


class VendorPlanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = (Path(self.tmp.name) / "chatbot").resolve()
        self.project.mkdir()
        self.target = self.project / ".omni-team"

    def tearDown(self):
        self.tmp.cleanup()

    def test_fresh_copies_framework_and_project_template_but_no_runs_or_caches(self):
        vplan = vendor.plan(FRAMEWORK, self.project)
        self.assertEqual(vplan.mode, "fresh")
        vendor.apply(vplan)
        for rel in ("install.py", "orchestrator.py", "team/_protocol.md", "project/profile.yaml", "VERSION"):
            self.assertTrue((self.target / rel).exists(), rel)
        self.assertFalse((self.target / "runs").exists())
        self.assertEqual(list(self.target.rglob("__pycache__")), [])
        self.assertEqual(vendor.plan(FRAMEWORK, self.project).changes, 0, "second plan is a no-op")

    def test_upgrade_preserves_host_files_and_removes_stale_framework_files(self):
        vendor.apply(vendor.plan(FRAMEWORK, self.project))
        (self.target / "project" / "profile.yaml").write_text("version: 1\nproject: {name: Chatbot}\n")
        (self.target / "runs" / "T1").mkdir(parents=True)
        (self.target / "runs" / "T1" / "code-reviewer.md").write_text("report")
        (self.target / "team" / "old-role.md").write_text("stale")
        (self.target / "defaults.yaml").write_text("tampered: true\n")

        vplan = vendor.plan(FRAMEWORK, self.project)
        self.assertEqual(vplan.mode, "upgrade")
        self.assertIn(self.target / "team" / "old-role.md", vplan.removed)
        self.assertIn(self.target / "defaults.yaml", [dst for _, dst in vplan.updated])
        vendor.apply(vplan)
        self.assertIn("Chatbot", (self.target / "project" / "profile.yaml").read_text())
        self.assertEqual((self.target / "runs" / "T1" / "code-reviewer.md").read_text(), "report")
        self.assertFalse((self.target / "team" / "old-role.md").exists())
        self.assertEqual((self.target / "defaults.yaml").read_bytes(), (FRAMEWORK / "defaults.yaml").read_bytes())

    def test_refuses_foreign_folder_downgrade_and_nested_target(self):
        self.target.mkdir()
        (self.target / "notes.txt").write_text("not ours")
        with self.assertRaises(vendor.VendorError):
            vendor.plan(FRAMEWORK, self.project)
        shutil.rmtree(self.target)
        vendor.apply(vendor.plan(FRAMEWORK, self.project))
        (self.target / "VERSION").write_text("999.0.0\n")
        with self.assertRaises(vendor.VendorError):
            vendor.plan(FRAMEWORK, self.project)
        self.assertEqual(vendor.plan(FRAMEWORK, self.project, force=True).mode, "upgrade")
        with self.assertRaises(vendor.VendorError):
            vendor.plan(FRAMEWORK, FRAMEWORK / "examples")
        with self.assertRaises(vendor.VendorError):
            vendor.plan(FRAMEWORK, Path(self.tmp.name) / "missing")

    def test_same_folder_is_a_no_op(self):
        self.assertEqual(vendor.plan(FRAMEWORK, FRAMEWORK.parent).mode, "same")


class InstallDirTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = (Path(self.tmp.name) / "chatbot").resolve()
        self.project.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_install_dir_vendors_and_registers(self):
        self.assertEqual(quiet(install.main, ["--dir", str(self.project)]), 0)
        self.assertTrue((self.project / ".omni-team" / "install.py").exists())
        self.assertTrue((self.project / ".claude" / "agents" / "code-reviewer.md").exists())
        self.assertTrue((self.project / ".codex" / "agents" / "ba.toml").exists())
        self.assertIn("omni-team:begin", (self.project / "AGENTS.md").read_text())
        self.assertEqual(quiet(install.main, ["upgrade", "--dir", str(self.project)]), 0)

    def test_dry_run_writes_nothing(self):
        self.assertEqual(quiet(install.main, ["init", "--dir", str(self.project), "--dry-run"]), 0)
        self.assertEqual(list(self.project.iterdir()), [])

    def test_conflict_aborts_before_copying_anything(self):
        mine = self.project / ".claude" / "agents" / "pm.md"
        mine.parent.mkdir(parents=True)
        mine.write_text("hand written")
        self.assertEqual(quiet(install.main, ["--dir", str(self.project)]), 2)
        self.assertFalse((self.project / ".omni-team").exists())
        self.assertEqual(mine.read_text(), "hand written")

    def test_upgrade_requires_existing_copy_and_flags_are_exclusive(self):
        self.assertEqual(quiet(install.main, ["upgrade", "--dir", str(self.project)]), 2)
        self.assertEqual(quiet(install.main, ["--dir", str(self.project), "--project-root", str(self.project)]), 2)

    def test_uninstall_dir_keeps_vendored_folder(self):
        quiet(install.main, ["--dir", str(self.project)])
        self.assertEqual(quiet(install.main, ["uninstall", "--dir", str(self.project)]), 0)
        self.assertFalse((self.project / ".claude" / "agents" / "code-reviewer.md").exists())
        self.assertTrue((self.project / ".omni-team" / "install.py").exists())


if __name__ == "__main__":
    unittest.main()
