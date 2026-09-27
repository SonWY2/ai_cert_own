"""Consumer-visible snapshot isolation and source coverage checks."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "modules"))
from static_scan.orchestrator import scan  # noqa: E402


class SnapshotScanTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git("init", "-q")

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(self.repo), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def commit(self) -> str:
        self.git("add", "-A")
        self.git("-c", "user.email=test@example.org", "-c", "user.name=Test",
                 "commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def test_reads_only_frozen_regular_python_blobs(self) -> None:
        (self.repo / "src.py").write_text("def f():\n    raise RuntimeError('not executed')\n")
        (self.repo / "link.py").symlink_to("/etc/passwd")
        sha = self.commit()
        (self.repo / "src.py").write_text("raise RuntimeError('working tree')\n")
        (self.repo / "extra.py").write_text("raise RuntimeError('untracked')\n")

        result = scan(self.repo, "HEAD")
        self.assertEqual(result["commit"], sha)
        self.assertEqual([file["path"] for file in result["files"]], ["src.py"])
        self.assertEqual(result["files"][0]["symbols"][0]["name"], "f")
        self.assertEqual(scan(self.repo, sha), result)

    def test_parse_error_and_pep263_source_are_visible(self) -> None:
        (self.repo / "latin.py").write_bytes(b'# coding: latin-1\nx = "caf\xe9"\n')
        (self.repo / "bad.py").write_text("def broken(:\n")
        self.commit()
        records = {file["path"]: file for file in scan(self.repo, "HEAD")["files"]}
        self.assertIn("parse_error", records["bad.py"])
        self.assertNotIn("symbols", records["bad.py"])
        self.assertNotIn("parse_error", records["latin.py"])

    def test_rejects_revision_without_python_source(self) -> None:
        (self.repo / "README").write_text("documentation")
        self.commit()
        with self.assertRaisesRegex(ValueError, "No tracked Python source"):
            scan(self.repo, "HEAD")


if __name__ == "__main__":
    unittest.main()
