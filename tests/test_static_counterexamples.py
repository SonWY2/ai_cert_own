"""Boundary probes use immutable source, resolved calls and conservative guards."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from modules.static_scan.orchestrator import graph  # noqa: E402
from modules.static_scan.retrieval import retrieve  # noqa: E402


class StaticCounterexampleTest(unittest.TestCase):
    def frozen(self, root, source):
        repo = root / "repo"
        repo.mkdir()
        (repo / "case.py").write_text(source)

        def git(*args):
            return subprocess.run(["git", "-C", str(repo), *args], check=True,
                                  capture_output=True, text=True).stdout.strip()

        git("init", "-q")
        git("add", "case.py")
        git("-c", "user.name=A", "-c", "user.email=a@b.c", "commit", "-qm", "case")
        _, db = graph(repo, git("rev-parse", "HEAD"))
        return repo, db

    def test_resolved_parameter_flow_proposes_zero_once_without_running_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source = ("def helper(value):\n"
                      "    return 1 / value\n\n"
                      "def entry(amount):\n"
                      "    first = helper(amount)\n"
                      "    return helper(amount)\n")
            repo, db = self.frozen(Path(directory), source)
            try:
                found = retrieve(db, symbol="entry")["static_counterexamples"]
                self.assertEqual(found, [{"kind": "zero_denominator", "status": "static_hypothesis",
                                          "path": "case.py", "entry_symbol": "entry", "entry_line": 4,
                                          "parameter": "amount", "input_value": 0,
                                          "call_line": 5, "sink_symbol": "helper", "sink_line": 2}])
                self.assertEqual(retrieve(db, symbol="helper")["static_counterexamples"][0]["sink_line"], 2)
                (repo / "case.py").write_text("raise RuntimeError('changed worktree')\n")
                self.assertEqual(retrieve(db, symbol="entry")["static_counterexamples"], found)
            finally:
                db.close()

    def test_guarded_caller_callee_and_conditional_expression_do_not_claim_zero_path(self):
        with tempfile.TemporaryDirectory() as directory:
            source = ("def guarded_helper(x):\n"
                      "    if x == 0:\n"
                      "        return 0\n"
                      "    return 1 / x\n\n"
                      "def plain_helper(x):\n"
                      "    return 1 / x\n\n"
                      "def guarded_caller(value):\n"
                      "    if value <= 0:\n"
                      "        return 0\n"
                      "    return plain_helper(value)\n\n"
                      "def guarded_by_condition(value):\n"
                      "    return 1 / value if value else 0\n\n"
                      "def changed_parameter(value):\n"
                      "    value = value or 1\n"
                      "    return plain_helper(value)\n\n"
                      "def callee_guarded(value):\n"
                      "    return guarded_helper(value)\n")
            _, db = self.frozen(Path(directory), source)
            try:
                for name in ("guarded_helper", "guarded_caller", "guarded_by_condition",
                             "changed_parameter", "callee_guarded"):
                    with self.subTest(name=name):
                        self.assertEqual(retrieve(db, symbol=name)["static_counterexamples"], [])
            finally:
                db.close()

    def test_literal_zero_is_visible_but_unresolved_local_call_is_not(self):
        with tempfile.TemporaryDirectory() as directory:
            source = ("def helper(value):\n"
                      "    return 10 % value\n\n"
                      "def direct():\n"
                      "    return helper(0)\n\n"
                      "def unknown():\n"
                      "    helper = lambda x: x\n"
                      "    return helper(0)\n")
            _, db = self.frozen(Path(directory), source)
            try:
                found = retrieve(db, symbol="direct")["static_counterexamples"]
                self.assertEqual(len(found), 1)
                self.assertEqual((found[0]["parameter"], found[0]["input_value"],
                                  found[0]["call_line"], found[0]["sink_line"]),
                                 (None, 0, 5, 2))
                self.assertEqual(retrieve(db, symbol="unknown")["static_counterexamples"], [])
            finally:
                db.close()

    def test_empty_collection_flows_to_index_and_guards_suppress_it(self):
        with tempfile.TemporaryDirectory() as directory:
            source = ("def first(values):\n"
                      "    return values[0]\n\n"
                      "def unsafe(data):\n"
                      "    return first(data)\n\n"
                      "def guarded(data):\n"
                      "    if not data:\n"
                      "        return None\n"
                      "    return first(data)\n\n"
                      "def safe_first(values):\n"
                      "    if values == []:\n"
                      "        return None\n"
                      "    return values[0]\n\n"
                      "def direct():\n"
                      "    return first([])\n\n"
                      "def conditional(values):\n"
                      "    return values[0] if values else None\n")
            _, db = self.frozen(Path(directory), source)
            try:
                found = retrieve(db, symbol="unsafe")["static_counterexamples"]
                self.assertEqual(len(found), 1)
                self.assertEqual((found[0]["kind"], found[0]["entry_symbol"],
                                  found[0]["sink_symbol"], found[0]["input_value"]),
                                 ("empty_index", "unsafe", "first", []))
                self.assertEqual(retrieve(db, symbol="direct")["static_counterexamples"][0]["parameter"], None)
                for name in ("guarded", "safe_first", "conditional"):
                    with self.subTest(name=name):
                        self.assertEqual(retrieve(db, symbol=name)["static_counterexamples"], [])
            finally:
                db.close()


if __name__ == "__main__":
    unittest.main()
