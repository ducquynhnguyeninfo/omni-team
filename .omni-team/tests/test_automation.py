import importlib.util
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

FRAMEWORK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FRAMEWORK))

from lib import automation, profile  # noqa: E402

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None


class PolicyTest(unittest.TestCase):
    def test_default_is_off(self):
        self.assertEqual(automation.policy({}).pr_fix, "off")

    def test_levels_and_yaml_boolean_off(self):
        self.assertEqual(automation.policy({"automation": {"pr_fix": "push"}}).pr_fix, "push")
        self.assertEqual(automation.policy({"automation": {"pr_fix": False}}).pr_fix, "off")

    def test_invalid_values_fail_clearly(self):
        for bad in ({"pr_fix": "always"}, {"pr_fix": True}, {"push": "yes"}, {"protected_branches": "main"},
                    {"branch_prefix": ""}, {"branch_prefix": 3}, {"branch_prefix": "a b/"}, {"branch_prefix": "-x/"},
                    {"branch_prefix": "a..b/"}, {"branch_prefix": "fix:"}):
            with self.assertRaises(automation.AutomationError, msg=bad):
                automation.policy({"automation": bad})
        with self.assertRaises(automation.AutomationError):
            automation.policy({"automation": "push"})

    def test_branch_prefix_names_the_work_branch(self):
        self.assertEqual(automation.policy({}).work_branch("T-1"), "omni/T-1")
        self.assertEqual(automation.policy({"automation": {"branch_prefix": "bot/fix-"}}).work_branch("42"),
                         "bot/fix-42")

    def test_allows_is_cumulative(self):
        self.assertTrue(automation.Policy("push").allows("commit"))
        self.assertFalse(automation.Policy("commit").allows("push"))
        self.assertFalse(automation.Policy("off").allows("commit"))

    def test_profile_merges_automation_key_by_key(self):
        merged = profile.merge({"automation": {"pr_fix": "off", "protected_branches": ["main"]}},
                               {"automation": {"pr_fix": "commit"}})
        self.assertEqual(merged["automation"], {"pr_fix": "commit", "protected_branches": ["main"]})
        with self.assertRaises(profile.ProfileError):
            profile.merge({}, {"automation": "push"})

    @unittest.skipIf(yaml is None, "PyYAML not installed")
    def test_shipped_defaults_are_off(self):
        tree = profile.load(FRAMEWORK / "project" / "missing.yaml")
        self.assertEqual(automation.policy(tree).pr_fix, "off")
        self.assertIn("main", automation.policy(tree).protected_branches)


class ProblemsTest(unittest.TestCase):
    OK = {"workspace": ("feat/x", "main", "feat/x")}

    def problems(self, level="push", action="push", branches=None, green=True, phase="review", gates=None):
        return automation.problems(automation.Policy(level, ["release/*"]), action, branches or self.OK,
                                   green, phase, gates or {"code-reviewer": "passed"})

    def test_all_clear(self):
        self.assertEqual(self.problems(), [])
        self.assertEqual(self.problems(level="commit", action="commit", gates={"code-reviewer": "request_changes"}), [])

    def test_each_boundary(self):
        cases = {
            "pr_fix is 'commit'": dict(level="commit"),
            "default branch": dict(branches={"workspace": ("main", "main", "main")}),
            "detached": dict(branches={"workspace": ("", "main", "")}),
            "protected branch pattern": dict(branches={"workspace": ("release/1.2", "main", "release/1.2")}),
            "Gate 0": dict(green=False),
            "halted": dict(phase="halted"),
            "code-reviewer is request_changes": dict(gates={"code-reviewer": "request_changes"}),
            "code-reviewer is pending": dict(gates={"code-reviewer": "pending"}),
            "test-engineer is not run": dict(gates={"code-reviewer": "passed", "test-engineer": "not run"}),
            "pushes to 'main'": dict(branches={"workspace": ("feat/x", "main", "main")}),
            "pushes to 'release/9'": dict(branches={"workspace": ("feat/x", "main", "release/9")}),
        }
        for needle, kwargs in cases.items():
            found = self.problems(**kwargs)
            self.assertTrue(any(needle in p for p in found), f"{needle}: {found}")

    def test_push_target_only_matters_for_a_push(self):
        self.assertEqual(self.problems(level="commit", action="commit",
                                       branches={"workspace": ("feat/x", "main", "main")}), [])

    def test_main_and_master_are_always_protected(self):
        for branch in ("main", "master"):
            found = automation.problems(automation.Policy("push", ["develop"]), "push",
                                        {"workspace": (branch, "trunk", branch)}, True, "review", {})
            self.assertTrue(any("always protected" in p for p in found), found)

    def test_master_is_protected_when_origin_head_is_unknown(self):
        self.assertTrue(self.problems(branches={"workspace": ("master", "", "master")}))

    def test_unknown_action(self):
        with self.assertRaises(automation.AutomationError):
            self.problems(action="merge")


class RemedyTest(unittest.TestCase):
    POL = automation.Policy("push", ["release/*"], "omni/")

    def verdict(self, action, branches):
        return automation.verdict(self.POL, action, "T1", branches, True, "review", {"code-reviewer": "passed"},
                                  "runs/T1/_summary.md")

    def test_default_or_protected_branch_gets_a_work_branch_and_a_pull_request(self):
        for branch in ("main", "release/2.0"):
            ok, out = self.verdict("push", {"workspace": (branch, "main", branch)})
            self.assertFalse(ok)
            self.assertIn("`git switch -c omni/T1`", out)
            self.assertIn("push -u origin HEAD", out)
            self.assertIn("pull request into 'main'", out)
        ok, out = self.verdict("commit", {"api": automation.RepoBranch("main", "main", "", None, "-C api ")})
        self.assertIn("`git -C api switch -c omni/T1`", out)
        self.assertNotIn("push -u", out)

    def test_local_commits_on_the_protected_branch_are_moved_not_reset_unasked(self):
        _, out = self.verdict("push", {"workspace": automation.RepoBranch("main", "main", "main", 2)})
        self.assertIn("2 local commit(s) on 'main'", out)
        self.assertIn("only on the user's yes", out)

    def test_protected_push_target_unsets_the_upstream(self):
        ok, out = self.verdict("push", {"workspace": ("feat/x", "main", "main")})
        self.assertFalse(ok)
        self.assertIn("`git branch --unset-upstream`", out)
        self.assertNotIn("switch -c", out)

    def test_no_remedy_for_other_problems_and_pr_steps_when_allowed(self):
        ok, out = automation.verdict(self.POL, "push", "T1", {"workspace": ("feat/x", "main", "feat/x")}, False,
                                     "review", {}, "s.md")
        self.assertFalse(ok)
        self.assertNotIn("→", out)
        ok, out = self.verdict("push", {"workspace": ("omni/T1", "main", "omni/T1")})
        self.assertTrue(ok)
        self.assertIn("gh pr create --base main --head omni/T1", out)
        self.assertIn("--body-file runs/T1/_summary.md", out)
        self.assertIn("no --admin", out)
        ok, out = self.verdict("commit", {"workspace": ("omni/T1", "main", "")})
        self.assertTrue(ok)
        self.assertNotIn("gh pr", out)


@unittest.skipIf(yaml is None or shutil.which("git") is None, "needs PyYAML and git")
class AutomationCommandTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        fw = self.root / ".omni-team"
        for name in ("lib", "team", "project"):
            shutil.copytree(FRAMEWORK / name, fw / name, ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("defaults.yaml", "orchestrator.py"):
            shutil.copy(FRAMEWORK / name, fw / name)
        self.git("init", "-q", "-b", "main")
        (self.root / "README.md").write_text("x\n")
        self.git("add", "README.md")
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)

    def profile(self, level):
        data = {"version": 1, "checks": [f'"{sys.executable}" -c "pass"'], "automation": {"pr_fix": level}}
        (self.root / ".omni-team/project/profile.yaml").write_text(json.dumps(data))

    def run_cmd(self, *args, stdin=None):
        done = subprocess.run([sys.executable, ".omni-team/orchestrator.py", *args, "--task", "T1"],
                              cwd=self.root, capture_output=True, text=True, input=stdin)
        return done.returncode, done.stdout + done.stderr

    def test_push_from_main_goes_through_a_work_branch_and_a_pull_request(self):
        self.profile("push")
        (self.root / "app.py").write_text("".join(f"print({i})\n" for i in range(30)))   # beyond trivial: routed
        code, out = self.run_cmd("automation", "--action", "push")
        self.assertEqual(code, 6, out)
        self.assertIn("default branch", out)
        self.assertIn("Gate 0", out)
        self.assertIn("`git switch -c omni/T1`", out)
        self.git("switch", "-q", "-c", "omni/T1")                 # the remedy: uncommitted work comes along
        self.assertTrue((self.root / "app.py").exists())
        self.assertEqual(self.run_cmd("checks")[0], 0)
        self.assertEqual(self.run_cmd("automation", "--action", "commit")[0], 0)
        code, out = self.run_cmd("automation", "--action", "push")        # no gate has run yet
        self.assertEqual(code, 6, out)
        unreviewed = re.findall(r"gate (\S+) is not run", out)
        self.assertTrue(unreviewed, out)
        for role in unreviewed:
            self.run_cmd("record", role, stdin="Looks fine.\nVERDICT: APPROVE\n")
        code, out = self.run_cmd("automation", "--action", "push")
        self.assertEqual(code, 0, out)
        self.assertIn("Task: T1", out)
        self.assertIn("gh pr create", out)
        self.assertIn("--head omni/T1", out)
        (self.root / "app.py").write_text("print(2)\n")          # changed after Gate 0 went green
        self.assertEqual(self.run_cmd("automation", "--action", "commit")[0], 6)

    def test_off_refuses_and_classify_reports_the_level(self):
        self.profile("off")
        self.git("checkout", "-q", "-b", "feat/x")
        self.assertEqual(self.run_cmd("checks")[0], 0)
        code, out = self.run_cmd("automation", "--action", "commit")
        self.assertEqual(code, 6)
        self.assertIn("only when the user asks", out)
        self.assertIn("pr_fix=off", self.run_cmd("classify")[1])

    def test_invalid_level_is_a_config_error(self):
        self.profile("always")
        code, out = self.run_cmd("classify")
        self.assertEqual(code, 2)
        self.assertIn("automation.pr_fix", out)


def load_guard():
    spec = importlib.util.spec_from_file_location("git_guard", FRAMEWORK / "examples/automation/git-guard.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GitGuardTest(unittest.TestCase):
    def setUp(self):
        self.guard = load_guard()

    def blocked(self, command, branch="feat/x", target=None):
        with mock.patch.object(self.guard, "current_branch", return_value=branch), \
                mock.patch.object(self.guard, "push_target", return_value=target or branch):
            return self.guard.check(command, ".")

    def test_blocks_what_is_never_automated(self):
        for command in ("git push --force origin feat/x", "git push -f", "FOO=1 git push --force-with-lease",
                        "git push origin +feat/x", "git push origin :old", "git push --delete origin x",
                        "git push origin HEAD:main", "git -C sub push origin release/2.0", "git push --tags",
                        "git merge main", "git tag v1.0", "git branch -D x", "gh pr merge 12",
                        "echo ok && git push --mirror", "gh api -X PUT repos/o/r/pulls/1/merge --admin",
                        "gh pr create --base main --admin"):
            self.assertTrue(self.blocked(command), command)
        self.assertTrue(self.blocked("git push", branch="main"))
        self.assertTrue(self.blocked("git push origin HEAD", branch="develop"))
        self.assertTrue(self.blocked("git push", branch="feat/x", target="main"))
        with mock.patch.dict("os.environ", {"OMNI_GUARD_PROTECTED": "develop"}):   # main/master stay protected
            self.assertTrue(self.blocked("git push origin HEAD:master"))
            self.assertTrue(self.blocked("git push origin HEAD:develop"))   # upstream set to main

    def test_allows_the_fix_loop(self):
        for command in ("git switch -c omni/T1", "git checkout -b omni/T1", "git push -u origin omni/T1",
                        "git push -u origin HEAD", "gh pr view omni/T1",
                        "gh pr create --base main --head omni/T1 --title 'T1: x' --body-file s.md",
                        "git push origin HEAD", "git push -u origin feat/x", "git commit -m x", "git tag",
                        "git tag -l 'v*'", "git merge --abort", "git status", "gh pr view 3"):
            self.assertIsNone(self.blocked(command), command)

    def test_hook_protocol(self):
        event = {"tool_name": "Bash", "tool_input": {"command": "git merge main"}, "cwd": "."}
        err = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(json.dumps(event))), redirect_stderr(err):
            self.assertEqual(self.guard.main(), 2)
        self.assertIn("human gate", err.getvalue())
        with mock.patch("sys.stdin", io.StringIO(json.dumps({"tool_name": "Read"}))):
            self.assertEqual(self.guard.main(), 0)


if __name__ == "__main__":
    unittest.main()
