import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import artifacts  # noqa: E402
from lib.roles import Role  # noqa: E402
from lib.runner import run_gate  # noqa: E402


def entry(n: int, verdict: str = "REQUEST_CHANGES", size: int = 3000) -> str:
    body = f"report {n}\n" + ("x" * size) + f"\nVERDICT: {verdict} — summary of attempt {n} | with a pipe"
    return artifacts.format_entry("code-reviewer", verdict, dt.datetime(2026, 1, 1, 0, 0, n), 1.0, "test", body)


class RotationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "runs" / "T1" / "code-reviewer.md"
        self.archive = self.path.parent / "_archive" / "code-reviewer.md"

    def tearDown(self):
        self.tmp.cleanup()

    def test_appends_until_the_cap(self):
        for n in range(1, 4):
            self.assertFalse(artifacts.append(self.path, entry(n), max_kb=40))
        rows, entries = artifacts.parse(self.path.read_text())
        self.assertEqual((rows, [e.when for e in entries]), ([], ["2026-01-01T00:00:01", "2026-01-01T00:00:02",
                                                               "2026-01-01T00:00:03"]))
        self.assertFalse(self.archive.exists())

    def test_rotation_keeps_index_and_latest_and_archives_everything(self):
        rotated = [artifacts.append(self.path, entry(n), max_kb=10) for n in range(1, 8)]
        self.assertTrue(any(rotated))
        hot = self.path.read_text()
        self.assertLessEqual(len(hot.encode()), 10 * 1024 + 4000, "hot file stays near the cap")
        rows, entries = artifacts.parse(hot)
        self.assertEqual(entries[-1].when, "2026-01-01T00:00:07", "newest report always kept in full")
        self.assertEqual(len(rows) + len(entries), 7, "every report is either indexed or present")
        self.assertEqual([r.split("|")[1].strip() for r in rows], [str(i) for i in range(1, len(rows) + 1)])
        self.assertIn("summary of attempt 1 / with a pipe", rows[0], "pipes in summaries cannot break the table")
        archived = self.archive.read_text()
        for n in range(1, len(rows) + 1):
            self.assertIn(f"report {n}\n", archived, f"report {n} archived verbatim")

    def test_disabled_and_single_large_entry(self):
        for n in range(1, 6):
            artifacts.append(self.path, entry(n), max_kb=0)
        self.assertFalse(self.archive.exists())
        big = Path(self.tmp.name) / "big.md"
        self.assertFalse(artifacts.append(big, entry(1, size=50_000), max_kb=10), "a lone report is never moved")

    def test_legacy_file_is_parsed_and_rotated(self):
        self.path.parent.mkdir(parents=True)
        legacy = "".join("\n\n---\n\n" + entry(n) for n in range(1, 5))     # pre-2.8 append-only format
        self.path.write_text(legacy)
        artifacts.append(self.path, entry(5), max_kb=8)
        rows, entries = artifacts.parse(self.path.read_text())
        self.assertEqual(len(rows) + len(entries), 5)
        self.assertIn("report 1\n", self.archive.read_text())

    def test_run_gate_writes_through_rotation(self):
        role = Role("code-reviewer", "d", "standard", "read-only", "body\n", Path("x.md"))
        engine = {"cmd": [sys.executable, "-c", "print('x' * 6000); print('VERDICT: REQUEST_CHANGES — again')"]}
        for _ in range(4):
            run_gate(role=role, protocol="p\n", invocation="scope", engine_name="t", engine=engine,
                     project_root=Path(self.tmp.name), artifact_path=self.path, timeout_s=30, max_kb=10)
        self.assertTrue(self.archive.exists())
        rows, entries = artifacts.parse(self.path.read_text())
        self.assertEqual(len(rows) + len(entries), 4)
        self.assertTrue(all(r.split("|")[3].strip() == "REQUEST_CHANGES" for r in rows))


if __name__ == "__main__":
    unittest.main()
