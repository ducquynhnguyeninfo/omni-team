import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

FRAMEWORK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FRAMEWORK))

import install  # noqa: E402
from lib import vendor  # noqa: E402

try:
    import yaml  # type: ignore  # noqa: F401
except ImportError:  # pragma: no cover
    yaml = None


def quiet(fn, *args):
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        return fn(*args)


class TempProject(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = (Path(self.tmp.name) / "chatbot").resolve()
        self.project.mkdir()
        self.target = self.project / ".omni-team"

    def tearDown(self):
        self.tmp.cleanup()


class RuntimeSetTest(unittest.TestCase):
    def test_every_entry_exists(self):
        self.assertTrue(vendor.expand(FRAMEWORK, vendor.RUNTIME_SET))

    def test_links_inside_the_slim_copy_resolve(self):
        files = set(vendor.expand(FRAMEWORK, vendor.RUNTIME_SET)) | {
            Path("project") / p for p in vendor.framework_files(FRAMEWORK / "project")}
        broken = []
        for rel in (f for f in files if f.suffix == ".md"):
            for target in re.findall(r"\]\(([^)#\s]+)", (FRAMEWORK / rel).read_text(encoding="utf-8")):
                if target.startswith("http"):
                    continue
                resolved = Path(*[p for p in (rel.parent / target).parts])
                parts = []
                for part in resolved.parts:
                    if part == "..":
                        parts.pop()
                    elif part != ".":
                        parts.append(part)
                path = Path(*parts) if parts else Path(".")
                if path not in files and not any(f.parts[:len(path.parts)] == path.parts for f in files):
                    broken.append(f"{rel} → {target}")
        self.assertEqual(broken, [])

    def test_orchestrator_imports_only_shipped_modules(self):
        shipped = {p.stem for p in vendor.expand(FRAMEWORK, vendor.RUNTIME_SET) if p.parts[0] == "lib"}
        for module in ("orchestrator.py",) + tuple(f"lib/{m}.py" for m in shipped if m != "__init__"):
            text = (FRAMEWORK / module).read_text(encoding="utf-8")
            used = set(re.findall(r"from lib(?:\.(\w+))? import ([\w, ]+)", text))
            names = {m for m, _ in used if m} | {n.strip() for m, ns in used if not m for n in ns.split(",")}
            names |= set(re.findall(r"from \.(\w+) import", text))
            self.assertTrue(names <= shipped, f"{module} imports {names - shipped}, not in RUNTIME_SET")


class VendorPlanTest(TempProject):
    def test_fresh_slim_copy(self):
        vplan = vendor.plan(FRAMEWORK, self.project)
        self.assertEqual((vplan.mode, vplan.flavor), ("fresh", "slim"))
        vendor.apply(vplan)
        for rel in ("AGENTS.md", "orchestrator.py", "lib/routing.py", "team/_protocol.md", "defaults.yaml",
                    "project/profile.yaml", "docs/profile.md", vendor.MANIFEST):
            self.assertTrue((self.target / rel).exists(), rel)
        for rel in ("install.py", "lib/vendor.py", "lib/adapters.py", "tests", "examples", "README.md",
                    "skills", "docs/maintaining.md", "runs"):
            self.assertFalse((self.target / rel).exists(), rel)
        manifest = json.loads((self.target / vendor.MANIFEST).read_text())
        self.assertEqual((manifest["flavor"], manifest["source"]), ("slim", str(FRAMEWORK)))
        self.assertNotIn("project/profile.yaml", manifest["files"])
        self.assertEqual(vendor.plan(FRAMEWORK, self.project).changes, 0, "second plan is a no-op")

    def test_skills_only_for_tools_without_native_skills_and_full_flavor(self):
        vendor.apply(vendor.plan(FRAMEWORK, self.project, with_skills=True))
        self.assertTrue((self.target / "skills" / "omni-task" / "SKILL.md").exists())
        vplan = vendor.plan(FRAMEWORK, self.project, full=True)
        vendor.apply(vplan)
        for rel in ("install.py", "tests", "examples", "docs/maintaining.md"):
            self.assertTrue((self.target / rel).exists(), rel)
        vendor.apply(vendor.plan(FRAMEWORK, self.project))      # back to slim removes them again
        for rel in ("install.py", "tests", "examples", "skills"):
            self.assertFalse((self.target / rel).exists(), rel)

    def test_upgrade_preserves_host_files_and_removes_only_what_it_shipped(self):
        vendor.apply(vendor.plan(FRAMEWORK, self.project))
        (self.target / "project" / "profile.yaml").write_text("version: 1\nproject: {name: Chatbot}\n")
        (self.target / "runs" / "T1").mkdir(parents=True)
        (self.target / "runs" / "T1" / "code-reviewer.md").write_text("report")
        (self.target / "team" / "old-role.md").write_text("shipped by an older version")
        (self.target / "team" / "my-notes.md").write_text("added by the user")
        manifest = json.loads((self.target / vendor.MANIFEST).read_text())
        manifest["files"].append("team/old-role.md")
        (self.target / vendor.MANIFEST).write_text(json.dumps(manifest))
        (self.target / "defaults.yaml").write_text("tampered: true\n")

        vplan = vendor.plan(FRAMEWORK, self.project)
        self.assertEqual(vplan.mode, "upgrade")
        vendor.apply(vplan)
        self.assertIn("Chatbot", (self.target / "project" / "profile.yaml").read_text())
        self.assertEqual((self.target / "runs" / "T1" / "code-reviewer.md").read_text(), "report")
        self.assertFalse((self.target / "team" / "old-role.md").exists())
        self.assertTrue((self.target / "team" / "my-notes.md").exists())
        self.assertEqual((self.target / "defaults.yaml").read_bytes(), (FRAMEWORK / "defaults.yaml").read_bytes())

    def test_legacy_full_copy_without_manifest_is_slimmed(self):
        shutil.copytree(FRAMEWORK, self.target, ignore=shutil.ignore_patterns("__pycache__", "runs"))
        (self.target / "runs").mkdir()
        (self.target / "runs" / "keep.md").write_text("x")
        vendor.apply(vendor.plan(FRAMEWORK, self.project))
        self.assertFalse((self.target / "install.py").exists())
        self.assertFalse((self.target / "tests").exists())
        self.assertTrue((self.target / "project" / "conventions.md").exists())
        self.assertTrue((self.target / "runs" / "keep.md").exists())

    def test_refuses_foreign_folder_downgrade_and_nested_target(self):
        self.target.mkdir()
        (self.target / "notes.txt").write_text("not ours")
        with self.assertRaises(vendor.VendorError):
            vendor.plan(FRAMEWORK, self.project)
        shutil.rmtree(self.target)
        vendor.apply(vendor.plan(FRAMEWORK, self.project))
        (self.target / "VERSION").write_text("999.0.0\n")
        with self.assertRaises(vendor.VendorError):
            vendor.plan(FRAMEWORK, self.project)
        self.assertEqual(vendor.plan(FRAMEWORK, self.project, force=True).mode, "upgrade")
        with self.assertRaises(vendor.VendorError):
            vendor.plan(FRAMEWORK, FRAMEWORK / "examples")
        with self.assertRaises(vendor.VendorError):
            vendor.plan(FRAMEWORK, Path(self.tmp.name) / "missing")

    def test_preseeded_project_folder_installs_without_overwriting(self):
        (self.target / "project").mkdir(parents=True)
        (self.target / "project" / "profile.yaml").write_text("version: 1\nproject: {name: Pre}\n")
        vplan = vendor.plan(FRAMEWORK, self.project)
        self.assertEqual(vplan.mode, "fresh")
        vendor.apply(vplan)
        self.assertIn("Pre", (self.target / "project" / "profile.yaml").read_text())
        self.assertTrue((self.target / "project" / "conventions.md").exists(), "missing template files are added")
        self.assertTrue((self.target / "orchestrator.py").exists())

    def test_empty_existing_folder_counts_as_fresh(self):
        self.target.mkdir()
        self.assertEqual(vendor.plan(FRAMEWORK, self.project).mode, "fresh")

    def test_same_folder_is_a_no_op(self):
        self.assertEqual(vendor.plan(FRAMEWORK, FRAMEWORK.parent).mode, "same")


class InstallDirTest(TempProject):
    def test_install_dir_vendors_slim_and_registers(self):
        self.assertEqual(quiet(install.main, ["--dir", str(self.project)]), 0)
        self.assertTrue((self.target / "orchestrator.py").exists())
        self.assertFalse((self.target / "install.py").exists())
        self.assertFalse((self.target / "skills").exists(), "claude/codex have native skills")
        self.assertTrue((self.project / ".claude" / "skills" / "omni-task" / "SKILL.md").exists())
        self.assertTrue((self.project / ".codex" / "agents" / "ba.toml").exists())
        self.assertIn("omni-team:begin", (self.project / "AGENTS.md").read_text())
        generated = (self.target / vendor.GENERATED_LIST).read_text().splitlines()
        self.assertIn(".claude/agents/code-reviewer.md", generated)
        self.assertNotIn("AGENTS.md", generated, "pointer files hold user text and stay in review scope")
        self.assertEqual(quiet(install.main, ["upgrade", "--dir", str(self.project)]), 0)

    def test_tools_without_native_skills_get_skills_vendored(self):
        self.assertEqual(quiet(install.main, ["--dir", str(self.project), "--tools", "agents-md"]), 0)
        self.assertTrue((self.target / "skills" / "pm" / "SKILL.md").exists())

    def test_dry_run_writes_nothing(self):
        self.assertEqual(quiet(install.main, ["init", "--dir", str(self.project), "--dry-run"]), 0)
        self.assertEqual(list(self.project.iterdir()), [])

    def test_conflict_aborts_before_copying_anything(self):
        mine = self.project / ".claude" / "agents" / "pm.md"
        mine.parent.mkdir(parents=True)
        mine.write_text("hand written")
        self.assertEqual(quiet(install.main, ["--dir", str(self.project)]), 2)
        self.assertFalse(self.target.exists())
        self.assertEqual(mine.read_text(), "hand written")

    def test_upgrade_requires_existing_copy_and_flags_are_exclusive(self):
        self.assertEqual(quiet(install.main, ["upgrade", "--dir", str(self.project)]), 2)
        self.assertEqual(quiet(install.main, ["--dir", str(self.project), "--project-root", str(self.project)]), 2)

    def test_uninstall_dir_keeps_vendored_folder(self):
        quiet(install.main, ["--dir", str(self.project)])
        self.assertEqual(quiet(install.main, ["uninstall", "--dir", str(self.project)]), 0)
        self.assertFalse((self.project / ".claude" / "agents" / "code-reviewer.md").exists())
        self.assertTrue((self.target / "orchestrator.py").exists())
        self.assertFalse((self.target / vendor.GENERATED_LIST).exists())

    @unittest.skipIf(yaml is None or shutil.which("git") is None, "needs PyYAML and git")
    def test_slim_copy_orchestrator_runs(self):
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.project, check=True)
        quiet(install.main, ["--dir", str(self.project)])
        (self.project / "app.py").write_text("".join(f"x{i} = {i}\n" for i in range(40)))
        done = subprocess.run([sys.executable, ".omni-team/orchestrator.py", "classify", "--task", "t"],
                              cwd=self.project, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("code-reviewer", done.stdout)
        self.assertNotIn(".claude/agents/", done.stdout, "generated adapters are not review scope")
        self.assertIn("app.py", done.stdout)


if __name__ == "__main__":
    unittest.main()
