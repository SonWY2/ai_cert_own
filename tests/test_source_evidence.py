"""Source provenance is reproducible and rejects altered stored records."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "modules"))
from evidence.provenance import verify_source_run, write_source_run  # noqa: E402
from static_scan.orchestrator import scan  # noqa: E402


class SourceEvidenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "-C", str(self.repo), "init", "-q"], check=True)
        (self.repo / "a.py").write_text("def f(): return 1\n")
        for args in (("add", "a.py"), ("-c", "user.email=a@b.c", "-c", "user.name=A",
                                          "commit", "-qm", "fixture")):
            subprocess.run(["git", "-C", str(self.repo), *args], check=True)
        self.output = Path(self.temp.name) / "artifacts"

    def test_replay_is_immutable_and_not_a_diagnosis(self) -> None:
        result = scan(self.repo, "HEAD")
        bundle = write_source_run(self.output, str(self.repo), result)
        first = verify_source_run(bundle)
        self.assertEqual(first["run"]["stage"], "source_scanned")
        self.assertNotIn("run_status", first["run"])
        self.assertEqual(first["evidence"][0]["source_sha256"], result["files"][0]["source_sha256"])
        self.assertEqual(bundle, write_source_run(self.output, str(self.repo), result))
        self.assertEqual(first, verify_source_run(bundle))
        altered = json.loads((bundle / "evidence.jsonl").read_text())
        altered["source_sha256"] = "0" * 64
        (bundle / "evidence.jsonl").write_text(json.dumps(altered) + "\n")
        with self.assertRaises(ValueError):
            verify_source_run(bundle)
        with self.assertRaises(FileExistsError):
            write_source_run(self.output, str(self.repo), result)


if __name__ == "__main__":
    unittest.main()
