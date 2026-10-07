import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.routing import RoutingError, Scope, evaluate_signals, glob_match, match_when, select_gates  # noqa: E402


def scope(paths=(), added=(), removed=(), components=()):
    return Scope(list(paths), list(added), list(removed), set(components))


class GlobTest(unittest.TestCase):
    def test_leading_double_star_matches_root(self):
        self.assertTrue(glob_match("auth/login.py", "**/auth/**"))
        self.assertTrue(glob_match("src/auth/login.py", "**/auth/**"))
        self.assertTrue(glob_match("main.tsx", "**/*.tsx"))

    def test_plain_pattern(self):
        self.assertTrue(glob_match("docs/a/b.md", "docs/**"))
        self.assertFalse(glob_match("src/docs.py", "docs/**"))


class PredicateTest(unittest.TestCase):
    def test_empty_when_matches(self):
        self.assertTrue(match_when({}, scope(), {}))

    def test_loc_bounds(self):
        s = scope(added=["x"] * 10)
        self.assertTrue(match_when({"loc_min": 10, "loc_max": 10}, s, {}))
        self.assertFalse(match_when({"loc_max": 9}, s, {}))

    def test_only_paths_requires_every_path(self):
        self.assertTrue(match_when({"only_paths": ["**/*.md"]}, scope(["a.md", "d/b.md"]), {}))
        self.assertFalse(match_when({"only_paths": ["**/*.md"]}, scope(["a.md", "b.py"]), {}))
        self.assertFalse(match_when({"only_paths": ["**/*.md"]}, scope([]), {}))

    def test_added_lines_regex_only_on_added(self):
        s = scope(added=["@router.get('/x')"], removed=["@router.post('/y')"])
        self.assertTrue(match_when({"added_lines": [r"@router\.get\("]}, s, {}))
        self.assertFalse(match_when({"added_lines": [r"@router\.post\("]}, s, {}))

    def test_keywords_case_insensitive_on_changed_lines(self):
        self.assertTrue(match_when({"keywords": ["api_key"]}, scope(removed=["API_KEY = 1"]), {}))

    def test_components_all_vs_any(self):
        s = scope(components={"api", "backend"})
        self.assertTrue(match_when({"components": ["api", "backend"]}, s, {}))
        self.assertFalse(match_when({"components": ["api", "web"]}, s, {}))
        self.assertTrue(match_when({"any_component": ["api", "web"]}, s, {}))

    def test_unknown_predicate_fails_loudly(self):
        with self.assertRaises(RoutingError):
            match_when({"stacks": ["backend"]}, scope(), {})

    def test_undefined_signal_fails_loudly(self):
        with self.assertRaises(RoutingError):
            match_when({"signals": ["nope"]}, scope(), {})

    def test_bad_regex_fails_loudly(self):
        with self.assertRaises(RoutingError):
            match_when({"added_lines": ["("]}, scope(added=["x"]), {})


class SignalTest(unittest.TestCase):
    def test_list_signal_is_or(self):
        defs = {"sec": [{"paths": ["**/auth/**"]}, {"keywords": ["password"]}]}
        self.assertTrue(evaluate_signals(defs, scope(added=["password=1"]))["sec"])
        self.assertTrue(evaluate_signals(defs, scope(paths=["auth/x.go"]))["sec"])
        self.assertFalse(evaluate_signals(defs, scope(paths=["x.go"]))["sec"])

    def test_signal_may_not_reference_signals(self):
        with self.assertRaises(RoutingError):
            evaluate_signals({"a": {"signals": ["b"]}}, scope())


TREE = {
    "signals": {"docs": {"only_paths": ["**/*.md"]}, "sec": {"keywords": ["token"]}},
    "routing": {
        "order": ["code-reviewer", "security-engineer", "qa-lead"],
        "base": [
            {"name": "docs", "when": {"signals": ["docs"]}, "agents": [], "final": True},
            {"name": "small", "when": {"loc_max": 5}, "agents": ["code-reviewer"]},
            {"name": "big", "when": {}, "agents": ["qa-lead", "code-reviewer"]},
        ],
        "add_if": [{"name": "security", "when": {"signals": ["sec"]}, "agents_add": ["security-engineer"]}],
    },
}


class SelectTest(unittest.TestCase):
    def test_first_base_wins_and_add_if_appends_in_order(self):
        sel = select_gates(TREE, scope(["a.py"], added=["token"] * 9))
        self.assertEqual(sel.base_rule, "big")
        self.assertEqual(sel.add_rules, ["security"])
        self.assertEqual(sel.gates, ["code-reviewer", "security-engineer", "qa-lead"])

    def test_final_base_rule_skips_add_if(self):
        sel = select_gates(TREE, scope(["README.md"], added=["token"]))
        self.assertEqual((sel.base_rule, sel.gates, sel.add_rules), ("docs", [], []))

    def test_deduplicates(self):
        sel = select_gates(TREE, scope(["a.py"], added=["x"]))
        self.assertEqual(sel.gates, ["code-reviewer"])


if __name__ == "__main__":
    unittest.main()
