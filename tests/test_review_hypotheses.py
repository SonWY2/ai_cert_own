"""The CLI accepts cited hypotheses without calling them confirmed findings."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from modules.evidence.provenance import verify_source_run, write_source_run  # noqa: E402
from modules.findings.actions import append_action  # noqa: E402
from modules.static_scan.orchestrator import scan  # noqa: E402


class ReviewHypothesesTest(unittest.TestCase):
    def test_real_source_bundle_yields_only_provisional_risk(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            def git(*args):
                subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True)
            git("init", "-q")
            (repo / "worker.py").write_text("def work():\n    return 1\n")
            git("add", "worker.py")
            git("-c", "user.email=a@b.c", "-c", "user.name=A", "commit", "-qm", "fixture")
            bundle = write_source_run(root / "out", str(repo), scan(repo, "HEAD"))
            evidence_id = verify_source_run(bundle)["evidence"][0]["id"]
            claim = {"root_symbol": "work", "mechanism": "result may be stale",
                     "condition": "concurrent write", "impact": "caller may see old value",
                     "trigger": "simultaneous requests", "taxonomy": "concurrency", "severity": "High",
                     "location": {"path": "worker.py", "line": 1}, "evidence_ids": [evidence_id],
                     "next_action": {"action": "exercise concurrent writes", "oracle": "returned version matches final version",
                                     "time_minutes": 7}}
            candidates = root / "candidates.json"
            candidates.write_text(json.dumps([claim, dict(claim, perspective="correctness")]))
            command = [sys.executable, str(ROOT / "src" / "review_hypotheses.py"), str(bundle), str(candidates)]
            completed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(completed.stdout)
            self.assertEqual(result["stage"], "provisional_hypotheses")
            self.assertEqual(len(result["findings"]), 1)
            self.assertEqual(result["priority_rows"][0]["evidence_status"], "deferred")
            self.assertIsNone(result["priority_rows"][0]["user_action"])
            owner = root / "owner"
            owner.mkdir(mode=0o700)
            action_cli = [sys.executable, str(ROOT / "src" / "record_action.py"),
                          str(bundle), str(candidates), str(owner),
                          result["findings"][0]["id"], "verify"]
            self.assertEqual(subprocess.run(action_cli, capture_output=True).returncode, 2)
            self.assertFalse(list(owner.iterdir()))
            append_action(bundle, result["findings"], result["findings"][0]["id"],
                          "verify", owner, True)
            with_actions = subprocess.run([*command, "--actions", str(owner)],
                                          capture_output=True, text=True)
            self.assertEqual(with_actions.returncode, 0, with_actions.stderr)
            row = json.loads(with_actions.stdout)["priority_rows"][0]
            self.assertEqual((row["user_action"], row["evidence_status"]), ("verify", "deferred"))
            claim["evidence_ids"] = ["forged"]
            candidates.write_text(json.dumps([claim]))
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)


if __name__ == "__main__":
    unittest.main()
