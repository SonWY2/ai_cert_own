"""Offline syntactic review units from frozen Git blobs, not target imports."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "modules"))
from static_scan.code_graph import context  # noqa: E402
from static_scan.orchestrator import graph  # noqa: E402
from static_scan.review_units import extract_review_units  # noqa: E402


class ReviewUnitsTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name)
        self.git("init", "-q")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def frozen(self, source):
        for path, content in (source if isinstance(source, dict) else {"a.py": source}).items():
            (self.repo / path).write_text(content, encoding="utf-8")
        self.git("add", "-A")
        self.git("-c", "user.email=test@example.org", "-c", "user.name=Test",
                 "commit", "-qm", "fixture")
        _, db = graph(self.repo, self.git("rev-parse", "HEAD"))
        self.addCleanup(db.close)
        (self.repo / "a.py").write_text("raise RuntimeError('must not read worktree')\n")
        return db

    def test_same_line_calls_have_stable_distinct_utf8_byte_offsets_and_revision_ids(self):
        source = "def chosen():\n    return 한글() + 한글()\n"
        db = self.frozen(source)
        view = context(db, "function:a.py:chosen:1", hops=0)
        first = extract_review_units(db, view, level="outline", selected_symbol="chosen")
        second = extract_review_units(db, view, level="outline", selected_symbol="chosen")
        calls = [item for item in first["delivered"] if item["kind"] == "call"]
        self.assertEqual(first, second)
        self.assertEqual(len(calls), 2)
        self.assertEqual(len({item["id"] for item in calls}), 2)
        self.assertEqual([item["col"] for item in calls], [11, 22])
        self.assertEqual([item["syntax"] for item in calls], ["한글()", "한글()"])
        self.assertEqual(set(first["extracted_ids"]), {item["id"] for item in first["delivered"]})
        self.assertEqual(first["source_bytes"], len(json.dumps(first, ensure_ascii=False,
                               separators=(",", ":")).encode("utf-8")))

    def test_identical_functions_in_different_files_have_distinct_ids(self):
        source = "def duplicate():\n    return call()\n"
        db = self.frozen({"a.py": source, "b.py": source})
        first = extract_review_units(db, context(db, "module:a.py", hops=0), level="outline")
        second = extract_review_units(db, context(db, "module:b.py", hops=0), level="outline")
        first_call = next(item for item in first["delivered"] if item["kind"] == "call")
        second_call = next(item for item in second["delivered"] if item["kind"] == "call")
        self.assertEqual(first_call["syntax"], second_call["syntax"])
        self.assertEqual(first_call["line"], second_call["line"])
        self.assertNotEqual(first_call["id"], second_call["id"])

    def test_selected_function_excludes_nested_body_and_conditional_scope_is_separate(self):
        db = self.frozen("def outer():\n    def nested():\n        return helper()\n"
                         "    return outer_call()\nif ready:\n    def conditional():\n"
                         "        return conditional_call()\n")
        outer = extract_review_units(db, context(db, "function:a.py:outer:1", hops=0),
                                     level="outline", selected_symbol="outer")
        self.assertEqual([item["syntax"] for item in outer["delivered"]
                          if item["kind"] == "call"], ["outer_call()"])
        self.assertIn("nested_definition", {row["reason"] for row in outer["omitted"]})
        view = context(db, "module:a.py", hops=0)
        full = extract_review_units(db, view, level="outline", selected_symbol="conditional")
        calls = [item for item in full["delivered"] if item["kind"] == "call"]
        self.assertEqual({item["symbol"] for item in calls},
                         {"outer.nested", "outer", "conditional"})
        self.assertEqual(calls[0]["symbol"], "conditional")

    def test_loop_cards_preserve_empty_guarded_and_shadowed_syntax_without_path_claims(self):
        db = self.frozen("def progress(chunk, end):\n"
                         "    start = 0\n"
                         "    while start < end:\n"
                         "        if not chunk:\n"
                         "            break\n"
                         "        start += len(chunk)\n"
                         "    if retry:\n"
                         "        start = 0\n"
                         "    while True:\n"
                         "        pass\n")
        view = context(db, "function:a.py:progress:1", hops=0)
        result = extract_review_units(db, view, level="cards")
        cards = [item for item in result["delivered"] if item["kind"] == "loop_card"]
        self.assertEqual([item["condition"] for item in cards], ["start < end", "True"])
        relations = cards[0]["relations"]
        self.assertEqual([(item["kind"], item["line"], item["syntax"]) for item in relations],
                         [("assignment", 2, "start = 0"),
                          ("nested_guard", 4, "not chunk"),
                          ("nested_break", 5, "break"),
                          ("increment", 6, "start += len(chunk)"),
                          ("assignment", 8, "start = 0")])
        self.assertIn("assignment_path_and_shadowing", cards[0]["unknown"])
        self.assertEqual(cards[1]["relations"], [])
        self.assertIn("condition_value_and_progress", cards[1]["unknown"])

    def test_truncated_context_omissions_provenance_and_entire_payload_budget(self):
        db = self.frozen("def first():\n    return visible()\n"
                         "def second():\n    return secret()\n")
        view = context(db, "function:a.py:first:1", hops=0)
        result = extract_review_units(db, view, level="outline")
        self.assertTrue(all("secret" not in json.dumps(item) for item in result["delivered"]))
        full = context(db, "module:a.py", hops=0)
        bounded = extract_review_units(db, full, level="outline", max_bytes=380,
                                       selected_symbol="second")
        self.assertLessEqual(bounded["source_bytes"], 380)
        self.assertEqual(bounded["source_bytes"], len(json.dumps(bounded, ensure_ascii=False,
                               separators=(",", ":")).encode("utf-8")))
        self.assertGreater(bounded["unlisted_count"] + len(bounded["omitted"]), 0)
        self.assertEqual(bounded["delivered"][0]["symbol"], "second")
        tampered = {**view, "nodes": [{**view["nodes"][0], "source_slice": "spoof"}]}
        with self.assertRaises(ValueError):
            extract_review_units(db, tampered, level="outline")

    def test_partial_approved_slice_omits_whole_nodes_and_hidden_relations(self):
        source = ("def partial(end):\n"
                  "    start = 0\n"
                  "    while start < end:\n"
                  "        start += 1\n"
                  "        reveal_secret()\n")
        db = self.frozen(source)
        full = context(db, "function:a.py:partial:1", hops=0)
        fragment = {**full["nodes"][0], "slice_start_line": 1, "slice_end_line": 4,
                    "source_slice": "".join(source.splitlines(keepends=True)[:4])}
        scoped = extract_review_units(db, {**full, "nodes": [fragment]}, level="cards")
        self.assertNotIn("reveal_secret", json.dumps(scoped))
        self.assertEqual(scoped["delivered"], [])
        self.assertEqual(set(row["reason"] for row in scoped["omitted"]),
                         {"outside_transmitted_source_slice"})
        self.assertGreater(len(scoped["extracted_ids"]), 0)

    def test_try_finally_header_is_a_syntactic_location_not_a_call_edge(self):
        db = self.frozen("def cleanup():\n"
                         "    try:\n"
                         "        send()\n"
                         "    finally:\n"
                         "        close()\n")
        view = context(db, "function:a.py:cleanup:1", hops=0)
        units = extract_review_units(db, view, level="outline")["delivered"]
        attempt = next(item for item in units if item["kind"] == "try")
        self.assertEqual(attempt["finally"],
                         {"line": 4, "col": 4, "end_line": 4, "end_col": 12,
                          "syntax": "finally:"})
        self.assertEqual([(item["kind"], item["syntax"]) for item in units
                          if item["kind"] == "call"], [("call", "send()"), ("call", "close()")])



if __name__ == "__main__":
    unittest.main()
