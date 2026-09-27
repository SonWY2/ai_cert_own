"""Candidate selection must preserve SHA topology and uncertain coverage."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from modules.git_modes import plan_candidate, plan_main  # noqa: E402


class GitModeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git("init", "-q")
        self.git("branch", "-M", "main")

    def git(self, *args: str) -> str:
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def commit(self) -> str:
        self.git("add", "-A")
        self.git("-c", "user.email=a@b.c", "-c", "user.name=A", "commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def test_impact_tracks_reverse_imports_deletion_and_merge_base(self) -> None:
        (self.repo / "a.py").write_text("answer = 1\n")
        (self.repo / "b.py").write_text("import a\nvalue = a.answer\n")
        (self.repo / "c.py").write_text("unrelated = True\n")
        (self.repo / "gone.py").write_text("obsolete = True\n")
        base = self.commit()
        self.git("switch", "-qc", "candidate")
        (self.repo / "a.py").write_text("answer = 2\n")
        (self.repo / "gone.py").unlink()
        target = self.commit()
        self.git("switch", "-q", "main")
        (self.repo / "main_only.py").write_text("main = True\n")
        self.commit()
        plan = plan_candidate(self.repo, "main", "candidate", scope="impact")
        self.assertEqual((plan["base_sha"], plan["target_sha"]), (base, target))
        self.assertEqual(plan["observed_target_paths"], ["a.py", "b.py"])
        self.assertIn("gone.py", plan["omitted_unknown_paths"])
        self.assertIn("c.py", plan["omitted_unknown_paths"])
        self.assertNotIn("main_only.py", plan["observed_target_paths"])

        command = subprocess.run(
            [sys.executable, str(ROOT / "src" / "plan_scan.py"), str(self.repo),
             "candidate", "main", "candidate", "--scope", "impact"],
            capture_output=True, text=True)
        self.assertEqual(command.returncode, 0, command.stderr)
        self.assertEqual(json.loads(command.stdout), plan)
        full = plan_candidate(self.repo, "main", "candidate", scope="full")
        self.assertEqual(full["observed_target_paths"], ["a.py", "b.py", "c.py"])
        self.assertEqual(plan_main(self.repo, "main", self.git("rev-parse", "main"))["skipped"], True)
        with self.assertRaisesRegex(ValueError, "immutable commit SHA"):
            plan_main(self.repo, "main", "main")

    def test_rename_keeps_old_dependents_in_partial_scope(self) -> None:
        (self.repo / "a.py").write_text("value = 1\n")
        (self.repo / "b.py").write_text("import a\n")
        (self.repo / "c.py").write_text("unrelated = 1\n")
        self.commit()
        self.git("switch", "-qc", "candidate")
        self.git("mv", "a.py", "renamed.py")
        self.commit()

        result = plan_candidate(self.repo, "main", "candidate", scope="impact")
        self.assertEqual(result["observed_target_paths"], ["b.py", "renamed.py"])
        self.assertIn("a.py", result["omitted_unknown_paths"])
        self.assertIn("c.py", result["omitted_unknown_paths"])

    def test_first_python_file_after_non_python_base_is_observable(self) -> None:
        (self.repo / "README").write_text("source comes later\n")
        self.commit()
        self.git("switch", "-qc", "candidate")
        (self.repo / "new.py").write_text("new = 1\n")
        self.commit()
        plan = plan_candidate(self.repo, "main", "candidate", scope="impact")
        self.assertEqual(plan["observed_target_paths"], ["new.py"])
        self.assertEqual(plan["omitted_unknown_paths"], [])


if __name__ == "__main__":
    unittest.main()
