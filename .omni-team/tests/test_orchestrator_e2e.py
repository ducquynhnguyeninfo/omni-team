"""End-to-end: the real orchestrator in a throwaway git repo, with a fake engine CLI."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

FRAMEWORK = Path(__file__).resolve().parent.parent

try:
    import yaml  # type: ignore  # noqa: F401
except ImportError:  # pragma: no cover
    yaml = None

FAKE_ENGINE = r'''
import pathlib, re, sys
prompt = sys.stdin.read()
role = re.search(r"omni-team role `([^`]+)`", prompt).group(1)
table = dict(line.split("=", 1) for line in pathlib.Path(".omni-team/fake_verdicts.txt").read_text().split())
print("fake report for " + role)
print("VERDICT: " + table.get(role, "APPROVE") + " — fake")
'''


@unittest.skipIf(yaml is None or shutil.which("git") is None, "needs PyYAML and git")
class OrchestratorE2ETest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        fw = self.root / ".omni-team"
        for name in ("lib", "team", "skills", "project"):
            shutil.copytree(FRAMEWORK / name, fw / name, ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("defaults.yaml", "orchestrator.py"):
            shutil.copy(FRAMEWORK / name, fw / name)
        (fw / "fake_engine.py").write_text(FAKE_ENGINE)
        self.write_profile(checks=[f'"{sys.executable}" -c "pass"'])
        self.git("init", "-q", "-b", "main")
        (self.root / "README.md").write_text("x\n")
        self.git("add", "README.md")
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)

    def write_profile(self, checks):
        profile = {
            "version": 1,
            "checks": checks,
            "orchestrator": {
                "engine": "fake", "max_parallel": 3,
                "engines": {"fake": {"cmd": [sys.executable, ".omni-team/fake_engine.py"], "tiers": {}}},
            },
        }
        (self.root / ".omni-team/project/profile.yaml").write_text(json.dumps(profile))

    def verdicts(self, **table):
        lines = [f"{k.replace('_', '-')}={v}" for k, v in table.items()]
        (self.root / ".omni-team/fake_verdicts.txt").write_text("\n".join(lines))

    def run_cmd(self, *args):
        done = subprocess.run([sys.executable, ".omni-team/orchestrator.py", *args, "--task", "T1"],
                              cwd=self.root, capture_output=True, text=True)
        return done.returncode, done.stdout + done.stderr

    def state(self):
        raw = json.loads((self.root / ".omni-team/runs/T1/_state.json").read_text())
        return {g["name"]: g for g in raw["gates"]}

    def write(self, rel, lines):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(f"{line}\n" for line in lines))

    def test_checks_parallel_stage_reopen_cycle(self):
        self.write("src/app.py", [f"v{i} = {i}" for i in range(30)])
        self.write("db/migrations/001.sql", ["CREATE TABLE t (id int);"])
        self.verdicts(data_reviewer="APPROVE", code_reviewer="REQUEST_CHANGES", test_engineer="APPROVE")

        code, out = self.run_cmd("run")
        self.assertEqual(code, 1, out)
        self.assertIn("data-reviewer ‖ code-reviewer ‖ test-engineer", out)
        st = self.state()
        self.assertEqual({n: g["status"] for n, g in st.items()},
                         {"data-reviewer": "passed", "code-reviewer": "request_changes", "test-engineer": "passed"})

        # Fix touching only application code: code-reviewer re-runs, data-reviewer keeps its approval.
        self.write("src/app.py", [f"v{i} = {i}" for i in range(50)])
        self.verdicts(code_reviewer="APPROVE")
        code, out = self.run_cmd("run")
        self.assertEqual(code, 0, out)
        st = self.state()
        self.assertEqual((st["code-reviewer"]["attempts"], st["data-reviewer"]["attempts"]), (2, 1))

        # A later migration change re-opens data-reviewer (and test-engineer, via schema routing).
        self.write("db/migrations/001.sql", ["CREATE TABLE t (id int);", "ALTER TABLE t ADD c int;"])
        code, out = self.run_cmd("run")
        self.assertEqual(code, 0, out)
        self.assertIn("data-reviewer re-opened", out)
        st = self.state()
        self.assertEqual(st["data-reviewer"]["attempts"], 2)
        self.assertEqual(st["code-reviewer"]["attempts"], 2)

    def test_record_persists_external_reports_with_state(self):
        self.write("src/app.py", [f"v{i} = {i}" for i in range(30)])
        report = "## Code review\n- F1 [src/app.py:3] (CR-1) bug\n  Fix: fix it\n\nVERDICT: REQUEST_CHANGES — one bug"
        done = subprocess.run([sys.executable, ".omni-team/orchestrator.py", "record", "code-reviewer", "--task", "T1"],
                              cwd=self.root, input=report, capture_output=True, text=True)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)            # paused: changes requested
        self.assertIn("REQUEST_CHANGES", done.stdout)
        gate = self.state()["code-reviewer"]
        self.assertEqual((gate["status"], gate["attempts"]), ("request_changes", 1))
        self.assertIn("F1 [src/app.py:3]", (self.root / ".omni-team/runs/T1/code-reviewer.md").read_text())
        empty = subprocess.run([sys.executable, ".omni-team/orchestrator.py", "record", "code-reviewer", "--task", "T1"],
                               cwd=self.root, input="", capture_output=True, text=True)
        self.assertEqual(empty.returncode, 2)

    def test_failing_checks_stop_before_any_ai_gate(self):
        self.write("src/app.py", [f"v{i} = {i}" for i in range(30)])
        self.write_profile(checks=[f'"{sys.executable}" -c "import sys; sys.exit(3)"'])
        self.verdicts()
        code, out = self.run_cmd("run")
        self.assertEqual(code, 7, out)
        self.assertTrue(all(g["attempts"] == 0 for g in self.state().values()))
        self.assertIn("❌", (self.root / ".omni-team/runs/T1/_checks.md").read_text())

        self.write_profile(checks=[f'"{sys.executable}" -c "pass"'])
        code, out = self.run_cmd("run")
        self.assertEqual(code, 0, out)
        code, out = self.run_cmd("run")
        self.assertIn("already green for this snapshot", out)


if __name__ == "__main__":
    unittest.main()
