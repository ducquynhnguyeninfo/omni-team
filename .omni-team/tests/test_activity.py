import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import activity, artifacts  # noqa: E402


def report(n: int, day: int, size: int = 3000) -> str:
    body = f"report {n}\n" + ("x" * size) + f"\nVERDICT: REQUEST_CHANGES — attempt {n}"
    return artifacts.format_entry("code-reviewer", "REQUEST_CHANGES", dt.datetime(2026, 10, day, 9, n), 1.0, "t", body)


class SinceDateTest(unittest.TestCase):
    def test_forms(self):
        today = dt.date(2026, 10, 19)
        self.assertEqual(activity.since_date("today", today), "2026-10-19")
        self.assertEqual(activity.since_date("yesterday", today), "2026-10-18")
        self.assertEqual(activity.since_date("7d", today), "2026-10-12")
        self.assertEqual(activity.since_date("2026-10-01", today), "2026-10-01")
        with self.assertRaises(ValueError):
            activity.since_date("last week", today)


class ActivityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.runs = self.root / ".omni-team" / "runs"

    def tearDown(self):
        self.tmp.cleanup()

    def test_rotated_reports_and_journal_sessions_are_dated(self):
        t1 = self.runs / "T1"
        for n in range(1, 6):                   # small cap: earlier reports move to the index
            artifacts.append(t1 / "code-reviewer.md", report(n, day=17 + n % 2), max_kb=8)
        session = artifacts.format_session(dt.datetime(2026, 10, 18, 17, 30), "**Done**: parser\n**Next**: tests")
        artifacts.append(t1 / "_journal.md", session, max_kb=40)
        (t1 / "_summary.md").write_text("## Invocation 2026-10-18T00:00:00\nnot an event\n")
        (self.runs / "T2").mkdir(parents=True)

        folders = activity.task_folders(self.root, ".omni-team/runs/{task_id}")
        self.assertEqual(sorted(folders), ["T1", "T2"])
        found = activity.events("T1", folders["T1"])
        self.assertEqual(len([e for e in found if e.source == "code-reviewer"]), 5, "indexed + full reports")
        self.assertNotIn("_summary", {e.source for e in found})

        recent = activity.since(found, "2026-10-18")
        self.assertEqual([e.when for e in recent], sorted(e.when for e in recent))
        self.assertTrue(all(e.when >= "2026-10-18" for e in recent))
        journal = [e for e in recent if e.source == "journal"]
        self.assertEqual((journal[0].verdict, journal[0].summary), ("—", "Done: parser"))

        text = activity.render(recent)
        self.assertIn("📅 2026-10-18", text)
        self.assertIn("17:30 journal — Done: parser", text)
        self.assertIn("code-reviewer REQUEST_CHANGES — attempt", text)

    def test_journal_rotates_like_reports(self):
        path = self.runs / "T1" / "_journal.md"
        for n in range(1, 8):
            session = artifacts.format_session(dt.datetime(2026, 10, 18, 9, n), f"Done: step {n}\n" + "y" * 3000)
            artifacts.append(path, session, max_kb=8)
        hot = path.read_text()
        self.assertTrue(hot.startswith("# Journal") and "Earlier sessions" in hot)
        rows, entries = artifacts.parse(hot)
        self.assertEqual(len(rows) + len(entries), 7)
        self.assertIn("| — | Done: step 1 |", rows[0])
        self.assertIn("Done: step 1\n", (path.parent / "_archive" / "_journal.md").read_text())

    def test_hand_written_text_is_moved_not_lost(self):
        path = self.runs / "T1" / "code-reviewer.md"
        path.parent.mkdir(parents=True)
        path.write_text("## code-reviewer — aem-01 — attempt 1\nhand-written finding F1\n")
        (path.parent / "spec.md").write_text("not a role file\n")
        self.assertEqual(activity.unrecorded(path.parent, lambda name: name == "code-reviewer"), ["code-reviewer.md"])

        self.assertEqual(artifacts.append(path, report(1, day=18), max_kb=40), "stray")
        archive = (path.parent / "_archive" / "code-reviewer.md").read_text()
        self.assertIn("hand-written finding F1", archive)
        rows, entries = artifacts.parse(path.read_text())
        self.assertEqual((len(rows), len(entries)), (1, 1))
        self.assertIn("moved verbatim", rows[0])
        self.assertEqual(activity.unrecorded(path.parent, lambda name: name == "code-reviewer"), [])
        self.assertEqual(artifacts.append(path, report(2, day=18), max_kb=40), "", "clean file: nothing moved")

    def test_artifacts_dir_without_task_slot_fails_loudly(self):
        with self.assertRaises(ValueError):
            activity.task_folders(self.root, ".omni-team/runs")


if __name__ == "__main__":
    unittest.main()
