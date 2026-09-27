"""Source-only reviews require real Git bytes and preserve partial-scope unknowns."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from modules.evidence.provenance import verify_source_run, write_source_run  # noqa: E402
from modules.findings import admit  # noqa: E402
from modules.static_scan.orchestrator import scan  # noqa: E402


class ReviewGitCliTest(unittest.TestCase):
    def test_partial_review_omits_unobserved_and_rejects_forged_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            def git(*args):
                return subprocess.run(["git", "-C", str(repo), *args], check=True,
                                      capture_output=True, text=True).stdout.strip()
            git("init", "-q")
            git("branch", "-M", "main")
            for name, text in {"a.py": "answer = 1\n", "b.py": "import a\nvalue = a.answer\n",
                               "c.py": "unrelated = 1\n", "gone.py": "old = 1\n"}.items():
                (repo / name).write_text(text)
            git("add", "-A")
            git("-c", "user.email=a@b.c", "-c", "user.name=A", "commit", "-qm", "base")
            git("switch", "-qc", "candidate")
            (repo / "a.py").write_text("answer = 2\n")
            (repo / "gone.py").unlink()
            git("add", "-A")
            git("-c", "user.email=a@b.c", "-c", "user.name=A", "commit", "-qm", "target")
            bundle = write_source_run(root / "out", str(repo), scan(repo, "candidate"))
            evidence = {row["path"]: row["id"] for row in verify_source_run(bundle)["evidence"]}
            def claim(path):
                return {"root_symbol": path, "mechanism": "possibly stale value",
                        "condition": "concurrent request", "impact": "old response",
                        "trigger": "shared state update", "taxonomy": "concurrency", "severity": "High",
                        "location": {"path": path, "line": 1}, "evidence_ids": [evidence[path]],
                        "next_action": {"action": "exercise shared state", "oracle": "response equals final value",
                                        "time_minutes": 5}}
            candidates = root / "candidates.json"
            candidates.write_text(json.dumps([claim(path) for path in ("a.py", "b.py", "c.py")]))
            cli = [sys.executable, str(ROOT / "src" / "review_hypotheses.py"), str(bundle), str(candidates)]
            scoped = ["--main-ref", "main", "--candidate-ref", "candidate", "--scope", "impact"]
            response = subprocess.run([*cli, *scoped], capture_output=True, text=True)
            self.assertEqual(response.returncode, 0, response.stderr)
            result = json.loads(response.stdout)
            self.assertEqual({row["location"]["path"] for row in result["findings"]}, {"a.py", "b.py"})
            self.assertEqual(result["scope"]["omitted_unknown_paths"], ["c.py", "gone.py"])
            self.assertTrue(all(row["state"] == "deferred" for row in result["findings"]))
            full = subprocess.run([*cli, "--main-ref", "main", "--candidate-ref", "candidate",
                                   "--scope", "full"], check=True, capture_output=True, text=True)
            self.assertEqual(len(json.loads(full.stdout)["findings"]), 3)
            self.assertEqual(subprocess.run([*cli, "--main-ref", "main"], capture_output=True).returncode, 2)
            owner = root / "owner"
            owner.mkdir(mode=0o700)
            outside_id = admit(bundle, [claim("c.py")])[0]["id"]
            action = [sys.executable, str(ROOT / "src" / "record_action.py"), str(bundle),
                      str(candidates), str(owner), outside_id, "verify", *scoped]
            denied = subprocess.run(action, capture_output=True, text=True)
            self.assertEqual(denied.returncode, 2)
            self.assertIn("does not belong", denied.stderr)
            self.assertFalse(list(owner.iterdir()))
            base = write_source_run(root / "out", str(repo), scan(repo, "main"))
            base_evidence = {row["path"]: row["id"] for row in verify_source_run(base)["evidence"]}
            base_claim = claim("a.py")
            base_claim["evidence_ids"] = [base_evidence["a.py"]]
            base_candidates = root / "base-candidates.json"
            base_candidates.write_text(json.dumps([base_claim]))
            baseline = owner / "base.json"
            base_cli = [sys.executable, str(ROOT / "src" / "review_hypotheses.py"),
                        str(base), str(base_candidates)]
            created = subprocess.run([*base_cli, "--main-ref", "main",
                                      "--save-snapshot", str(baseline)],
                                     capture_output=True, text=True)
            self.assertEqual(created.returncode, 0, created.stderr)
            previous = ["--previous", str(baseline), "--previous-bundle", str(base)]
            reviewed = subprocess.run([*cli, *scoped, *previous], capture_output=True, text=True)
            self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
            by_path = {row["location"]["path"]: row["change_status"] for row in
                       json.loads(reviewed.stdout)["priority_rows"]}
            self.assertEqual(by_path, {"a.py": "unchanged", "b.py": "unknown"})
            skipped = subprocess.run([*base_cli, "--main-ref", "main", *previous],
                                     capture_output=True, text=True)
            self.assertEqual(skipped.returncode, 2)
            self.assertIn("Already reviewed", skipped.stderr)
            target_snapshot = owner / "target.json"
            saved = subprocess.run([*cli, *scoped, "--save-snapshot", str(target_snapshot)],
                                   capture_output=True, text=True)
            self.assertEqual(saved.returncode, 0, saved.stderr)
            wrong_base = ["--previous", str(target_snapshot), "--previous-bundle", str(bundle)]
            rejected_base = subprocess.run([*cli, *scoped, *wrong_base],
                                           capture_output=True, text=True)
            self.assertEqual(rejected_base.returncode, 2)
            self.assertIn("planned base SHA", rejected_base.stderr)
            wrong_action = subprocess.run([*action, *wrong_base], capture_output=True, text=True)
            self.assertEqual(wrong_action.returncode, 2)
            self.assertIn("planned base SHA", wrong_action.stderr)
            unrelated = subprocess.run([*base_cli, *wrong_base],
                                       capture_output=True, text=True)
            self.assertEqual(unrelated.returncode, 2)
            self.assertIn("not an ancestor", unrelated.stderr)
            bad_claim = claim("a.py")
            bad_claim["location"]["line"] = 999
            candidates.write_text(json.dumps([bad_claim]))
            wrong_line = subprocess.run([*cli, *scoped], capture_output=True, text=True)
            self.assertEqual(wrong_line.returncode, 2)
            self.assertIn("line span", wrong_line.stderr)
            candidates.write_text(json.dumps([claim(path) for path in ("a.py", "b.py", "c.py")]))
            forged = scan(repo, "candidate")
            forged["files"][0]["source_sha256"] = "0" * 64
            fake = write_source_run(root / "out", str(repo), forged)
            rejected = subprocess.run([sys.executable, str(ROOT / "src" / "review_hypotheses.py"),
                                       str(fake), str(candidates)], capture_output=True, text=True)
            self.assertEqual(rejected.returncode, 2)
            self.assertIn("Git commit", rejected.stderr)


if __name__ == "__main__":
    unittest.main()
