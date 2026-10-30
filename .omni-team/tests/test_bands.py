import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

FRAMEWORK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FRAMEWORK))

from lib import bands  # noqa: E402

try:
    import yaml  # type: ignore  # noqa: F401
except ImportError:  # pragma: no cover
    yaml = None

SPEC = {"metrics": {
    "errors": {"log": 0.01, "diagnose": 0.02, "propose": 0.05, "owner": "oncall"},
    "success": {"direction": "down", "log": 0.98, "diagnose": 0.95, "propose": 0.9},
    "latency": {"diagnose": 800},
}}


class BandsTest(unittest.TestCase):
    def run_values(self, **values):
        return {r.metric.name: r.band for r in bands.evaluate(bands.parse(SPEC), values)}

    def test_bands_in_both_directions(self):
        got = self.run_values(errors=0.001, success=0.99, latency=100)
        self.assertEqual(set(got.values()), {"normal"})
        got = self.run_values(errors=0.02, success=0.96, latency=800)
        self.assertEqual(got, {"errors": "diagnose", "success": "log", "latency": "diagnose"})
        got = self.run_values(errors=0.5, success=0.1, latency=1)
        self.assertEqual(got, {"errors": "propose", "success": "propose", "latency": "normal"})

    def test_missing_or_non_numeric_metric_is_diagnose(self):
        got = self.run_values(errors="n/a", success=True)
        self.assertEqual(got, {"errors": "diagnose", "success": "diagnose", "latency": "diagnose"})

    def test_exit_code_follows_the_worst_band(self):
        metrics = bands.parse(SPEC)
        self.assertEqual(bands.exit_code(bands.evaluate(metrics, {"errors": 0.015, "success": 1, "latency": 1})), 0)
        self.assertEqual(bands.exit_code(bands.evaluate(metrics, {"errors": 0.03, "success": 1, "latency": 1})), 1)
        self.assertEqual(bands.exit_code(bands.evaluate(metrics, {"errors": 0.06, "success": 1, "latency": 1})), 6)

    def test_render_names_the_band_owner_and_next_step(self):
        text = bands.render(bands.evaluate(bands.parse(SPEC), {"errors": 0.06, "success": 1, "latency": 1}))
        self.assertIn("errors = 0.06: propose", text)
        self.assertIn("owner oncall", text)
        self.assertIn("`ba` writes the incident spec", text)

    def test_invalid_specs(self):
        for spec in ({}, {"metrics": {"x": {}}}, {"metrics": {"x": {"direction": "sideways", "log": 1}}},
                     {"metrics": {"x": {"log": 5, "diagnose": 1}}}, {"metrics": {"x": {"direction": "down", "log": 1, "propose": 5}}},
                     {"metrics": {"x": {"log": "high"}}}, {"metrics": {"x": 3}}):
            with self.assertRaises(bands.BandsError, msg=spec):
                bands.parse(spec)
        with self.assertRaises(bands.BandsError):
            bands.load_metrics("[1, 2]")
        with self.assertRaises(bands.BandsError):
            bands.load_metrics("{nope")


@unittest.skipIf(yaml is None, "needs PyYAML")
class BandsCommandTest(unittest.TestCase):
    def test_command_with_the_shipped_example(self):
        tmp = Path(tempfile.mkdtemp())
        fw = tmp / ".omni-team"
        shutil.copytree(FRAMEWORK / "lib", fw / "lib", ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("defaults.yaml", "orchestrator.py"):
            shutil.copy(FRAMEWORK / name, fw / name)
        (fw / "project").mkdir()
        shutil.copy(FRAMEWORK / "examples/automation/bands.yaml", fw / "project/bands.yaml")
        metrics = tmp / "m.json"

        def run(values):
            metrics.write_text(json.dumps(values))
            return subprocess.run([sys.executable, str(fw / "orchestrator.py"), "bands", "--metrics", str(metrics)],
                                  cwd=tmp, capture_output=True, text=True)

        done = run({"http_5xx_rate": 0.001, "p95_latency_ms": 120, "checkout_success_rate": 0.995})
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        done = run({"http_5xx_rate": 0.04, "p95_latency_ms": 120, "checkout_success_rate": 0.995})
        self.assertEqual(done.returncode, 6)
        self.assertIn("http_5xx_rate = 0.04: propose", done.stdout)
        metrics.write_text("{bad")
        bad = subprocess.run([sys.executable, str(fw / "orchestrator.py"), "bands", "--metrics", str(metrics)],
                             cwd=tmp, capture_output=True, text=True)
        self.assertEqual(bad.returncode, 2)


if __name__ == "__main__":
    unittest.main()
