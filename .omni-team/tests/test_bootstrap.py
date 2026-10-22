import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

FRAMEWORK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FRAMEWORK))

from lib import bootstrap  # noqa: E402


class UseVenvTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "requirements.txt").write_text("pyyaml>=6.0\n", encoding="utf-8")
        self.python = bootstrap.venv_python(self.root)
        patches = [
            mock.patch.object(bootstrap.importlib.util, "find_spec", return_value=None),
            mock.patch.dict(os.environ, {bootstrap.OPT_OUT: ""}),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def run_ensure(self, results):
        """use_venv with subprocess.run answering from `results` (one return code per call)."""
        calls = []

        def fake_run(cmd, **_):
            calls.append(cmd)
            if cmd[1:3] == ["-m", "venv"]:
                self.python.parent.mkdir(parents=True)
                self.python.write_text("", encoding="utf-8")
            return SimpleNamespace(returncode=results.pop(0), stdout="", stderr="no network")

        err = io.StringIO()
        with mock.patch.object(bootstrap.subprocess, "run", side_effect=fake_run), \
                mock.patch.object(bootstrap.os, "execv") as execv, redirect_stderr(err):
            bootstrap.use_venv(self.root, ["orchestrator.py", "status"])
        return calls, execv, err.getvalue()

    def test_creates_venv_installs_and_reruns_under_it(self):
        calls, execv, err = self.run_ensure([0, 1, 0])   # venv, `import yaml` probe, pip
        self.assertEqual(calls[0][1:], ["-m", "venv", str(self.root / ".venv")])
        self.assertIn("pip", calls[2])
        self.assertIn(str(self.root / "requirements.txt"), calls[2])
        execv.assert_called_once_with(str(self.python), [str(self.python), "orchestrator.py", "status"])
        self.assertIn("setting up", err)

    def test_existing_venv_is_used_even_when_yaml_is_here(self):
        self.python.parent.mkdir(parents=True)
        self.python.write_text("", encoding="utf-8")
        with mock.patch.object(bootstrap.importlib.util, "find_spec", return_value=object()):
            calls, execv, err = self.run_ensure([])
        self.assertEqual(calls, [])
        execv.assert_called_once()
        self.assertEqual(err, "")

    def test_failed_install_falls_through_to_the_pyyaml_error(self):
        calls, execv, err = self.run_ensure([0, 1, 1])   # venv, `import yaml` probe, pip
        execv.assert_not_called()
        self.assertIn("could not set up", err)
        self.assertIn("no network", err)

    def test_opt_out_and_present_yaml_without_venv_do_nothing(self):
        with mock.patch.dict(os.environ, {bootstrap.OPT_OUT: "1"}):
            calls, execv, _ = self.run_ensure([])
        self.assertEqual(calls, [])
        with mock.patch.object(bootstrap.importlib.util, "find_spec", return_value=object()):
            calls, execv, _ = self.run_ensure([])
        self.assertEqual(calls, [])
        execv.assert_not_called()

    def test_inside_the_venv_without_yaml_repairs_it_and_does_not_loop(self):
        self.python.parent.mkdir(parents=True)
        self.python.write_text("", encoding="utf-8")
        with mock.patch.object(bootstrap.sys, "prefix", str(self.root / ".venv")):
            calls, execv, err = self.run_ensure([1, 0])   # `import yaml` probe, pip
        self.assertIn("pip", calls[1])
        self.assertIn("installing", err)
        execv.assert_not_called()


class SetupTest(unittest.TestCase):
    def test_ui_probe_without_node_is_reported_not_fatal_to_python(self):
        root = Path(tempfile.mkdtemp())
        with mock.patch.object(bootstrap.shutil, "which", return_value=None):
            ok, detail = bootstrap.setup_ui_probe(root)
        self.assertFalse(ok)
        self.assertIn("Node.js", detail)

    def test_setup_reports_each_part_and_fails_when_one_fails(self):
        out = io.StringIO()
        with mock.patch.object(bootstrap, "setup_python", return_value=""), \
                mock.patch.object(bootstrap, "setup_ui_probe", return_value=(False, "no npm")), \
                mock.patch("sys.stdout", out):
            code = bootstrap.setup(Path(tempfile.mkdtemp()) / ".omni-team", ui_probe=True)
        self.assertEqual(code, 2)
        self.assertIn("✅ Python environment", out.getvalue())
        self.assertIn("❌ UI probe", out.getvalue())


if __name__ == "__main__":
    unittest.main()
