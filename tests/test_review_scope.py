"""Review selection keeps omitted target and prior paths unknown."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from modules.evidence.provenance import verify_source_run, write_source_run  # noqa: E402
from modules.git_modes import plan_candidate, plan_main  # noqa: E402
from modules.git_modes.review_scope import plan_for_review, select_candidates  # noqa: E402
from modules.static_scan.orchestrator import scan  # noqa: E402


class ReviewScopeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("branch", "-M", "main")
        for name, source in {"a.py": "answer = 1\n", "b.py": "import a\nvalue = a.answer\n",
                             "c.py": "unrelated = True\n", "gone.py": "old = 1\n"}.items():
            (self.repo / name).write_text(source)
        self.commit()
        self.git("switch", "-qc", "candidate")
        (self.repo / "a.py").write_text("answer = 2\n")
        (self.repo / "gone.py").unlink()
        self.target = self.commit()
        bundle = write_source_run(Path(self.temp.name) / "bundles", "repo", scan(self.repo, self.target))
        self.verified = verify_source_run(bundle)

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def commit(self):
        self.git("add", "-A")
        self.git("-c", "user.email=a@b.c", "-c", "user.name=A", "commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    @staticmethod
    def candidate(path, line=1):
        return {"location": {"path": path, "line": line}, "hypothesis": "unverified"}


    def test_impact_observes_change_and_reverse_dependency_only(self):
        plan = plan_candidate(self.repo, "main", "candidate")
        candidates = [self.candidate(path) for path in ("a.py", "b.py", "c.py", "gone.py")]
        selected = select_candidates(self.verified, plan, candidates)
        self.assertEqual(selected["observed_candidates"], candidates[:2])
        self.assertEqual(selected["omitted_unknown_paths"], ["c.py", "gone.py"])
        self.assertIn("unresolved", selected["coverage"])

    def test_package_initializer_change_selects_dotted_importers(self):
        self.git("switch", "main")
        package = self.repo / "pkg"
        package.mkdir()
        (package / "__init__.py").write_text("flag = 1\n")
        (package / "child.py").write_text("value = 1\n")
        (self.repo / "consumer.py").write_text("import pkg.child\n")
        base = self.commit()
        self.git("switch", "-qc", "package-change")
        (package / "__init__.py").write_text("flag = 2\n")
        self.commit()

        plan = plan_candidate(self.repo, base, "package-change")
        self.assertIn("consumer.py", plan["observed_target_paths"])
        self.assertNotIn("consumer.py", plan["omitted_unknown_paths"])

    def test_full_and_skipped_do_not_resolve_deleted_or_unresolved(self):
        full = plan_candidate(self.repo, "main", "candidate", scope="full")
        result = select_candidates(self.verified, full, [self.candidate("c.py")])
        self.assertEqual(result["observed_candidates"], [self.candidate("c.py")])
        self.assertEqual(result["omitted_unknown_paths"], [])
        self.assertIn("unresolved", result["coverage"])
        with self.assertRaisesRegex(ValueError, "outside target"):
            select_candidates(self.verified, full, [self.candidate("gone.py")])
        skipped = plan_main(self.repo, "candidate", self.target)
        result = select_candidates(self.verified, skipped, [self.candidate("a.py")])
        self.assertEqual(result["observed_candidates"], [])
        self.assertEqual(result["omitted_unknown_paths"], ["a.py"])

    def test_rejects_mismatched_sha_bad_plans_and_locations(self):
        plan = plan_candidate(self.repo, "main", "candidate")
        with self.assertRaisesRegex(ValueError, "SHA"):
            select_candidates(self.verified, {**plan, "target_sha": "0" * 40}, [])
        for change in ({"mode": "main"}, {"scope": "full"}, {"skipped": True},
                       {"observed_target_paths": ["../a.py"]},
                       {"observed_target_paths": ["a.py", "a.py"]},
                       {"omitted_unknown_paths": []}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                select_candidates(self.verified, {**plan, **change}, [])
        for path, line in (("../a.py", 1), ("/tmp/a.py", 1), ("a.py", 0),
                           ("a.py", True), ("untracked.py", 1)):
            with self.subTest(path=path, line=line), self.assertRaises(ValueError):
                select_candidates(self.verified, plan, [self.candidate(path, line)])


if __name__ == "__main__":
    unittest.main()
