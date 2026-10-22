"""
The toolset `.omni-team/` scripts run on, kept inside the vendored folder in `.omni-team/.venv`.

- Python: a venv with `requirements.txt` (PyYAML). `orchestrator.py setup` creates it; every
  orchestrator command re-runs itself under it when it exists, and creates it on first use
  when the running interpreter lacks PyYAML.
- UI probe (`setup --ui-probe`): Playwright for `tools/ui-probe.mjs` under `.venv/node`, plus
  Chromium when no installed Chrome/Edge starts.

The folder is git-ignored and survives upgrades; deleting it undoes everything here. Set
`OMNI_TEAM_NO_BOOTSTRAP=1` to keep commands on the running interpreter. Stdlib only: this runs
before anything else is importable.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

VENV = ".venv"
OPT_OUT = "OMNI_TEAM_NO_BOOTSTRAP"
EXIT_MISSING = 3    # tools/ui-probe.mjs: browser library or browser missing


def venv_python(framework_root: Path) -> Path:
    venv = framework_root / VENV
    return venv / "Scripts" / "python.exe" if os.name == "nt" else venv / "bin" / "python"


def node_prefix(framework_root: Path) -> Path:
    return framework_root / VENV / "node"


def _say(message: str) -> None:
    print(f"omni-team: {message}", file=sys.stderr)


def _step(command: List[str]) -> str:
    """Run one setup command; "" on success, else a short reason with the output tail."""
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode == 0:
        return ""
    tail = (done.stderr or done.stdout).strip().splitlines()[-3:]
    return f"{' '.join(command[:4])} … exited {done.returncode}\n  " + "\n  ".join(tail)


def _has_yaml(python: Path) -> bool:
    return subprocess.run([str(python), "-c", "import yaml"], capture_output=True).returncode == 0


def setup_python(framework_root: Path) -> str:
    """Create the venv if needed and install requirements into it; "" on success, else why not."""
    python = venv_python(framework_root)
    if not python.exists():
        failed = _step([sys.executable, "-m", "venv", str(framework_root / VENV)])
        if failed:
            return failed
    if _has_yaml(python):
        return ""
    return _step([str(python), "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
                  "-r", str(framework_root / "requirements.txt")])


def setup_ui_probe(framework_root: Path) -> Tuple[bool, str]:
    """Playwright under .venv/node, and a browser it can start. (ok, what was found or why not)."""
    node, npm = shutil.which("node"), shutil.which("npm")
    if not node or not npm:
        return False, "Node.js 18+ with npm not found; smoke-tester falls back to a browser tool's evaluate"
    prefix = node_prefix(framework_root)
    if not (prefix / "node_modules" / "playwright").is_dir():
        failed = _step([npm, "install", "--prefix", str(prefix), "--no-audit", "--no-fund", "--silent", "playwright"])
        if failed:
            return False, failed
    check = [node, str(framework_root / "tools" / "ui-probe.mjs"), "--check"]
    done = subprocess.run(check, capture_output=True, text=True)
    if done.returncode == EXIT_MISSING:
        failed = _step([node, str(prefix / "node_modules" / "playwright" / "cli.js"), "install", "chromium"])
        if failed:
            return False, failed
        done = subprocess.run(check, capture_output=True, text=True)
    output = (done.stdout or done.stderr).strip()
    return done.returncode == 0, output.splitlines()[0] if output else f"exit {done.returncode}"


def setup(framework_root: Path, ui_probe: bool) -> int:
    """`orchestrator.py setup`: install the toolset and say what is ready. 0 when all of it is."""
    rel = f"{framework_root.name}/{VENV}"
    failed = setup_python(framework_root)
    print(f"❌ Python environment {rel}: {failed}" if failed else
          f"✅ Python environment {rel} (orchestrator: {venv_python(framework_root).relative_to(framework_root.parent)})")
    ok = not failed
    if ui_probe:
        probe_ok, detail = setup_ui_probe(framework_root)
        print(f"{'✅' if probe_ok else '❌'} UI probe ({rel}/node): {detail}")
        ok = ok and probe_ok
    return 0 if ok else 2


def use_venv(framework_root: Path, argv: List[str]) -> None:
    """Re-run argv under the framework's venv when it exists, or when PyYAML is missing here."""
    if os.environ.get(OPT_OUT):
        return
    if Path(sys.prefix).resolve() == (framework_root / VENV).resolve():
        if importlib.util.find_spec("yaml") is None:      # an earlier install failed half-way
            _say(f"PyYAML missing in {framework_root / VENV}; installing…")
            failed = setup_python(framework_root)
            if failed:
                _say(f"could not install: {failed}")
            importlib.invalidate_caches()
        return
    python = venv_python(framework_root)
    if not python.exists():
        if importlib.util.find_spec("yaml") is not None:
            return
        _say(f"PyYAML not found; setting up {framework_root / VENV} (one time)…")
        failed = setup_python(framework_root)
        if failed:
            _say(f"could not set up {framework_root / VENV}: {failed}")
            return   # the PyYAML error that follows explains the manual setup
    command = [str(python), *argv]
    if os.name == "nt":
        sys.exit(subprocess.call(command))
    os.execv(str(python), command)
