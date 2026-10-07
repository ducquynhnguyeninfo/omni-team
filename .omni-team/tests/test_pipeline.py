import sys
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import pipeline  # noqa: E402
from lib.routing import Scope  # noqa: E402
from lib.state import GateState, RunState  # noqa: E402


class RecordTest(unittest.TestCase):
    def setUp(self):
        self.gate = GateState(name="code-reviewer")
        self.state = RunState(task_id="t", gates=[self.gate])
        self.budget = pipeline.Budget(request_changes_max=2, block_max=1)

    def test_pass_stores_approved_snapshot(self):
        self.assertEqual(pipeline.record(self.state, self.gate, "APPROVE", "tree1", self.budget), (None, ""))
        self.assertEqual((self.gate.status, self.gate.approved_tree), ("passed", "tree1"))

    def test_request_changes_pauses_then_exhausts_budget(self):
        self.assertEqual(pipeline.record(self.state, self.gate, "REQUEST_CHANGES", "t", self.budget)[0],
                         pipeline.EXIT_PAUSED)
        code, escape = pipeline.record(self.state, self.gate, "REQUEST_CHANGES", "t", self.budget)
        self.assertEqual(code, pipeline.EXIT_RC_BUDGET)
        self.assertIn("budget", escape)
        self.assertEqual(self.state.phase, "halted")

    def test_block_budget_counted_separately(self):
        self.assertEqual(pipeline.record(self.state, self.gate, "BLOCK", "t", self.budget)[0],
                         pipeline.EXIT_BLOCK_BUDGET)
        self.assertEqual(self.gate.request_changes_count, 0)

    def test_human_and_unknown(self):
        self.assertEqual(pipeline.record(self.state, self.gate, "BLOCKED", "t", self.budget)[0], pipeline.EXIT_HUMAN)
        self.assertEqual(pipeline.record(self.state, GateState("x"), "UNKNOWN", "t", self.budget)[0],
                         pipeline.EXIT_UNKNOWN)
        self.assertIn("code-reviewer: BLOCKED", self.state.halt_reason)
        self.assertIn("x: UNKNOWN", self.state.halt_reason)

    def test_most_severe(self):
        self.assertIsNone(pipeline.most_severe([None, None]))
        self.assertEqual(pipeline.most_severe([pipeline.EXIT_PAUSED, None, pipeline.EXIT_HUMAN]), pipeline.EXIT_HUMAN)


class ReopenTest(unittest.TestCase):
    def make_state(self):
        gates = [GateState("data-reviewer", status="passed", approved_tree="old"),
                 GateState("code-reviewer", status="passed", approved_tree="old"),
                 GateState("qa-lead", status="pending")]
        return RunState(task_id="t", gates=gates)

    def test_reopens_only_gates_the_delta_would_route(self):
        state = self.make_state()
        delta = Scope(["db/migrations/2.sql"], ["ALTER TABLE x"])
        reopened = pipeline.reopen_changed(state, "new", lambda old: delta, lambda s: ["data-reviewer"])
        self.assertEqual([name for name, _ in reopened], ["data-reviewer"])
        self.assertEqual(state.gate("data-reviewer").status, "pending")
        self.assertIn("re-opened", state.gate("data-reviewer").note)
        self.assertEqual(state.gate("code-reviewer").status, "passed")

    def test_same_tree_or_empty_delta_keeps_approval(self):
        state = self.make_state()
        self.assertEqual(pipeline.reopen_changed(state, "old", lambda o: None, lambda s: ["data-reviewer"]), [])
        self.assertEqual(pipeline.reopen_changed(state, "new", lambda o: Scope(), lambda s: ["data-reviewer"]), [])

    def test_unknown_snapshot_reopens(self):
        state = self.make_state()
        reopened = pipeline.reopen_changed(state, "new", lambda old: None, lambda s: [])
        self.assertEqual(len(reopened), 2)


class RunStageTest(unittest.TestCase):
    def test_parallel_runs_concurrently_and_keeps_order(self):
        active, peak, lock = [0], [0], threading.Lock()

        def work(gate):
            with lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            time.sleep(0.05)
            with lock:
                active[0] -= 1
            return gate.name.upper()

        gates = [GateState(n) for n in ("a", "b", "c")]
        results = pipeline.run_stage(gates, work, max_parallel=3)
        self.assertEqual([r for _, r in results], ["A", "B", "C"])
        self.assertGreater(peak[0], 1)

    def test_serial_when_max_parallel_is_one(self):
        order = []
        pipeline.run_stage([GateState("a"), GateState("b")], lambda g: order.append(g.name), max_parallel=1)
        self.assertEqual(order, ["a", "b"])


if __name__ == "__main__":
    unittest.main()
