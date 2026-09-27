"""Graph edges must not turn unresolved names into asserted dependencies."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "modules"))
from static_scan.orchestrator import graph  # noqa: E402
from static_scan.code_graph import context  # noqa: E402


class CodeGraphTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git("init", "-q")

    def git(self, *args: str) -> str:
        return subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True,
                              check=True, text=True).stdout.strip()

    def freeze(self) -> str:
        self.git("add", "-A")
        self.git("-c", "user.email=test@example.org", "-c", "user.name=Test", "commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def test_resolved_edges_and_source_slice_survive_worktree_changes(self) -> None:
        (self.repo / "a.py").write_text(
            "import b\nclass Base: pass\nclass Child(Base): pass\n"
            "def helper(): return 1\ndef caller():\n    return helper()\n")
        (self.repo / "b.py").write_text("answer = 42\n")
        sha = self.freeze()
        (self.repo / "a.py").write_text("raise RuntimeError('worktree should not be read')\n")
        result, db = graph(self.repo, sha)
        try:
            self.assertEqual(result["commit"], sha)
            edges = db.execute("SELECT kind,state FROM edges WHERE state='resolved'").fetchall()
            self.assertTrue({("defines", "resolved"), ("imports", "resolved"),
                             ("inherits", "resolved"), ("calls", "resolved")} <= set(edges))
            view = context(db, "module:a.py", hops=2)
            self.assertIn("def helper(): return 1", "\n".join(n.get("source_slice", "") for n in view["nodes"]))
            self.assertNotIn("worktree should not be read", str(view))
        finally:
            db.close()

    def test_unambiguous_local_class_import_keeps_dynamic_call_unknown(self) -> None:
        package = self.repo / "pkg"
        package.mkdir()
        (package / "__init__.py").write_text("")
        (package / "models.py").write_text(
            "class Base:\n    def create(self): return 1\n")
        (package / "dynamic.py").write_text("class User: pass\nUser = object\n")
        (package / "api.py").write_text(
            "from .models import Base\n"
            "from .dynamic import User\n"
            "def register(manager: Base): return manager.create()\n")
        sha = self.freeze()
        (package / "models.py").write_text("raise RuntimeError('not frozen')\n")
        _, db = graph(self.repo, sha)
        try:
            imports = list(db.execute(
                "SELECT reference,target,state FROM edges WHERE source='module:pkg/api.py' "
                "AND kind='imports' ORDER BY reference"))
            self.assertIn(("pkg.models.Base", "class:pkg/models.py:Base:1", "resolved"),
                          imports)
            self.assertIn(("pkg.dynamic.User", "", "unknown"), imports)
            self.assertEqual(list(db.execute(
                "SELECT reference,state FROM edges WHERE source='function:pkg/api.py:register:3' "
                "AND kind='calls'")), [("manager.create", "unknown")])
            view = context(db, "module:pkg/api.py", hops=1)
            self.assertIn("class:pkg/models.py:Base:1",
                          {node["id"] for node in view["nodes"]})
            self.assertNotIn("not frozen", str(view))
        finally:
            db.close()

    def test_method_and_nested_calls_are_attributed_without_false_resolution(self) -> None:
        (self.repo / "a.py").write_text(
            "def helper():\n    return 1\n"
            "class Worker:\n"
            "    def work(self):\n        return helper() + self.other()\n"
            "    async def check(self):\n        return await self.fetch()\n"
            "def outer():\n"
            "    def inner():\n        return helper()\n"
            "    return inner()\n")
        sha = self.freeze()
        (self.repo / "a.py").write_text("raise RuntimeError('working tree should not run')\n")
        _, db = graph(self.repo, sha)
        try:
            rows = list(db.execute(
                "SELECT source,reference,state FROM edges WHERE kind='calls' ORDER BY source,reference"))
            self.assertEqual(rows, [
                ("function:a.py:Worker.check:6", "self.fetch", "unknown"),
                ("function:a.py:Worker.work:4", "helper", "unknown"),
                ("function:a.py:Worker.work:4", "self.other", "unknown"),
                ("function:a.py:outer.inner:9", "helper", "unknown"),
                ("function:a.py:outer:8", "inner", "unknown")])
            method = context(db, "function:a.py:Worker.work:4", hops=0)
            self.assertEqual([row["reference"] for row in method["edges"]],
                             ["helper", "self.other"])
            self.assertEqual({row["state"] for row in method["edges"]}, {"unknown"})
            self.assertNotIn("function:a.py:helper:1",
                             [node["id"] for node in context(db, "function:a.py:Worker.work:4", hops=1)["nodes"]])
            self.assertNotIn("working tree should not run", str(method))
        finally:
            db.close()

    def test_conditional_definitions_have_locations_but_not_resolved_calls(self) -> None:
        (self.repo / "a.py").write_text(
            "def helper(): return 1\n"
            "if ready:\n"
            "    def conditional(): return helper()\n"
            "else:\n"
            "    class Conditional:\n"
            "        def method(self): return helper()\n"
            "try:\n"
            "    def guarded(): return helper()\n"
            "except Exception:\n"
            "    def recovered(): return helper()\n"
            "finally:\n"
            "    def cleanup(): return helper()\n"
            "match mode:\n"
            "    case _:\n"
            "        def matched(): return helper()\n"
            "def caller(): return conditional()\n"
            "if ready:\n"
            "    def helper(): return 2\n"
            "def invoke(): return helper()\n")
        sha = self.freeze()
        _, db = graph(self.repo, sha)
        try:
            for name, line in (("conditional", 3), ("Conditional.method", 6),
                               ("guarded", 8), ("recovered", 10), ("cleanup", 12),
                               ("matched", 15)):
                with self.subTest(name=name):
                    identity = f"function:a.py:{name}:{line}"
                    self.assertEqual(db.execute("SELECT id FROM nodes WHERE id=?",
                                                (identity,)).fetchone(), (identity,))
                    self.assertEqual(db.execute(
                        "SELECT state FROM edges WHERE source=? AND kind='calls'",
                        (identity,)).fetchall(), [("unknown",)])
            self.assertEqual(db.execute(
                "SELECT state FROM edges WHERE source='function:a.py:caller:16' AND kind='calls'"
            ).fetchall(), [("unknown",)])
            self.assertEqual(db.execute(
                "SELECT state FROM edges WHERE source='function:a.py:invoke:19' AND kind='calls'"
            ).fetchall(), [("unknown",)])
        finally:
            db.close()

    def test_source_slices_use_physical_newlines_not_control_characters(self) -> None:
        source = "# banner\fmetadata\r\ndef chosen():\r\n    return 1\r\n"
        (self.repo / "a.py").write_bytes(source.encode())
        sha = self.freeze()
        _, db = graph(self.repo, sha)
        try:
            selected = context(db, "function:a.py:chosen:2", hops=0)["nodes"][0]
            self.assertEqual(selected["source_slice"], "def chosen():\r\n    return 1\r\n")
            self.assertEqual((selected["line"], selected["end_line"]), (2, 3))
            module = context(db, "module:a.py", hops=0)["nodes"][0]
            self.assertEqual(module["source_slice"], source)
            self.assertEqual(module["end_line"], 3)
        finally:
            db.close()

    def test_byte_budget_omits_large_anchor_but_keeps_complete_neighbor(self) -> None:
        source = "def small():\n    return 'é'\n\n" + "padding = '" + "x" * 200 + "'\n"
        (self.repo / "a.py").write_text(source, encoding="utf-8")
        sha = self.freeze()
        (self.repo / "a.py").write_text("raise RuntimeError('do not execute or read worktree')\n")
        _, db = graph(self.repo, sha)
        try:
            small = "def small():\n    return 'é'\n"
            budget = len(small.encode("utf-8"))
            view = context(db, "module:a.py", hops=1, source_byte_budget=budget)
            self.assertEqual([node["id"] for node in view["nodes"]], ["function:a.py:small:1"])
            self.assertEqual(view["nodes"][0]["source_slice"], small)
            self.assertEqual((view["nodes"][0]["line"], view["nodes"][0]["end_line"]), (1, 2))
            self.assertEqual(view["source_bytes"], budget)
            self.assertTrue(view["truncated"])
            self.assertEqual(view["edges"], [])
            self.assertEqual(context(db, "module:a.py", hops=0, source_byte_budget=budget)["nodes"], [])
            self.assertEqual(context(db, "module:a.py", hops=1,
                                     source_byte_budget=budget - 1)["nodes"], [])
            for invalid in (True, 0, -1, 1.5):
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    context(db, "module:a.py", source_byte_budget=invalid)
        finally:
            db.close()

    def test_wildcard_import_cannot_resolve_shadowed_local_function(self) -> None:
        (self.repo / "a.py").write_text(
            "def target(): return 'local'\n"
            "from b import *\n"
            "def caller(): return target()\n")
        (self.repo / "b.py").write_text(
            "__all__ = ['target']\ndef target(): return 'imported'\n")
        sha = self.freeze()
        _, db = graph(self.repo, sha)
        try:
            view = context(db, "function:a.py:caller:3", hops=1)
            self.assertNotIn("function:a.py:target:1", [node["id"] for node in view["nodes"]])
            self.assertEqual([edge for edge in view["edges"] if edge["kind"] == "calls"],
                             [{"source": "function:a.py:caller:3", "target": "", "kind": "calls",
                               "state": "unknown", "reference": "target"}])
        finally:
            db.close()

    def test_global_write_makes_top_level_call_target_unknown(self) -> None:
        (self.repo / "a.py").write_text(
            "def target(): return 'original'\n"
            "def replace():\n"
            "    global target\n"
            "    target = lambda: 'replaced'\n"
            "def caller(): return target()\n")
        sha = self.freeze()
        _, db = graph(self.repo, sha)
        try:
            edge = db.execute(
                "SELECT target,state FROM edges WHERE source='function:a.py:caller:5' "
                "AND kind='calls' AND reference='target'").fetchone()
            self.assertEqual(edge, ("", "unknown"))
        finally:
            db.close()

    def test_decorators_are_in_function_and_class_source_slices(self) -> None:
        (self.repo / "a.py").write_text(
            "@cache(\n    size=2,\n)\n"
            "def work(): return 1\n"
            "@register\n"
            "class Service: pass\n")
        sha = self.freeze()
        _, db = graph(self.repo, sha)
        try:
            for identity, start, end, source in (
                ("function:a.py:work:4", 1, 4, "@cache(\n    size=2,\n)\ndef work(): return 1\n"),
                ("class:a.py:Service:6", 5, 6, "@register\nclass Service: pass\n"),
            ):
                with self.subTest(identity=identity):
                    node = context(db, identity, hops=0)["nodes"][0]
                    self.assertEqual((node["line"], node["end_line"]), (start, end))
                    self.assertEqual(node["source_slice"], source)
        finally:
            db.close()

    def test_unresolved_dynamic_and_shadowed_names_remain_unknown(self) -> None:
        (self.repo / "a.py").write_text(
            "import missing\ndef target(): pass\n"
            "def caller(target):\n    target()\n    obj.run()\n")
        sha = self.freeze()
        _, db = graph(self.repo, sha)
        try:
            self.assertEqual(db.execute("SELECT count(*) FROM edges WHERE kind='calls' AND state='resolved'").fetchone()[0], 0)
            self.assertGreaterEqual(db.execute("SELECT count(*) FROM edges WHERE state='unknown'").fetchone()[0], 3)
            view = context(db, "module:a.py", hops=2)
            self.assertTrue(any(e["state"] == "unknown" for e in view["edges"]))
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
