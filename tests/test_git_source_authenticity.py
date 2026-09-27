"""Git-backed source provenance authenticates commit bytes and complete inventory."""

import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "modules"))
from evidence.authenticity import verify_git_source  # noqa: E402
from evidence.provenance import write_source_run  # noqa: E402
from static_scan.orchestrator import scan  # noqa: E402


class GitSourceAuthenticityTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        (self.repo / "a.py").write_bytes(b"answer = 42\n")
        (self.repo / "odd name\t.py").write_bytes(b"value = 1\n")
        self.git("add", "-A")
        self.git("-c", "user.email=a@b.c", "-c", "user.name=A", "commit", "-qm", "fixture")
        self.output = Path(self.temp.name) / "out"
        self.result = scan(self.repo, "HEAD")

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def bundle(self, result=None, repository=None):
        return write_source_run(self.output, str(repository or self.repo), result or self.result)

    def test_replace_ref_cannot_substitute_committed_source(self):
        oid = subprocess.run(["git", "-C", str(self.repo), "rev-parse", "HEAD:a.py"],
                             check=True, capture_output=True, text=True).stdout.strip()
        replacement = subprocess.run(["git", "-C", str(self.repo), "hash-object", "-w", "--stdin"],
                                     input=b"answer = 99\n", check=True, capture_output=True).stdout.decode().strip()
        self.git("replace", oid, replacement)

        scanned = scan(self.repo, "HEAD")
        original = next(item for item in self.result["files"] if item["path"] == "a.py")
        observed = next(item for item in scanned["files"] if item["path"] == "a.py")
        self.assertEqual(observed["source_sha256"], original["source_sha256"])
        self.assertEqual(verify_git_source(self.bundle(scanned))["inventory_count"], 2)

        forged = {**scanned, "files": [dict(item) for item in scanned["files"]]}
        next(item for item in forged["files"] if item["path"] == "a.py")["source_sha256"] = (
            hashlib.sha256(b"answer = 99\n").hexdigest())
        fake_bundle = write_source_run(self.output / "forged", str(self.repo), forged)
        with self.assertRaisesRegex(ValueError, "differs from Git commit"):
            verify_git_source(fake_bundle)

    def test_full_inventory_from_commit_not_worktree(self):
        bundle = self.bundle()
        self.assertEqual(verify_git_source(bundle)["inventory_count"], 2)
        (self.repo / "a.py").write_bytes(b"changed without commit\n")
        (self.repo / "odd name\t.py").unlink()
        self.assertEqual(verify_git_source(bundle)["inventory_count"], 2)

    def test_self_consistent_forged_hash_is_rejected(self):
        forged = {**self.result, "files": [dict(file) for file in self.result["files"]]}
        forged["files"][0]["source_sha256"] = "0" * 64
        bundle = self.bundle(forged)
        with self.assertRaises(ValueError):
            verify_git_source(bundle)

    def test_missing_or_extra_inventory_is_rejected(self):
        missing = {**self.result, "files": self.result["files"][:1]}
        with self.assertRaises(ValueError):
            verify_git_source(self.bundle(missing))
        extra = {**self.result, "files": [*self.result["files"],
                 {**self.result["files"][0], "path": "invented.py"}]}
        with self.assertRaises(ValueError):
            verify_git_source(self.bundle(extra))

    def test_bad_repository_and_symlink_exclusion(self):
        with self.assertRaises(ValueError):
            verify_git_source(self.bundle(repository=Path(self.temp.name) / "missing"))
        with self.assertRaises(ValueError):
            verify_git_source(self.bundle(repository=Path("relative-repository")))
        (self.repo / "link.py").symlink_to("a.py")
        self.git("add", "link.py")
        self.git("-c", "user.email=a@b.c", "-c", "user.name=A", "commit", "-qm", "symlink")
        result = scan(self.repo, "HEAD")
        self.assertEqual(verify_git_source(self.bundle(result))["inventory_count"], 2)
        forged = {**result, "files": [*result["files"], {**result["files"][0], "path": "link.py"}]}
        with self.assertRaises(ValueError):
            verify_git_source(self.bundle(forged))


if __name__ == "__main__":
    unittest.main()
