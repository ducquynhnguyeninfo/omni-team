import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchlib import (Case, Defect, RunResult, extract_findings, load_cases, materialize,  # noqa: E402
                      score)

KNOWN = ["app/db.py", "app/orders.py", "src/routes.ts"]


def make_case(defects):
    return Case("c", "python", "req", defects, Path("."))


class ExtractTest(unittest.TestCase):
    def test_formats_seen_in_the_wild(self):
        text = "\n".join([
            "- [app/db.py:20] (CR-6) injection",               # omni-team
            "app/orders.py:21 — slice drops the last item",    # /code-review
            "/private/tmp/x/py-search/app/db.py:22-23 leak",   # absolute path with range
            "`orders.py:27` floor division",                   # basename only
            "see docs/README.md:3 and unknown.py:9",           # unknown files are ignored
        ])
        found = [(f.file, f.line, f.end) for f in extract_findings(text, KNOWN)]
        self.assertEqual(found, [("app/db.py", 20, 20), ("app/orders.py", 21, 21),
                                 ("app/db.py", 22, 23), ("app/orders.py", 27, 27)])

    def test_json_findings_from_headless_code_review(self):
        text = '```json\n[{"file": "app/orders.py", "line": 19, "summary": "slice"},\n {"file": "x.py", "line": 3}]\n```'
        self.assertEqual([(f.file, f.line) for f in extract_findings(text, KNOWN)], [("app/orders.py", 19)])

    def test_template_metadata_lines_are_not_findings(self):
        text = "**Pattern reference**: `app/db.py:8` uses a bound parameter\n- [app/db.py:20] (CR-6) injection"
        self.assertEqual([f.line for f in extract_findings(text, KNOWN)], [20])

    def test_duplicates_collapse(self):
        self.assertEqual(len(extract_findings("app/db.py:20 x\napp/db.py:20 y", KNOWN)), 1)


class ScoreTest(unittest.TestCase):
    def setUp(self):
        self.case = make_case([
            Defect("D1", "app/db.py", 20, 21, "critical", "sql", ["injection"]),
            Defect("D2", "app/db.py", 30, 30, "warning", "leak", ["close"]),
        ])
        self.case.root = Path(tempfile.mkdtemp())
        (self.case.root / "change" / "app").mkdir(parents=True)
        (self.case.root / "change" / "app" / "db.py").write_text("x")
        (self.case.root / "base").mkdir()

    def run_score(self, text):
        result = RunResult("c", "c", 1, ok=True, text=text)
        score(self.case, result)
        return result

    def test_strict_within_tolerance_and_extras(self):
        r = self.run_score("app/db.py:23 injection here\napp/db.py:50 style nit")
        self.assertEqual(r.caught_strict, ["D1"])
        self.assertEqual([f.line for f in r.extra], [50])

    def test_outside_tolerance_is_not_strict_but_can_be_lenient(self):
        r = self.run_score("db.py: the connection is never closed on error (around line 40)\napp/db.py:40 close it")
        self.assertEqual(r.caught_strict, [])
        self.assertEqual(r.caught_lenient, ["D2"])

    def test_no_output_catches_nothing(self):
        r = self.run_score("")
        self.assertEqual((r.caught_strict, r.caught_lenient, r.extra), ([], [], []))


class CasesTest(unittest.TestCase):
    def test_answer_keys_point_inside_the_changed_files(self):
        for case in load_cases():
            for d in case.defects:
                changed = case.root / "change" / d.file
                lines = (changed if changed.exists() else case.root / "base" / d.file).read_text().splitlines()
                self.assertTrue(1 <= d.start <= d.end <= len(lines), f"{case.id}:{d.id}")
                self.assertTrue(any(lines[i - 1].strip() for i in range(d.start, d.end + 1)), f"{case.id}:{d.id} blank")

    def test_materialized_repo_has_no_answer_key_and_uncommitted_change(self):
        import subprocess
        case = load_cases(["py-search"])[0]
        with tempfile.TemporaryDirectory() as tmp:
            repo = materialize(case, Path(tmp))
            self.assertFalse((repo / "case.yaml").exists())
            status = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout
            self.assertIn("app/db.py", status)


if __name__ == "__main__":
    unittest.main()
