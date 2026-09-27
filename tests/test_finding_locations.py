"""Location proofs bind physical lines to verified immutable Git blobs."""

import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from modules.evidence.authenticity import verify_git_source  # noqa: E402
from modules.evidence.provenance import write_source_run  # noqa: E402
from modules.findings.locations import validate_locations  # noqa: E402
from modules.static_scan.orchestrator import scan  # noqa: E402


class FindingLocationsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.contents = {
            "ordinary.py": b"first = 1\nlast = 2",
            "crlf.py": b"first = 1\r\nlast = 2\r\n",
            "cr.py": b"first = 1\rlast = 2\r",
            "latin.py": b"# coding: latin-1\r\nname = '\xe9'\r\n",
            "control.py": b"first = 1\vlast = 2\f",
            "empty.py": b"",
        }
        for path, content in self.contents.items():
            (self.repo / path).write_bytes(content)
        self.git("add", "-A")
        self.git("-c", "user.email=a@b.c", "-c", "user.name=A", "commit", "-qm", "fixture")
        bundle = write_source_run(Path(self.temp.name) / "out", str(self.repo), scan(self.repo, "HEAD"))
        self.verified = verify_git_source(bundle)
        self.ids = {record["path"]: record["id"] for record in self.verified["evidence"]}

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)

    def candidate(self, path="ordinary.py", line=1, end_line=None):
        location = {"path": path, "line": line}
        if end_line is not None:
            location["end_line"] = end_line
        return {"location": location, "evidence_ids": [self.ids[path]]}

    def test_first_last_and_inclusive_source_slice(self):
        candidates = [self.candidate(line=1), self.candidate(line=2), self.candidate(end_line=2)]
        proofs = validate_locations(self.verified, candidates)
        self.assertEqual(len(proofs), 3)
        self.assertEqual([(proof["line"], proof["end_line"]) for proof in proofs],
                         [(1, 1), (2, 2), (1, 2)])
        for proof, content in zip(proofs, (b"first = 1\n", b"last = 2", self.contents["ordinary.py"])):
            self.assertEqual(proof["source_slice_sha256"], hashlib.sha256(content).hexdigest())
            self.assertEqual(proof["evidence_ids"], [self.ids["ordinary.py"]])

    def test_rejects_out_of_range_empty_file_and_foreign_evidence(self):
        invalid = [self.candidate(line=3), self.candidate(end_line=3),
                   self.candidate("empty.py"), self.candidate(line=0),
                   self.candidate(line=True), self.candidate(line=2, end_line=1),
                   {"location": {"path": "missing.py", "line": 1},
                    "evidence_ids": [self.ids["ordinary.py"]]},
                   {"location": {"path": "ordinary.py", "line": 1},
                    "evidence_ids": [self.ids["cr.py"]]},
                   {"location": {"path": "ordinary.py", "line": 1},
                    "evidence_ids": ["fabricated"]}]
        for candidate in invalid:
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                validate_locations(self.verified, [candidate])

    def test_worktree_changes_cannot_change_proof(self):
        candidate = self.candidate(line=2)
        expected = validate_locations(self.verified, [candidate])
        (self.repo / "ordinary.py").write_bytes(b"completely different\n")
        (self.repo / "cr.py").unlink()
        self.assertEqual(validate_locations(self.verified, [candidate]), expected)

    def test_physical_lines_with_newlines_and_encoding_cookie(self):
        candidates = [self.candidate(path, 2) for path in ("crlf.py", "cr.py", "latin.py")]
        proofs = validate_locations(self.verified, candidates)
        for proof, content in zip(proofs, (b"last = 2\r\n", b"last = 2\r", b"name = '\xe9'\r\n")):
            self.assertEqual(proof["source_slice_sha256"], hashlib.sha256(content).hexdigest())
        for path in ("crlf.py", "cr.py", "latin.py"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                validate_locations(self.verified, [self.candidate(path, 3)])


    def test_control_characters_do_not_create_physical_lines(self):
        proof = validate_locations(self.verified, [self.candidate("control.py")])[0]
        self.assertEqual(proof["source_slice_sha256"],
                         hashlib.sha256(self.contents["control.py"]).hexdigest())
        with self.assertRaises(ValueError):
            validate_locations(self.verified, [self.candidate("control.py", 2)])

if __name__ == "__main__":
    unittest.main()
