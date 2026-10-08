import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import checks, diffscope  # noqa: E402

HAS_GIT = shutil.which("git") is not None


class ResolveChecksTest(unittest.TestCase):
    COMPS = [
        {"name": "api", "path": "api", "commands": {"lint": "ruff .", "test": "pytest", "run": "serve"}},
        {"name": "web", "path": "web", "commands": {"typecheck": "tsc"}},
    ]

    def test_explicit_list_runs_at_root(self):
        got = checks.resolve({"checks": ["make lint", "make test"]}, set())
        self.assertEqual([(c.command, c.cwd) for c in got], [("make lint", "."), ("make test", ".")])

    def test_auto_uses_touched_components_only(self):
        got = checks.resolve({"checks": "auto", "components": self.COMPS}, {"api", "backend"})
        self.assertEqual([c.name for c in got], ["api:lint", "api:test"])

    def test_auto_without_touched_component_runs_all(self):
        got = checks.resolve({"components": self.COMPS}, set())
        self.assertEqual([c.name for c in got], ["api:lint", "api:test", "web:typecheck"])

    def test_disabled_and_invalid(self):
        self.assertEqual(checks.resolve({"checks": "none"}, set()), [])
        self.assertEqual(checks.resolve({"checks": "auto"}, set()), [])
        with self.assertRaises(checks.ChecksError):
            checks.resolve({"checks": 42}, set())

    def test_run_all_and_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ok = checks.Check("ok", f'"{sys.executable}" -c "print(1)"', ".")
            bad = checks.Check("bad", f'"{sys.executable}" -c "import sys; print(\'boom\'); sys.exit(2)"', ".")
            results = checks.run_all([ok, bad], root, timeout_s=30)
            self.assertEqual([r.ok for r in results], [True, False])
            log = root / "_checks.md"
            checks.write_log(log, results, "abcdef123456789")
            text = log.read_text(encoding="utf-8")
            self.assertIn("❌ `bad`", text)
            self.assertIn("boom", text)


@unittest.skipUnless(HAS_GIT, "git not installed")
class SnapshotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.git("init", "-q", "-b", "main")
        (self.root / "a.py").write_text("x = 1\n")
        self.git("add", ".")
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True, check=True).stdout

    def test_snapshot_includes_untracked_and_leaves_index_alone(self):
        (self.root / "new.py").write_text("y = 2\n")
        (self.root / ".omni-team").mkdir()
        (self.root / ".omni-team" / "report.md").write_text("r\n")
        before = self.git("status", "--porcelain")
        info = diffscope.compute(self.root, "main", True, [".omni-team/**"], [])
        self.assertEqual(self.git("status", "--porcelain"), before)
        self.assertEqual(info.scope.changed_paths, ["new.py"])
        self.assertEqual(info.scope.added_lines, ["y = 2"])

    def test_same_size_edit_right_after_commit_is_seen(self):
        # Regression: the snapshot copies the index. A copy with a fresh mtime defeats git's
        # racy-clean check, so a same-size edit made in the same second as the last index write,
        # snapshotted a second later, looked unchanged. copy2 keeps the index mtime.
        import time
        (self.root / "a.py").write_text("x = 1\n")
        self.git("add", "a.py")
        (self.root / "a.py").write_text("y = 2\n")                 # same size, same second as the add
        time.sleep(1.2)                                             # snapshot happens a second later
        info = diffscope.compute(self.root, "HEAD", True, [], [])
        self.assertEqual(info.scope.changed_paths, ["a.py"])
        self.assertEqual(info.scope.added_lines, ["y = 2"])

    def test_snapshot_ignores_excluded_changes_and_delta_is_exact(self):
        excludes = [".omni-team/**"]
        t1 = diffscope.snapshot_tree(self.root, excludes)
        (self.root / ".omni-team").mkdir()
        (self.root / ".omni-team" / "report.md").write_text("r\n")
        self.assertEqual(diffscope.snapshot_tree(self.root, excludes), t1)
        (self.root / "a.py").write_text("x = 1\nz = 3\n")
        t2 = diffscope.snapshot_tree(self.root, excludes)
        delta = diffscope.delta(self.root, t1, t2, excludes, [])
        self.assertEqual((delta.changed_paths, delta.added_lines), (["a.py"], ["z = 3"]))
        self.assertIsNone(diffscope.delta(self.root, "0" * 40, t2, excludes, []))


if __name__ == "__main__":
    unittest.main()
