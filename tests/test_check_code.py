"""The noninteractive entry point reports verified diagnosis and errors."""

import contextlib
import hashlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import check_code  # noqa: E402
from modules.evidence.authenticity import verify_git_source  # noqa: E402
from modules.evidence.final_bundle import verify_final_bundle  # noqa: E402
import diagnose_approved  # noqa: E402


class CheckCodeTest(unittest.TestCase):
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
        (self.repo / "case.py").write_text("def check(): return 1\n")
        git("add", "-A")
        git("-c", "user.name=A", "-c", "user.email=a@b.c", "commit", "-qm", "case")
        self.sha = git("rev-parse", "HEAD")
        bounds = {"wall_seconds": 30, "cpu_seconds": 30, "memory_bytes": 1048576,
                  "tokens": 25000, "tool_seconds": 30}
        self.template = {"schema_version": "run-manifest-v3", "snapshot_sha": "0" * 40,
            "analysis": None,
            "image_digest": "sha256:" + "a" * 64, "tools": [], "nodes": [],
            "limits": {**bounds, "per_node": {}},
            "network": {"dependency": False, "model": True, "workload": False},
            "writable_paths": ["/work/evidence"],
            "model": {"endpoint": "https://api.anthropic.com/v1/messages", "name_version": "pinned-model",
                      "prompt_sha256": "0" * 64, "transmitted_data": ["source", "context"]}}
        self.saved = self.root / "saved.json"
        self.saved.write_text(json.dumps(self.template))

    def call(self, output, *, symbol=None):
        args = ["check_code.py", str(self.repo), "--manifest", str(self.saved),
                "--output", str(output)]
        if symbol:
            args += ["--symbol", symbol]
        stdout = io.StringIO()
        with patch.object(sys, "argv", args), contextlib.redirect_stdout(stdout):
            code = check_code.main()
        return code, stdout.getvalue()


    def test_noninteractive_one_command_generates_verified_final_report(self):
        output = self.root / "result"
        real_child = check_code._child
        def child(name, *args):
            if name != "diagnose_approved.py":
                self.assertEqual(name, "scan_sources.py")
                return real_child(name, *args)
            text = io.StringIO()
            with patch.object(sys, "argv", [name, *args]), contextlib.redirect_stdout(text):
                code = diagnose_approved.main()
            return subprocess.CompletedProcess(args, code, text.getvalue(), "")
        reply = {"usage": {"input_tokens": 40, "output_tokens": 4},
                 "stop_reason": "end_turn", "content": [{"type": "text", "text": '{"candidates": []}'}]}
        with patch.object(sys.stdin, "isatty", return_value=False), patch.object(
                check_code, "_child", side_effect=child), patch(
                "modules.diagnosis.model._request", return_value=reply) as request:
            code, printed = self.call(output)
        self.assertEqual(request.call_count, 5)
        self.assertEqual(code, 0)
        self.assertIn("[3/3] 분석 완료", printed)
        self.assertIn("후보 0건", printed)
        self.assertNotIn("{\"stage\"", printed)
        self.assertIn("결함 부재를 보장하지 않음", (output / "report.md").read_text())
        self.assertEqual(json.loads(self.saved.read_text()), self.template)
        self.assertEqual(json.loads((output / "manifest.json").read_text())["snapshot_sha"], self.sha)
        self.assertEqual({p.name for p in output.iterdir()},
                         {"source", "manifest.json", "final", "responses", "result.json", "report.md"})
        result = json.loads((output / "result.json").read_text())
        self.assertEqual(len(result["response_artifacts"]), 5)
        source_bundle = next((output / "source" / "runs").iterdir())
        sealed = verify_final_bundle(Path(result["final_source_only_bundle"]), source_bundle)
        self.assertEqual(sealed["report"]["analysis_status"], "completed")
        self.assertIn("모델 응답 원자료 5건", printed)
        audits = [row for group in result["perspectives"] for row in group["perspectives"]]
        self.assertEqual(len(audits), len(result["response_artifacts"]))
        for artifact, audit in zip(result["response_artifacts"], audits):
            self.assertEqual(artifact["response_sha256"], audit["response_sha256"])
            self.assertEqual(hashlib.sha256(Path(artifact["path"]).read_bytes()).hexdigest(),
                             artifact["response_sha256"])
        for path in output.rglob("*"):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700 if path.is_dir() else 0o600)

    def test_incomplete_provider_preserves_result_and_report_with_exit_three(self):
        output = self.root / "incomplete"
        real_child = check_code._child

        def child(name, *args):
            if name != "diagnose_approved.py":
                return real_child(name, *args)
            text = io.StringIO()
            with patch.object(sys, "argv", [name, *args]), contextlib.redirect_stdout(text):
                code = diagnose_approved.main()
            return subprocess.CompletedProcess(args, code, text.getvalue(), "")

        response = {"usage": {"input_tokens": 40, "output_tokens": 4},
                    "stop_reason": "incomplete", "content": []}
        with patch.object(check_code, "_child", side_effect=child), patch(
                "modules.diagnosis.model._request", return_value=response):
            code, printed = self.call(output, symbol="check")
        self.assertEqual(code, 3)
        self.assertIn("분석 불완전", printed)
        self.assertIn("response\\_incomplete", (output / "report.md").read_text())
        self.assertEqual(json.loads((output / "result.json").read_text())["perspectives"][0]["tokens"], 44)
        saved = json.loads((output / "result.json").read_text())
        self.assertEqual(len(saved["response_artifacts"]), 5)
        self.assertEqual([item["response_sha256"] for item in saved["response_artifacts"]],
                         [item["response_sha256"] for item in saved["perspectives"]])
        self.assertIn("모델 응답 원자료 5건", printed)
        self.assertEqual(len(list((output / "final" / "runs").iterdir())), 1)

    def test_mixed_candidates_preserve_valid_role_and_render_null_safely(self):
        output = self.root / "unverified"
        real_child = check_code._child

        def child(name, *args):
            if name != "diagnose_approved.py":
                return real_child(name, *args)
            text = io.StringIO()
            with patch.object(sys, "argv", [name, *args]), contextlib.redirect_stdout(text):
                code = diagnose_approved.main()
            return subprocess.CompletedProcess(args, code, text.getvalue(), "")

        def respond(endpoint, payload, timeout):
            perspective = json.loads(payload["messages"][0]["content"])["perspective"]
            source = next((output / "source" / "runs").iterdir())
            evidence_id = verify_git_source(source)["evidence"][0]["id"]
            claim = {"root_symbol": "check", "mechanism": "returns <script>alert(1)</script> | wrong value",
                     "condition": "input differs", "impact": "incorrect output",
                     "trigger": "invoke check", "taxonomy": perspective, "severity": "Low",
                     "location": {"path": "case.py", "line": 1}, "evidence_ids": [evidence_id],
                     "next_action": {"action": "check return", "time_minutes": 1}}
            valid = {**claim, "mechanism": "constant result ignores required input",
                     "taxonomy": "performance", "perspective": "spoofed",
                     "next_action": {"action": "compare expected return", "oracle": "equals one",
                                     "time_minutes": 1}}
            return {"usage": {"input_tokens": 40, "output_tokens": 4},
                    "stop_reason": "end_turn",
                    "content": [{"type": "text", "text": json.dumps({
                        "candidates": [claim, None, valid] if perspective == "tests" else []})}]}

        with patch.object(check_code, "_child", side_effect=child), patch(
                "modules.diagnosis.model._request", side_effect=respond):
            code, printed = self.call(output, symbol="check")
        self.assertEqual(code, 3)
        self.assertIn("분석 불완전", printed)
        report = (output / "report.md").read_text()
        self.assertIn(r"case\.py:1", report)
        self.assertIn("&lt;script&gt;", report)
        self.assertIn(r"candidate\_schema\_invalid", report)
        self.assertNotIn("<script>", report)
        result = json.loads((output / "result.json").read_text())
        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(result["findings"][0]["perspectives"], ["tests"])
        self.assertEqual(result["findings"][0]["taxonomy"], "performance")
        self.assertEqual(result["findings"][0]["state"], "deferred")
        rejected = {row["candidate_index"]: row for row in result["unverified_candidates"]}
        self.assertEqual(rejected[0]["candidate"]["mechanism"],
                         "returns <script>alert(1)</script> | wrong value")
        self.assertEqual(rejected[0]["reason"], "candidate_schema_invalid")
        self.assertIsNone(rejected[1]["candidate"])
        self.assertEqual(rejected[1]["reason"], "candidate_schema_invalid")
        call = result["perspectives"][-1]
        self.assertEqual(call["status"], "completed")
        self.assertEqual([row["status"] for row in call["candidates"]],
                         ["unverified", "unverified", "accepted"])
        source = next((output / "source" / "runs").iterdir())
        sealed = verify_final_bundle(Path(result["final_source_only_bundle"]), source)
        self.assertEqual(sealed["report"]["candidate_counts"], {"accepted": 1, "unverified": 2})
        self.assertEqual(sealed["report"]["analysis_status"], "incomplete")
        self.assertEqual(sealed["report"]["confirmed_count"], 0)

    def test_existing_output_and_invalid_template_block_model(self):
        output = self.root / "existing"
        output.mkdir()
        code, _ = self.call(output)
        self.assertEqual(code, 2)
        self.assertFalse((output / "report.md").exists())
        self.template["model"]["endpoint"] = "https://example.invalid/other"
        self.saved.write_text(json.dumps(self.template))
        new = self.root / "invalid"
        with patch("modules.diagnosis.model._request") as request:
            code, _ = self.call(new)
        self.assertEqual(code, 2)
        request.assert_not_called()
        self.assertFalse((new / "result.json").exists())
        self.assertIn("코드 진단 중단", (new / "report.md").read_text())


if __name__ == "__main__":
    unittest.main()
