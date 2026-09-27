"""CLI source-stage output must respect immutable snapshots and write boundaries."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from modules.evidence.provenance import verify_source_run  # noqa: E402


class ScanSourcesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        self.output = Path(self.temp.name) / "evidence"
        self.git("init", "-q")
        (self.repo / "a.py").write_text("def ready(): return 1\n")
        self.git("add", "a.py")
        self.git("-c", "user.email=test@example.org", "-c", "user.name=Test", "commit", "-qm", "fixture")
        self.sha = self.git("rev-parse", "HEAD")

    def git(self, *args: str) -> str:
        return subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True,
                              check=True, text=True).stdout.strip()

    def cli(self, output: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(ROOT / "src" / "scan_sources.py"),
                               str(self.repo), "HEAD", str(output), *args], capture_output=True, text=True)

    def test_non_utf8_git_path_rejected_without_partial_evidence(self) -> None:
        path = os.path.join(os.fsencode(self.repo), b"\xff.py")
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(b"value = 1\n")
        self.git("add", "-A")
        self.git("-c", "user.email=test@example.org", "-c", "user.name=Test", "commit", "-qm", "raw path")

        response = self.cli(self.output)
        self.assertEqual(response.returncode, 2, response.stderr)
        self.assertIn("UTF-8", response.stderr)
        self.assertFalse(self.output.exists())

    def test_source_bundle_and_graph_context(self) -> None:
        (self.repo / "a.py").write_text("raise RuntimeError('working tree must not run')\n")
        process = self.cli(self.output, "--node", "module:a.py", "--hops", "2")
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual(result["commit"], self.sha)
        self.assertEqual(result["stage"], "source_scanned")
        self.assertIn("def ready()", str(result["context"]))
        bundle = Path(result["source_bundle"])
        records = verify_source_run(bundle)
        self.assertEqual(records["run"]["commit"], self.sha)
        self.assertNotIn("working tree must not run", str(result))
        self.assertEqual(self.cli(self.output).returncode, 0)

    def test_search_uses_only_frozen_source(self) -> None:
        (self.repo / "a.py").write_text("def changed(): return 2\n")
        response = self.cli(self.output, "--symbol", "ready", "--changed-file", "a.py",
                            "--query", "def ready")
        self.assertEqual(response.returncode, 0, response.stderr)
        nodes = json.loads(response.stdout)["context"]["nodes"]
        self.assertEqual(nodes[0]["name"], "ready")
        self.assertNotIn("changed", str(nodes))


    def test_static_probes_report_frozen_call_boundary_without_running_source(self) -> None:
        (self.repo / "a.py").write_text(
            "def helper(value):\n    return 1 / value\n\n"
            "def entry(amount):\n    return helper(amount)\n\n"
            "def safe(value):\n    if value == 0:\n        return 0\n    return 1 / value\n")
        self.git("add", "a.py")
        self.git("-c", "user.email=test@example.org", "-c", "user.name=Test",
                 "commit", "-qm", "boundary")
        frozen = self.git("rev-parse", "HEAD")
        (self.repo / "a.py").write_text("raise RuntimeError('working tree execution')\n")
        response = self.cli(self.output, "--symbol", "entry", "--static-probes")
        self.assertEqual(response.returncode, 0, response.stderr)
        result = json.loads(response.stdout)
        self.assertEqual(result["commit"], frozen)
        self.assertNotIn("context", result)
        self.assertNotIn("working tree execution", response.stdout)
        self.assertEqual([(item["input_value"], item["call_line"], item["sink_line"])
                          for item in result["static_counterexamples"]], [(0, 5, 2)])
        self.assertEqual(verify_source_run(Path(result["source_bundle"]))["run"]["commit"], frozen)
        readable = self.cli(self.output, "--symbol", "entry", "--static-probes", "--readable")
        self.assertEqual(readable.returncode, 0, readable.stderr)
        self.assertIn(f"Git: {frozen}", readable.stdout)
        self.assertIn("후보: 1건", readable.stdout)
        self.assertIn("a.py", readable.stdout)
        self.assertIn("경계 입력: \"amount\"=0 · 호출 5행", readable.stdout)
        self.assertIn("helper:2", readable.stdout.replace('"', ""))
        self.assertIn("결함 확증 아님", readable.stdout)
        self.assertNotIn("working tree execution", readable.stdout)
        clean = self.cli(self.output, "--symbol", "safe", "--static-probes", "--readable")
        self.assertEqual(clean.returncode, 0, clean.stderr)
        self.assertIn("후보: 0건 (0건도 안전 증명이 아님)", clean.stdout)
        self.assertNotIn("0으로 나눌 가능성", clean.stdout)
        unreadable = self.cli(Path(self.temp.name) / "unreadable", "--readable")
        self.assertEqual(unreadable.returncode, 2)
        self.assertFalse((Path(self.temp.name) / "unreadable").exists())
        denied = self.cli(Path(self.temp.name) / "denied", "--static-probes")
        self.assertEqual(denied.returncode, 2)
        self.assertFalse((Path(self.temp.name) / "denied").exists())

    def test_frame_selects_nested_frozen_function_and_records_source_hash(self) -> None:
        frozen = (
            "def outer():\n"
            "    def inner():\n"
            "        return 17\n"
            "    return inner()\n"
        )
        (self.repo / "a.py").write_text(frozen)
        self.git("add", "a.py")
        self.git("-c", "user.email=test@example.org", "-c", "user.name=Test",
                 "commit", "-qm", "nested fixture")
        commit = self.git("rev-parse", "HEAD")
        (self.repo / "a.py").write_text("raise RuntimeError('uncommitted code')\n")
        response = self.cli(self.output, "--frame", "a.py:3")
        self.assertEqual(response.returncode, 0, response.stderr)
        result = json.loads(response.stdout)
        self.assertEqual(result["commit"], commit)
        frame = result["context"]["frame"]
        self.assertEqual(frame["path"], "a.py")
        self.assertEqual(frame["line"], 3)
        self.assertEqual(frame["source_sha256"], hashlib.sha256(frozen.encode()).hexdigest())
        selected = next(node for node in result["context"]["nodes"] if node["id"] == frame["node_id"])
        self.assertEqual(selected["name"], "outer.inner")
        self.assertIn("return 17", selected["source_slice"])
        self.assertNotIn("uncommitted", str(result))
        records = verify_source_run(Path(result["source_bundle"]))
        self.assertEqual(records["run"]["commit"], commit)

    def test_frame_rejects_invalid_format_unmapped_lines_and_node_hops(self) -> None:
        for options in (
            ("--frame", "a.py"),
            ("--frame", "a.py:0"),
            ("--frame", "a.py:nan"),
            ("--frame", "missing.py:1"),
            ("--frame", "a.py:2"),
            ("--frame", "a.py:1", "--node", "module:a.py"),
            ("--frame", "a.py:1", "--hops", "2"),
        ):
            with self.subTest(options=options):
                response = self.cli(self.output, *options)
                self.assertEqual(response.returncode, 2, response.stderr)
                self.assertFalse(self.output.exists())

    def test_context_budget_keeps_complete_small_neighbor_from_git(self) -> None:
        (self.repo / "a.py").write_text(
            "def huge():\n    x = '" + "é" * 1000 + "'\n\n"
            "def small():\n    return 2\n")
        self.git("add", "a.py")
        self.git("-c", "user.email=test@example.org", "-c", "user.name=Test",
                 "commit", "-qm", "large function")
        response = self.cli(self.output, "--symbol", "huge", "--source-byte-budget", "60")
        self.assertEqual(response.returncode, 0, response.stderr)
        context = json.loads(response.stdout)["context"]
        self.assertTrue(context["truncated"])
        self.assertLessEqual(context["source_bytes"], 60)
        self.assertEqual([node["name"] for node in context["nodes"]], ["small"])
        self.assertIn("return 2", context["nodes"][0]["source_slice"])
        self.assertEqual(context["nodes"][0]["end_line"], 5)
        self.assertEqual(self.cli(self.output, "--source-byte-budget", "60").returncode, 2)
        scan = subprocess.run(
            [sys.executable, str(ROOT / "src" / "modules" / "static_scan" / "orchestrator.py"),
             str(self.repo), "HEAD", "--node", "function:a.py:huge:1",
             "--hops", "2", "--source-byte-budget", "60"], capture_output=True, text=True)
        self.assertEqual(scan.returncode, 0, scan.stderr)
        self.assertEqual([node["name"] for node in json.loads(scan.stdout)["context"]["nodes"]],
                         ["small"])

    def test_rejects_writes_inside_source_and_unknown_node(self) -> None:
        denied = self.cli(self.repo / "artifacts")
        self.assertEqual(denied.returncode, 2)
        self.assertFalse((self.repo / "artifacts").exists())
        missing = self.cli(self.output, "--node", "module:missing.py")
        self.assertEqual(missing.returncode, 2)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
