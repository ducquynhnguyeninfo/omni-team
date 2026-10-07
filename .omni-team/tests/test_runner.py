import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.roles import Role  # noqa: E402
from lib.runner import EngineError, engine_argv, parse_verdict, run_gate  # noqa: E402

ROLE = Role("code-reviewer", "d", "standard", "read-only", "body\n", Path("x.md"))
RUN_ROLE = Role("smoke-tester", "d", "standard", "run", "body\n", Path("y.md"))


class VerdictTest(unittest.TestCase):
    def test_plain_and_decorated(self):
        self.assertEqual(parse_verdict("x\nVERDICT: APPROVE — fine"), "APPROVE")
        self.assertEqual(parse_verdict("**VERDICT:** `REQUEST_CHANGES` — 2 warnings"), "REQUEST_CHANGES")
        self.assertEqual(parse_verdict("> verdict: request changes - x"), "REQUEST_CHANGES")

    def test_last_verdict_line_wins(self):
        self.assertEqual(parse_verdict("VERDICT: BLOCK — a\n...\nVERDICT: APPROVE — b"), "APPROVE")

    def test_block_vs_blocked(self):
        self.assertEqual(parse_verdict("VERDICT: BLOCKED — server down"), "BLOCKED")
        self.assertEqual(parse_verdict("VERDICT: BLOCK — sql injection"), "BLOCK")

    def test_aliases(self):
        self.assertEqual(parse_verdict("VERDICT: SHIP-READY"), "APPROVE")
        self.assertEqual(parse_verdict("VERDICT: NOT-IN-SCOPE"), "NOT_APPLICABLE")
        self.assertEqual(parse_verdict("VERDICT: PLAN_READY — 4 phases"), "PLAN_READY")

    def test_no_guessing_from_prose(self):
        self.assertEqual(parse_verdict("I would APPROVE this, no BLOCK issues."), "UNKNOWN")

    def test_template_legend_is_unknown(self):
        self.assertEqual(parse_verdict("VERDICT: <APPROVE|BLOCK> — summary"), "UNKNOWN")


class EngineArgvTest(unittest.TestCase):
    ENGINE = {"cmd": ["tool", "-m", "{tier}", "{prompt}"], "cmd_run": ["tool", "--rw", "{prompt}"],
              "tiers": {"standard": "mid"}}

    def test_substitution(self):
        self.assertEqual(engine_argv(self.ENGINE, ROLE, "P {tier}"), (["tool", "-m", "mid", "P {tier}"], None))

    def test_run_roles_use_cmd_run(self):
        self.assertEqual(engine_argv(self.ENGINE, RUN_ROLE, "P"), (["tool", "--rw", "P"], None))

    def test_prompt_goes_to_stdin_without_placeholder(self):
        engine = {"cmd": ["tool", "--allowedTools", "Read,Grep"], "tiers": {}}
        self.assertEqual(engine_argv(engine, ROLE, "P"), (["tool", "--allowedTools", "Read,Grep"], "P"))

    def test_missing_cmd(self):
        with self.assertRaises(EngineError):
            engine_argv({}, ROLE, "P")


class RunGateTest(unittest.TestCase):
    def _run(self, engine, dry_run=False):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "runs" / "code-reviewer.md"
            result = run_gate(role=ROLE, protocol="proto\n", invocation="scope", engine_name="t",
                              engine=engine, project_root=Path(tmp), artifact_path=artifact,
                              timeout_s=30, dry_run=dry_run)
            return result, artifact.read_text(encoding="utf-8")

    def test_dry_run_appends_artifact(self):
        result, text = self._run({"cmd": ["echo", "{prompt}"]}, dry_run=True)
        self.assertEqual(result.verdict, "APPROVE")
        self.assertIn("verdict: **APPROVE**", text)

    def test_real_process_reads_prompt_from_stdin(self):
        script = "import sys; d = sys.stdin.read(); print('VERDICT: REQUEST_CHANGES' if 'scope' in d else 'no')"
        result, _ = self._run({"cmd": [sys.executable, "-c", script]})
        self.assertEqual(result.verdict, "REQUEST_CHANGES")

    def test_missing_binary_is_blocked(self):
        result, _ = self._run({"cmd": ["definitely-not-a-real-binary-xyz", "{prompt}"]})
        self.assertEqual(result.verdict, "BLOCKED")

    def test_verdict_in_stderr_is_ignored(self):
        script = "import sys; print('VERDICT: APPROVE — echoed prompt', file=sys.stderr); sys.exit(1)"
        result, _ = self._run({"cmd": [sys.executable, "-c", script]})
        self.assertEqual(result.verdict, "BLOCKED")

    def test_failing_process_without_verdict_is_blocked(self):
        result, _ = self._run({"cmd": [sys.executable, "-c", "import sys; sys.exit(3)"]})
        self.assertEqual(result.verdict, "BLOCKED")


if __name__ == "__main__":
    unittest.main()
