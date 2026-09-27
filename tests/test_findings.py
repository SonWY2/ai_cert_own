"""Source-only claims remain deferred; priority and identity cannot hide uncertainty."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from modules.evidence.provenance import verify_source_run, write_source_run  # noqa: E402
from modules.findings import admit, compare, priority_rows  # noqa: E402
from modules.static_scan.orchestrator import scan  # noqa: E402


class FindingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        def git(*args):
            subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)
        git("init", "-q")
        (self.repo / "worker.py").write_text("def run():\n    return 1\n")
        git("add", "worker.py")
        git("-c", "user.email=a@b.c", "-c", "user.name=A", "commit", "-qm", "fixture")
        self.bundle = write_source_run(Path(self.temp.name) / "out", str(self.repo), scan(self.repo, "HEAD"))
        self.evidence_id = verify_source_run(self.bundle)["evidence"][0]["id"]

    def candidate(self, symbol="run", severity="High", minutes=8, perspective="concurrency"):
        return {"root_symbol": symbol, "mechanism": "child task is not awaited",
                "condition": "timeout after spawning a child", "impact": "orphan task may consume resources",
                "trigger": "request timeout", "taxonomy": "concurrency", "severity": severity,
                "location": {"path": "worker.py", "line": 1}, "evidence_ids": [self.evidence_id],
                "perspective": perspective,
                "next_action": {"action": "run a cancellation test", "oracle": "pending child count is zero",
                                "time_minutes": minutes}}

    def test_deduplicates_and_preserves_deferred_source_boundary(self):
        a = self.candidate()
        b = self.candidate(perspective="correctness")
        findings = admit(self.bundle, [b, a])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["state"], "deferred")
        self.assertEqual(set(findings[0]["perspectives"]), {"concurrency", "correctness"})
        self.assertEqual(admit(self.bundle, [a], previous=findings)[0]["id"], findings[0]["id"])
        a["evidence_ids"] = ["forged"]
        with self.assertRaises(ValueError):
            admit(self.bundle, [a])
        conflicting = self.candidate(perspective="correctness")
        conflicting["next_action"]["oracle"] = "result is stable"
        with self.assertRaises(ValueError):
            admit(self.bundle, [self.candidate(), conflicting])

    def test_identity_mismatch_is_unknown_and_priority_uses_change_then_time(self):
        one = admit(self.bundle, [self.candidate("run", minutes=20), self.candidate("other", minutes=5)])
        by_symbol = {row["root_symbol"]: row for row in one}
        changed = [dict(by_symbol["run"], root_symbol="different")]
        self.assertEqual(compare([by_symbol["run"]], changed, complete=True)[0]["status"], "unknown")
        statuses = {by_symbol["run"]["id"]: "worsened", by_symbol["other"]["id"]: "new"}
        rows = priority_rows(one, changes=statuses, actions={by_symbol["run"]["id"]: "verify"})
        self.assertEqual(rows[0]["id"], by_symbol["run"]["id"])
        self.assertEqual(rows[0]["user_action"], "verify")
        self.assertEqual(rows[0]["next_action"]["time_minutes"], 20)
        self.assertEqual(rows[0]["evidence_status"], "deferred")
        with self.assertRaises(ValueError):
            priority_rows(one, actions={by_symbol["run"]["id"]: "investigate"})


if __name__ == "__main__":
    unittest.main()
