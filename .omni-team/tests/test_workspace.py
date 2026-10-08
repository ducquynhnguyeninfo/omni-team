"""Workspaces whose components are nested git repositories (product repos inside a private workspace)."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

FRAMEWORK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FRAMEWORK))

from lib import diffscope  # noqa: E402

try:
    import yaml  # type: ignore  # noqa: F401
except ImportError:  # pragma: no cover
    yaml = None

GIT_ID = ["-c", "user.email=t@t", "-c", "user.name=t"]
COMPS = [
    {"name": "backend", "path": "backend", "kind": "backend"},
    {"name": "frontend", "path": "frontend", "kind": "frontend", "base_ref": "develop"},
]


def git(cwd, *args):
    return subprocess.run(["git", *GIT_ID, *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@unittest.skipIf(shutil.which("git") is None, "git not installed")
class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name).resolve()
        # product repo 1: main only
        self.be = self.ws / "backend"
        self.be.mkdir()
        git(self.be, "init", "-q", "-b", "main")
        write(self.be / "app.py", "x = 1\n")
        git(self.be, "add", "-A"); git(self.be, "commit", "-qm", "be")
        # product repo 2: main → develop → feature branch
        self.fe = self.ws / "frontend"
        self.fe.mkdir()
        git(self.fe, "init", "-q", "-b", "main")
        write(self.fe / "a.ts", "export const a = 1;\n")
        git(self.fe, "add", "-A"); git(self.fe, "commit", "-qm", "main")
        git(self.fe, "checkout", "-q", "-b", "develop")
        write(self.fe / "b.ts", "export const b = 2;\n")
        git(self.fe, "add", "-A"); git(self.fe, "commit", "-qm", "develop work")
        git(self.fe, "checkout", "-q", "-b", "feature")

    def tearDown(self):
        self.tmp.cleanup()

    def init_workspace(self):
        git(self.ws, "init", "-q", "-b", "main")
        write(self.ws / ".gitignore", "backend/\nfrontend/\n")
        write(self.ws / "AGENTS.md", "# ws\n")
        git(self.ws, "add", "-A"); git(self.ws, "commit", "-qm", "ws")

    def test_scope_spans_workspace_and_nested_repos(self):
        self.init_workspace()
        write(self.ws / "docs/spec.md", "spec\n")
        write(self.be / "app.py", "x = 1\ny = 2\n")
        write(self.fe / "c.ts", "export const c = 3;\n")          # untracked in the nested repo
        info = diffscope.compute(self.ws, "auto", True, [".omni-team/**"], COMPS)
        self.assertEqual(sorted(info.scope.changed_paths), ["backend/app.py", "docs/spec.md", "frontend/c.ts"])
        self.assertEqual(info.scope.components, {"backend", "frontend"})
        self.assertEqual([r.key for r in info.repos], [".", "backend", "frontend"])
        self.assertIn("backend:", info.tree)
        self.assertEqual(git(self.be, "status", "--porcelain"), " M app.py\n", "real index untouched")

    def test_component_base_ref_limits_scope_to_the_feature(self):
        self.init_workspace()
        write(self.fe / "c.ts", "export const c = 3;\n")
        scoped = diffscope.compute(self.ws, "auto", True, [], COMPS)
        self.assertNotIn("frontend/b.ts", scoped.scope.changed_paths, "develop's own work is not in scope")
        auto = [dict(c, base_ref=None) if c["name"] == "frontend" else c for c in COMPS]
        wide = diffscope.compute(self.ws, "auto", True, [], auto)
        self.assertIn("frontend/b.ts", wide.scope.changed_paths, "without base_ref the base falls back to main")

    def test_delta_is_per_repository(self):
        self.init_workspace()
        before = diffscope.compute(self.ws, "auto", True, [], COMPS).tree
        write(self.be / "app.py", "x = 1\nz = 3\n")
        after = diffscope.compute(self.ws, "auto", True, [], COMPS).tree
        d = diffscope.delta(self.ws, before, after, [], COMPS)
        self.assertEqual((d.changed_paths, d.added_lines, d.components), (["backend/app.py"], ["z = 3"], {"backend"}))
        self.assertIsNone(diffscope.delta(self.ws, "deadbeef", after, [], COMPS), "repo set changed → unknown")

    def test_workspace_without_git_still_reviews_nested_repos(self):
        write(self.be / "app.py", "x = 2\n")
        info = diffscope.compute(self.ws, "auto", True, [], COMPS)
        self.assertEqual(info.scope.changed_paths, ["backend/app.py"])
        with self.assertRaises(diffscope.GitError):
            diffscope.compute(self.ws, "auto", True, [], [])

    def test_gitlink_nested_repo_is_not_double_counted(self):
        git(self.ws, "init", "-q", "-b", "main")
        git(self.ws, "add", "backend")                              # records a gitlink
        git(self.ws, "commit", "-qm", "ws with gitlink")
        git(self.be, "commit", "--allow-empty", "-qm", "moves the gitlink pointer")
        write(self.be / "app.py", "x = 9\n")
        info = diffscope.compute(self.ws, "auto", True, [], COMPS)
        self.assertEqual(info.scope.changed_paths, ["backend/app.py"])
        undeclared = diffscope.compute(self.ws, "auto", True, [], [COMPS[0]])
        self.assertIn("frontend", undeclared.scope.changed_paths, "an undeclared nested repo is still reported")

    def test_single_repo_snapshot_stays_a_plain_tree(self):
        self.init_workspace()
        info = diffscope.compute(self.ws, "auto", True, [], [{"name": "ws", "path": "."}])
        self.assertNotIn(":", info.tree)
        self.assertEqual(diffscope.decode_snapshot(info.tree), {".": info.tree})

    @unittest.skipIf(yaml is None, "needs PyYAML")
    def test_orchestrator_classify_in_a_workspace(self):
        self.init_workspace()
        for name in ("lib", "team", "project"):
            shutil.copytree(FRAMEWORK / name, self.ws / ".omni-team" / name,
                            ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("defaults.yaml", "orchestrator.py"):
            shutil.copy(FRAMEWORK / name, self.ws / ".omni-team" / name)
        (self.ws / ".omni-team/project/profile.yaml").write_text(json.dumps({"version": 1, "components": COMPS}))
        write(self.be / "app.py", "".join(f"v{i} = {i}\n" for i in range(40)))
        done = subprocess.run([sys.executable, ".omni-team/orchestrator.py", "classify", "--task", "t"],
                              cwd=self.ws, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("git -C backend diff", done.stdout)
        self.assertIn("backend/app.py", done.stdout)
        self.assertIn("code-reviewer", done.stdout)


if __name__ == "__main__":
    unittest.main()
