"""Provisional history requires authentic Git sources and immutable owner storage."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from modules.evidence.authenticity import verify_git_source  # noqa: E402
from modules.evidence.provenance import write_source_run  # noqa: E402
from modules.findings.admission import admit, priority_rows  # noqa: E402
from modules.findings.snapshots import load_previous, save_snapshot  # noqa: E402
from modules.static_scan.orchestrator import scan  # noqa: E402


class ProvisionalSnapshotTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.repo = root / "repo"
        self.repo.mkdir()
        self.owner = root / "owner"
        self.owner.mkdir(mode=0o700)
        self.path = self.owner / "snapshot.json"
        self.git("init", "-q")
        (self.repo / "worker.py").write_text("def work():\n    return 1\n")
        self.git("add", "worker.py")
        self.git("-c", "user.email=a@b.c", "-c", "user.name=A", "commit", "-qm", "first")
        self.bundle = write_source_run(root / "out", str(self.repo), scan(self.repo, "HEAD"))
        self.verified = verify_git_source(self.bundle)
        evidence = self.verified["evidence"][0]["id"]
        claim = {"root_symbol": "work", "mechanism": "stale return", "condition": "concurrent writes",
                 "impact": "older value", "trigger": "overlap", "taxonomy": "concurrency",
                 "severity": "High", "location": {"path": "worker.py", "line": 1},
                 "evidence_ids": [evidence], "next_action": {"action": "test concurrent calls",
                 "oracle": "latest value returned", "time_minutes": 8}}
        self.findings = admit(self.bundle, [claim])
        self.review = {"stage": "provisional_hypotheses", "findings": self.findings,
                       "priority_rows": priority_rows(self.findings), "scope": {"complete": True}}

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True, check=True)

    def test_round_trip_and_exclusive_creation(self):
        sealed = save_snapshot(self.review, self.verified, self.path)
        self.assertEqual(load_previous(self.path, self.bundle, str(self.repo)), sealed)
        self.assertEqual(sealed["stage"], "provisional_hypotheses")
        self.assertEqual(sealed["source_run_id"], self.verified["run"]["id"])
        before = self.path.read_bytes()
        with self.assertRaises(FileExistsError):
            save_snapshot(self.review, self.verified, self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_tampered_and_resealed_claims_fail(self):
        save_snapshot(self.review, self.verified, self.path)
        data = json.loads(self.path.read_bytes())
        data["findings"][0]["state"] = "confirmed"
        self.path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            load_previous(self.path, self.bundle, str(self.repo))

    def test_different_original_git_bundle_rejected(self):
        save_snapshot(self.review, self.verified, self.path)
        (self.repo / "worker.py").write_text("def work():\n    return 2\n")
        self.git("add", "worker.py")
        self.git("-c", "user.email=a@b.c", "-c", "user.name=A", "commit", "-qm", "second")
        other = write_source_run(Path(self.temp.name) / "out", str(self.repo), scan(self.repo, "HEAD"))
        with self.assertRaises(ValueError):
            load_previous(self.path, other, str(self.repo))

    def test_invalid_duplicate_and_forged_risk_rejected(self):
        for changed in (lambda r: r["findings"].append(dict(r["findings"][0])),
                        lambda r: r["priority_rows"].append(dict(r["priority_rows"][0])),
                        lambda r: r["priority_rows"][0].update(evidence_status="confirmed"),
                        lambda r: r.update(source_run_id="forged")):
            with self.subTest(changed=changed):
                review = json.loads(json.dumps(self.review))
                changed(review)
                with self.assertRaises(ValueError):
                    save_snapshot(review, self.verified, self.path)
                self.assertFalse(self.path.exists())

    def test_cli_seals_previous_source_and_rejects_altered_history(self):
        finding = self.findings[0]
        keys = ("root_symbol", "mechanism", "condition", "impact", "trigger",
                "taxonomy", "severity", "location", "evidence_ids", "next_action")
        candidates = self.owner / "candidates.json"
        candidates.write_text(json.dumps([{key: finding[key] for key in keys}]))
        command = [sys.executable, str(Path(__file__).resolve().parents[1] /
                                       "src" / "review_hypotheses.py"), str(self.bundle), str(candidates)]
        first = subprocess.run([*command, "--save-snapshot", str(self.path)],
                               check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(first.stdout)["snapshot_path"], str(self.path))
        previous = [*command, "--previous", str(self.path), "--previous-bundle", str(self.bundle)]
        second = subprocess.run(previous, check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(second.stdout)["priority_rows"][0]["change_status"], "unchanged")
        self.assertEqual(subprocess.run([*command, "--previous", str(self.path)],
                                        capture_output=True).returncode, 2)
        action = [sys.executable, str(Path(__file__).resolve().parents[1] / "src" / "record_action.py"),
                  str(self.bundle), str(candidates), str(self.owner), finding["id"], "verify",
                  "--previous", str(self.path), "--previous-bundle", str(self.bundle)]
        denied = subprocess.run(action, capture_output=True, text=True)
        self.assertEqual(denied.returncode, 2)
        self.assertIn("interactive terminal", denied.stderr)
        self.path.write_bytes(self.path.read_bytes() + b" ")
        rejected = subprocess.run(previous, capture_output=True, text=True)
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("snapshot", rejected.stderr)

    def test_previous_commit_remains_comparable_after_new_commit(self):
        save_snapshot(self.review, self.verified, self.path, source_bundle=self.bundle)
        (self.repo / "worker.py").write_text("def work():\n    return 2\n")
        self.git("add", "worker.py")
        self.git("-c", "user.email=a@b.c", "-c", "user.name=A", "commit", "-qm", "second")
        other = write_source_run(Path(self.temp.name) / "out", str(self.repo), scan(self.repo, "HEAD"))
        finding = self.findings[0]
        keys = ("root_symbol", "mechanism", "condition", "impact", "trigger",
                "taxonomy", "severity", "location", "next_action")
        claim = {key: finding[key] for key in keys}
        claim["evidence_ids"] = [verify_git_source(other)["evidence"][0]["id"]]
        candidates = self.owner / "second.json"
        candidates.write_text(json.dumps([claim]))
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parents[1] / "src" / "review_hypotheses.py"),
             str(other), str(candidates), "--previous", str(self.path),
             "--previous-bundle", str(self.bundle)],
            check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(result.stdout)["priority_rows"][0]["change_status"], "unchanged")

    def test_owner_boundary_and_read_only_source(self):
        with self.assertRaises(ValueError):
            save_snapshot(self.review, self.verified, self.repo / "snapshot.json")
        with self.assertRaises(ValueError):
            save_snapshot(self.review, self.verified, self.bundle / "snapshot.json",
                          source_bundle=self.bundle)
        invalid = json.loads(json.dumps(self.review))
        invalid["findings"][0]["location"]["line"] = 999
        with self.assertRaises(ValueError):
            save_snapshot(invalid, self.verified, self.path, source_bundle=self.bundle)
        save_snapshot(self.review, self.verified, self.path)
        os.chmod(self.bundle / "run.json", 0o444)
        os.chmod(self.bundle / "evidence.jsonl", 0o444)
        self.assertEqual(load_previous(self.path, self.bundle, str(self.repo))["findings"], self.findings)
        with self.assertRaises(ValueError):
            load_previous(self.path, self.bundle, "another repository")

    def test_fifo_snapshot_rejected_without_blocking(self):
        os.mkfifo(self.path, mode=0o600)
        script = (
            "import sys; from pathlib import Path; "
            "sys.path.insert(0, sys.argv[1]); "
            "from modules.findings.snapshots import load_previous; "
            "load_previous(*sys.argv[2:])"
        )
        result = subprocess.run(
            [sys.executable, "-c", script, str(Path(__file__).resolve().parents[1] / "src"),
             str(self.path), str(self.bundle), str(self.repo)],
            capture_output=True, text=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Snapshot must be an owner-only regular file", result.stderr)


if __name__ == "__main__":
    unittest.main()
