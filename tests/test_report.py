"""A readable report must not invent success or launder unverified log bytes."""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from modules.diagnosis.model import PERSPECTIVES, prompt_hash  # noqa: E402
from modules.diagnosis.plan import context_hash, prepare_analysis  # noqa: E402
from modules.evidence.authenticity import verify_git_source  # noqa: E402
from modules.evidence.final_bundle import verify_final_bundle, write_final_bundle  # noqa: E402
from modules.evidence.provenance import write_source_run  # noqa: E402
from modules.evidence.report import render_report  # noqa: E402
from modules.findings.admission import admit  # noqa: E402
from modules.run_policy import manifest_hash  # noqa: E402
from modules.static_scan.orchestrator import scan  # noqa: E402


class ReportTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        def git(*args):
            return subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                                  capture_output=True, text=True).stdout.strip()
        git("init", "-q")
        (self.repo / "case.py").write_text("def f(): return 1\n")
        git("add", "-A")
        git("-c", "user.name=A", "-c", "user.email=a@b.c", "commit", "-qm", "case")
        self.sha = git("rev-parse", "HEAD")
        self.source = write_source_run(self.root / "source", str(self.repo), scan(self.repo, self.sha))
        evidence = json.loads((self.source / "evidence.jsonl").read_text().splitlines()[0])
        self.candidate = {"root_symbol": "f", "mechanism": "wrong <script>|`code` result",
            "condition": "when called", "trigger": "f()", "impact": "returns 2",
            "taxonomy": "correctness", "severity": "High", "location": {"path": "case.py", "line": 1},
            "evidence_ids": [evidence["id"]], "perspective": "correctness",
            "next_action": {"action": "case.py:1 return 1; verify f()", "oracle": "expect 1; 2 falsifies",
                            "time_minutes": 3}}
        self.finding = admit(self.source, [self.candidate])[0]
        bounds = {"wall_seconds": 30, "cpu_seconds": 30, "memory_bytes": 1048576,
                  "tokens": 1000, "tool_seconds": 30}
        analysis, _, _ = prepare_analysis(verify_git_source(self.source), symbol="f")
        self.manifest = {"schema_version": "run-manifest-v3", "snapshot_sha": self.sha,
            "analysis": analysis,
            "image_digest": "sha256:" + "a" * 64, "tools": ["python"],
            "nodes": [{"id": "work", "tool": "python", "argv": ["python", "case.py"],
                       "cwd": "/workspace", "workload": "case.py", "trigger": "always"}],
            "limits": {**bounds, "per_node": {"work": bounds}},
            "network": {"dependency": False, "model": True, "workload": False},
            "writable_paths": ["/work/evidence"],
            "model": {"endpoint": "https://api.anthropic.com/v1/messages",
                      "name_version": "example-model", "prompt_sha256": prompt_hash("five"),
                      "transmitted_data": ["source", "context", "log", "evidence"]}}
        self.audit = [{"perspective": p, "status": "completed", "reason": None,
                       "tokens": 10, "request_sha256": "a" * 64,
                       "response_sha256": "b" * 64, "wall_seconds": 0.1,
                       "candidates": []} for p in PERSPECTIVES]

    def seal(self, findings, runtime=None):
        return write_final_bundle(self.source, findings, self.root / "final", manifest=self.manifest,
                                  model_audit=self.audit, runtime_trace_dir=runtime)

    def failed_runtime(self):
        output = self.root / "runtime"
        output.mkdir(mode=0o700)
        stderr = b"AssertionError: expected 1, got 2\n\x1b[31m````<script>|\n"
        (output / "work-0.stderr").write_bytes(stderr)
        (output / "work-0.stdout").write_bytes(b"")
        trace = {"schema_version": "approved-execution-v1", "snapshot_sha": self.sha,
                 "source_run_id": json.loads((self.source / "run.json").read_text())["id"],
                 "manifest_sha256": manifest_hash(self.manifest), "runtime_attested": False,
                 "runtime_provenance": "caller_declared_unattested",
                 "limitations": "A container trace is not an oracle or confirmed finding.",
                 "nodes": [{"node_id": "work", "status": "failed", "reason": "nonzero_exit",
                            "trial": 0, "exit_code": 1, "wall_seconds": 0.2,
                            "command_argv": ["python", "case.py"],
                            "image_digest": self.manifest["image_digest"],
                            "manifest_sha256": manifest_hash(self.manifest),
                            "stdout_path": "work-0.stdout", "stderr_path": "work-0.stderr",
                            "stdout_sha256": hashlib.sha256(b"").hexdigest(),
                            "stderr_sha256": hashlib.sha256(stderr).hexdigest()}]}
        (output / "execution.json").write_text(json.dumps(trace, sort_keys=True,
                                                    separators=(",", ":")) + "\n")
        return output

    def test_unexecuted_empty_review_is_not_safety_proof(self):
        bundle = self.seal([])
        markdown = render_report(self.source, bundle)
        self.assertIn("분석 완료·후보 없음, 결함 부재를 보장하지 않음", markdown)
        self.assertIn("실행하지 않음", markdown)
        self.assertNotIn("명령 비정상 종료", markdown)
        self.assertEqual(len(list(bundle.iterdir())), 5)
        self.audit[1] = {**self.audit[1], "status": "failed", "reason": "output_json_invalid"}
        partial = self.seal([])
        self.assertIn("분석 불완전", render_report(self.source, partial))

    def test_failed_command_remains_visible_without_model_candidate(self):
        runtime = self.failed_runtime()
        bundle = self.seal([], runtime)
        markdown = render_report(self.source, bundle, runtime_trace_dir=runtime)
        self.assertEqual(verify_final_bundle(bundle, self.source, runtime_trace_dir=runtime)
                         ["report"]["analysis_status"], "incomplete")
        self.assertIn("명령 비정상 종료", markdown)
        self.assertIn("AssertionError: expected 1, got 2", markdown)
        self.assertIn("work\\-0\\.stderr", markdown)
        self.assertNotIn("\x1b", markdown)
        self.assertIn("확증 0건", markdown)
        (runtime / "work-0.stderr").write_bytes(b"forged\n")
        with self.assertRaises(ValueError):
            render_report(self.source, bundle, runtime_trace_dir=runtime)

    def test_finding_details_escape_markup_and_untrusted_text(self):
        self.audit[1]["candidates"] = [{"index": 0, "candidate": self.candidate,
            "candidate_sha256": context_hash(self.candidate), "status": "accepted",
            "reason": None, "finding_id": self.finding["id"]}]
        bundle = self.seal([self.finding])
        markdown = render_report(self.source, bundle)
        self.assertIn("case\\.py:1", markdown)
        self.assertIn("case\\.py:1 return 1", markdown)
        self.assertIn("&lt;script&gt;", markdown)
        self.assertNotIn("<script>", markdown)
        self.assertIn("수정·검증 제안", markdown)
        self.assertIn("기대 결과·반증 조건", markdown)
        self.assertEqual(len(list(bundle.iterdir())), 5)

    def test_mixed_rows_remain_incomplete_and_scalar_rejections_render_safely(self):
        self.audit[1]["candidates"] = [{
            "index": 0, "candidate": self.candidate,
            "candidate_sha256": context_hash(self.candidate), "status": "accepted",
            "reason": None, "finding_id": self.finding["id"]}]
        for index, raw in enumerate((None, "<script>alert(1)</script>\x1b[31m",
                                      {"location": {"path": "elsewhere.py", "line": 99}}), 1):
            self.audit[1]["candidates"].append({
                "index": index, "candidate": raw, "candidate_sha256": context_hash(raw),
                "status": "unverified", "reason": "candidate_schema_invalid",
                "finding_id": None})
        bundle = self.seal([self.finding])
        markdown = render_report(self.source, bundle)
        self.assertIn("분석 불완전", markdown)
        self.assertIn("접수 1 · 미검증 3", markdown)
        self.assertIn("candidate\\_schema\\_invalid", markdown)
        self.assertIn("원래 행 1", markdown)
        self.assertIn("null", markdown)
        self.assertIn("&lt;script&gt;", markdown)
        self.assertNotIn("<script>", markdown)
        self.assertNotIn("\x1b", markdown)
        sealed = verify_final_bundle(bundle, self.source)
        self.assertEqual([row["id"] for row in sealed["findings"]], [self.finding["id"]])
        self.assertEqual(sealed["report"]["confirmed_count"], 0)


if __name__ == "__main__":
    unittest.main()
