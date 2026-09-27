"""Context retrieval ranks exact symbols ahead of lexical and graph neighbors."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from modules.static_scan.orchestrator import graph  # noqa: E402
from modules.static_scan.retrieval import retrieve  # noqa: E402
from modules.static_scan.code_graph import SOURCE_BYTE_BUDGET  # noqa: E402


class RetrievalTest(unittest.TestCase):
    def test_exact_symbol_precedes_lexical_with_small_budget(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            def git(*args: str) -> None:
                subprocess.run(["git", "-C", directory, *args], check=True, capture_output=True)
            git("init", "-q")
            (repo / "a.py").write_text("def z(): return 1\ndef a():\n    special = 2\n")
            git("add", "a.py")
            git("-c", "user.email=a@b.c", "-c", "user.name=A", "commit", "-qm", "fixture")
            _, db = graph(repo, "HEAD")
            try:
                result = retrieve(db, symbol="z", changed_files=["a.py"], query="special", limit=1)
                self.assertEqual(result["nodes"][0]["name"], "z")
                self.assertTrue(result["truncated"])
                self.assertEqual(result["source_bytes"], len(result["nodes"][0]["source_slice"].encode("utf-8")))
                self.assertLessEqual(result["source_bytes"], SOURCE_BYTE_BUDGET)
                self.assertEqual(retrieve(db, changed_files=["a.py"], query="special", limit=1)["nodes"][0]["name"], "a")
                with self.assertRaises(ValueError):
                    retrieve(db, query="special")
            finally:
                db.close()

    def test_byte_budget_skips_large_exact_and_keeps_small_neighbor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            text = "def huge():\n    value = '界界界界界界界界界界'\n    small()\n\ndef small():\n    return 1\n"
            (repo / "a.py").write_text(text, encoding="utf-8")
            def git(*args: str) -> None:
                subprocess.run(["git", "-C", directory, *args], check=True, capture_output=True)
            git("init", "-q")
            git("add", "a.py")
            git("-c", "user.email=a@b.c", "-c", "user.name=A", "commit", "-qm", "fixture")
            _, db = graph(repo, "HEAD")
            try:
                full = retrieve(db, symbol="huge", source_byte_budget=1000)
                self.assertEqual(full["nodes"][0]["name"], "huge")
                self.assertFalse(full["truncated"])
                self.assertEqual(full["source_bytes"], sum(
                    len(node["source_slice"].encode("utf-8")) for node in full["nodes"]))
                small = retrieve(db, symbol="huge", source_byte_budget=27)
                self.assertTrue(small["truncated"])
                self.assertNotIn("huge", [node["name"] for node in small["nodes"]])
                self.assertIn("small", [node["name"] for node in small["nodes"]])
                self.assertEqual(small["edges"], [])
                self.assertEqual(small["source_bytes"], sum(
                    len(node["source_slice"].encode("utf-8")) for node in small["nodes"]))
                for node in small["nodes"]:
                    self.assertEqual(node["source_slice"], "".join(
                        text.splitlines(keepends=True)[node["line"] - 1:node["end_line"]]))
                for invalid in (0, -1, True, 2.5, "27"):
                    with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                        retrieve(db, symbol="huge", source_byte_budget=invalid)
            finally:
                db.close()


    def test_frozen_frame_maps_innermost_and_validates_physical_lines(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            text = ("class Outer:\r\n"
                    "    def method(self):\r\n"
                    "        def inner():\r\n"
                    "            return 42\r\n"
                    "        return inner()\r\n"
                    "\r\n"
                    "answer = 1\r\n")
            (repo / "a.py").write_bytes(text.encode())
            (repo / "broken.py").write_text("def nope(:\n")
            def git(*args: str) -> None:
                subprocess.run(["git", "-C", directory, *args], check=True, capture_output=True)
            git("init", "-q")
            git("add", "a.py", "broken.py")
            git("-c", "user.email=a@b.c", "-c", "user.name=A", "commit", "-qm", "fixture")
            _, db = graph(repo, "HEAD")
            try:
                inner = retrieve(db, frame=("a.py", 4), limit=1)
                self.assertEqual(inner["nodes"][0]["name"], "Outer.method.inner")
                self.assertEqual(inner["frame"]["node_id"], inner["nodes"][0]["id"])
                self.assertEqual(inner["frame"]["line"], 4)
                self.assertEqual(inner["frame"]["source_sha256"], inner["nodes"][0]["source_sha256"])
                self.assertEqual(retrieve(db, frame=("a.py", 5), limit=1)["nodes"][0]["name"],
                                 "Outer.method")
                self.assertEqual(retrieve(db, frame=("a.py", 7), limit=1)["frame"]["node_id"],
                                 "module:a.py")
                (repo / "a.py").write_text("raise RuntimeError('changed')\n")
                self.assertEqual(retrieve(db, frame=("a.py", 4), limit=1), inner)
                tiny = retrieve(db, frame=("a.py", 4), limit=1, source_byte_budget=1)
                self.assertEqual(tiny["frame"], inner["frame"])
                self.assertTrue(tiny["truncated"])
                self.assertEqual(tiny["nodes"], [])
                self.assertNotIn("frame", retrieve(db, symbol="Outer.method.inner"))
                for invalid in (("", 1), ("missing.py", 1), ("broken.py", 1),
                                ("a.py", 0), ("a.py", 8), ("a.py", 9), ("a.py", True),
                                ("../a.py", 4), ("/a.py", 4), ("a.py", "4")):
                    with self.subTest(frame=invalid), self.assertRaises(ValueError):
                        retrieve(db, frame=invalid)
            finally:
                db.close()

if __name__ == "__main__":
    unittest.main()
