import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib import profile  # noqa: E402
from lib.routing import Scope, select_gates  # noqa: E402

try:
    import yaml  # type: ignore  # noqa: F401
except ImportError:  # pragma: no cover
    yaml = None


class MergeTest(unittest.TestCase):
    DEFAULTS = {
        "signals": {"a": {"paths": ["x"]}, "b": {"paths": ["y"]}},
        "quality_limits": {"file_lines": 500, "function_lines": 100},
        "routing": {"order": ["r1"], "base": [{"name": "d", "when": {}, "agents": []}],
                    "add_if": [{"name": "default-add"}]},
        "orchestrator": {"engine": "claude", "retry_budget": {"block_max": 3, "request_changes_max": 3},
                         "engines": {"claude": {"cmd": ["c"], "tiers": {"deep": "opus"}}}},
    }

    def test_signals_merge_by_name(self):
        merged = profile.merge(self.DEFAULTS, {"signals": {"a": {"paths": ["z"]}}})
        self.assertEqual(merged["signals"], {"a": {"paths": ["z"]}, "b": {"paths": ["y"]}})

    def test_quality_limits_merge_by_key(self):
        merged = profile.merge(self.DEFAULTS, {"quality_limits": {"file_lines": 300}})
        self.assertEqual(merged["quality_limits"], {"file_lines": 300, "function_lines": 100})

    def test_routing_extra_add_if_appends(self):
        merged = profile.merge(self.DEFAULTS, {"routing": {"extra_add_if": [{"name": "mine"}]}})
        self.assertEqual([r["name"] for r in merged["routing"]["add_if"]], ["default-add", "mine"])
        self.assertEqual(merged["routing"]["order"], ["r1"])

    def test_routing_unknown_key_fails(self):
        with self.assertRaises(profile.ProfileError):
            profile.merge(self.DEFAULTS, {"routing": {"extra": []}})

    def test_orchestrator_engines_merge(self):
        merged = profile.merge(self.DEFAULTS, {"orchestrator": {
            "engine": "codex", "retry_budget": {"block_max": 1},
            "engines": {"claude": {"tiers": {"deep": "x"}}, "codex": {"cmd": ["k"]}}}})
        orch = merged["orchestrator"]
        self.assertEqual(orch["engine"], "codex")
        self.assertEqual(orch["retry_budget"], {"block_max": 1, "request_changes_max": 3})
        self.assertEqual(orch["engines"]["claude"], {"cmd": ["c"], "tiers": {"deep": "x"}})
        self.assertIn("codex", orch["engines"])

    def test_components_validation(self):
        with self.assertRaises(profile.ProfileError):
            profile.components({"components": [{"name": "api"}]})
        self.assertEqual(profile.components({"components": None}), [])


@unittest.skipIf(yaml is None, "PyYAML not installed")
class ShippedFilesTest(unittest.TestCase):
    def test_default_profile_and_examples_load_and_route(self):
        paths = [None] + sorted((ROOT / "examples").glob("*/profile.yaml"))
        self.assertGreaterEqual(len(paths), 4)
        for path in paths:
            tree = profile.load(path)
            profile.components(tree)
            for scenario in (
                Scope(["README.md"], ["doc"] * 40),
                Scope(["src/auth/login.ts"], ["const token = 1"] * 200),
                Scope(["db/migrations/001.sql"], ["CREATE TABLE x ();"] * 30),
            ):
                select_gates(tree, scenario)

    def test_default_routing_examples(self):
        tree = profile.load()
        docs = select_gates(tree, Scope(["README.md", "docs/a.md"], ["x"] * 300))
        self.assertEqual(docs.gates, [])
        feature = select_gates(tree, Scope(["api/routes.py", "api/migrations/0002_add.py"],
                                           ["@router.post('/items')"] + ["x = 1"] * 400))
        for gate in ("data-reviewer", "code-reviewer", "test-engineer", "perf-engineer", "qa-lead"):
            self.assertIn(gate, feature.gates)
        self.assertLess(feature.gates.index("data-reviewer"), feature.gates.index("code-reviewer"))
        self.assertEqual(feature.gates[-1], "qa-lead")

    def test_architect_gate_joins_the_review_stage(self):
        sel = select_gates(profile.load(), Scope(["docker-compose.yml", "api/app.py"], ["x = 1"] * 200))
        self.assertIn("architect", sel.gates)
        review_stage = next(s for s in sel.stages if "code-reviewer" in s)
        self.assertIn("architect", review_stage)


if __name__ == "__main__":
    unittest.main()
