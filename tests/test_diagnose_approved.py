"""Manual one-use consent gates model transmission even for known Git source."""

import hashlib
import json
import contextlib
import io
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import diagnose_approved  # noqa: E402
from modules.diagnosis.model import PERSPECTIVES, analyze, prompt_hash  # noqa: E402
from modules.diagnosis.plan import context_hash, prepare_analysis  # noqa: E402
from modules.evidence.authenticity import verify_git_source  # noqa: E402
from modules.evidence.final_bundle import verify_final_bundle  # noqa: E402
from modules.evidence.provenance import write_source_run  # noqa: E402
from modules.findings.admission import admit  # noqa: E402
from modules.run_policy import issue_approval, manifest_hash  # noqa: E402
from modules.static_scan.orchestrator import scan  # noqa: E402


class ApprovedDiagnosisTest(unittest.TestCase):
    def fixture(self, root, files):
        repo = root / "repo"
        repo.mkdir()

        def git(*args):
            return subprocess.run(["git", "-C", str(repo), *args], check=True,
                                  capture_output=True, text=True).stdout.strip()

        git("init", "-q")
        for path, source in files.items():
            (repo / path).write_text(source)
        git("add", ".")
        git("-c", "user.name=A", "-c", "user.email=a@b.c", "commit", "-qm", "base")
        base = git("rev-parse", "HEAD")
        return repo, base, git

    def approved(self, root, repo, sha, tokens, *, mode="five", symbol="a",
                 scope=None, main_ref=None, candidate_ref=None):
        bundle = write_source_run(root / "source", str(repo), scan(repo, sha))
        bounds = {"wall_seconds": 30, "cpu_seconds": 30, "memory_bytes": 1048576,
                  "tokens": tokens, "tool_seconds": 30}
        analysis, _, _ = prepare_analysis(
            verify_git_source(bundle), mode=mode, symbol=symbol, scope=scope,
            main_ref=main_ref, candidate_ref=candidate_ref)
        manifest = {"schema_version": "run-manifest-v3", "snapshot_sha": sha,
                    "analysis": analysis,
                    "image_digest": "sha256:" + "a" * 64, "tools": ["python"],
                    "nodes": [{"id": "work", "argv": ["python", "a.py"],
                               "cwd": "/workspace", "workload": "a.py",
                               "trigger": "always", "tool": "python"}],
                    "limits": {**bounds, "per_node": {"work": bounds}},
                    "network": {"dependency": False, "model": True, "workload": False},
                    "writable_paths": ["/work/evidence"],
                    "model": {"endpoint": "https://api.anthropic.com/v1/messages",
                              "name_version": "pinned-model", "prompt_sha256": prompt_hash(mode),
                              "transmitted_data": ["source", "context"]}}
        manifest_file = root / "manifest.json"
        manifest_file.write_text(json.dumps(manifest))
        receipt = root / "approval.json"
        return bundle, manifest, manifest_file, receipt

    def invoke(self, bundle, manifest_file, receipt, *options, expected_code=0):
        output = io.StringIO()
        if "--response-output" not in options:
            options = (*options, "--response-output", str(manifest_file.parent / "responses"))
        with patch.object(sys, "argv", ["diagnose_approved.py", str(bundle), str(manifest_file),
                                        str(receipt), *options]), contextlib.redirect_stdout(output):
            code = diagnose_approved.main()
        self.assertEqual(code, expected_code)
        return json.loads(output.getvalue())

    def test_boundary_role_keeps_taxonomy_and_failure_attribution_separate(self):
        for scope in (("--symbol", "a"), ("--scope", "full")):
            for boundary_line in (2, 999):
                with self.subTest(scope=scope, boundary_line=boundary_line), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    repo, sha, _ = self.fixture(root, {"a.py": "def a(value):\n    return 1 / value\n"})
                    bundle, manifest, file, receipt = self.approved(
                        root, repo, sha, 30000, mode="boundary",
                        symbol="a" if scope[0] == "--symbol" else None,
                        scope=None if scope[0] == "--symbol" else "full")
                    manifest["model"]["prompt_sha256"] = prompt_hash("boundary")
                    file.write_text(json.dumps(manifest))
                    issue_approval(manifest, sha, receipt, manifest_hash(manifest))
                    source_id = verify_git_source(bundle)["evidence"][0]["id"]
                    candidate = {
                        "root_symbol": "a", "mechanism": "zero input reaches division",
                        "condition": "value is zero", "trigger": "a(0)", "impact": "request fails",
                        "taxonomy": "correctness", "severity": "High",
                        "location": {"path": "a.py", "line": 2}, "evidence_ids": [source_id],
                        "next_action": {"action": "check zero input handling", "oracle": "a(0) has defined behavior",
                                        "time_minutes": 2}}

                    def reply(endpoint, payload, timeout):
                        role = json.loads(payload["messages"][0]["content"])["perspective"]
                        rows = []
                        if role == "correctness":
                            rows = [candidate]
                        elif role == "assumptions":
                            rows = [{**candidate, "mechanism": "caller nonzero contract is not established",
                                     "location": {"path": "a.py", "line": boundary_line}}]
                        return {"usage": {"input_tokens": 100, "output_tokens": 20},
                                "stop_reason": "end_turn",
                                "content": [{"type": "text", "text": json.dumps({"candidates": rows})}]}

                    with patch("modules.diagnosis.model._request", side_effect=reply):
                        result = self.invoke(bundle, file, receipt, *scope, "--boundary-review",
                                             "--final-output", str(root / "final"),
                                             expected_code=0 if boundary_line == 2 else 3)
                    sealed = verify_final_bundle(Path(result["final_source_only_bundle"]), bundle)
                    findings = sealed["findings"]
                    self.assertEqual({row["taxonomy"] for row in findings}, {"correctness"})
                    self.assertEqual({row["state"] for row in findings}, {"deferred"})
                    self.assertEqual({tuple(row["perspectives"]) for row in findings},
                                     {("correctness",), ("assumptions",)} if boundary_line == 2
                                     else {("correctness",)})
                    audits = result["perspectives"]
                    if scope[0] == "--scope":
                        audits = audits[0]["perspectives"]
                        self.assertEqual(result["diagnosis_coverage"]["analyzed_paths"],
                                         ["a.py"])
                    by_role = {row["perspective"]: row for row in audits}
                    self.assertEqual(by_role["correctness"]["status"], "completed")
                    self.assertEqual(by_role["assumptions"]["status"], "completed")
                    self.assertEqual(by_role["assumptions"]["candidates"][0]["status"],
                                     "accepted" if boundary_line == 2 else "unverified")
                    self.assertEqual(sum(row["tokens"] for row in audits), 720)
                    self.assertEqual(sealed["report"]["confirmed_count"], 0)
                    if boundary_line == 999:
                        self.assertEqual(result["unverified_candidates"][0]["perspective"], "assumptions")

    def test_mixed_batch_rows_seal_valid_candidate_with_actual_role_and_exit_three(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, sha, _ = self.fixture(root, {"a.py": "def a(value):\n    return 1 / value\n"})
            bundle, manifest, file, receipt = self.approved(
                root, repo, sha, 20000, symbol=None, scope="full")
            issue_approval(manifest, sha, receipt, manifest_hash(manifest))
            source_id = verify_git_source(bundle)["evidence"][0]["id"]
            valid = {"root_symbol": "a", "mechanism": "zero input reaches division",
                     "condition": "value is zero", "trigger": "a(0)", "impact": "request fails",
                     "taxonomy": "correctness", "perspective": "tests", "severity": "High",
                     "location": {"path": "a.py", "line": 2}, "evidence_ids": [source_id],
                     "next_action": {"action": "check zero handling", "oracle": "defined outcome",
                                     "time_minutes": 2}}
            rows = [None, valid, {**valid, "evidence_ids": ["forged-source"]},
                    {**valid, "location": {"path": "a.py", "line": 999}},
                    {**valid, "taxonomy": "invented"}]

            def respond(endpoint, payload, timeout):
                role = json.loads(payload["messages"][0]["content"])["perspective"]
                return {"usage": {"input_tokens": 100, "output_tokens": 20},
                        "stop_reason": "end_turn",
                        "content": [{"type": "text", "text": json.dumps({
                            "candidates": rows if role == "structure" else []})}]}

            with patch("modules.diagnosis.model._request", side_effect=respond):
                result = self.invoke(bundle, file, receipt, "--scope", "full",
                                     "--final-output", str(root / "final"), expected_code=3)
            sealed = verify_final_bundle(Path(result["final_source_only_bundle"]), bundle)
            self.assertEqual(len(sealed["findings"]), 1)
            finding = sealed["findings"][0]
            self.assertEqual(finding["taxonomy"], "correctness")
            self.assertEqual(finding["perspectives"], ["structure"])
            self.assertEqual(finding["state"], "deferred")
            self.assertEqual(finding["basis"], "source_only")
            self.assertEqual(result["diagnosis_coverage"]["analyzed_paths"], ["a.py"])
            call = result["perspectives"][0]["perspectives"][0]
            self.assertEqual(call["status"], "completed")
            self.assertEqual([row["index"] for row in call["candidates"]], list(range(5)))
            self.assertEqual([row["status"] for row in call["candidates"]],
                             ["unverified", "accepted", "unverified", "unverified", "unverified"])
            self.assertEqual([row["reason"] for row in call["candidates"]],
                             ["candidate_schema_invalid", None, "candidate_source_invalid",
                              "candidate_location_outside_context", "candidate_schema_invalid"])
            self.assertEqual(call["candidates"][1]["finding_id"], finding["id"])
            self.assertEqual(call["candidates"][1]["candidate"], valid)
            for entry, original in zip(call["candidates"], rows):
                self.assertEqual(entry["candidate_sha256"], context_hash(original))
            self.assertEqual(sealed["report"]["confirmed_count"], 0)

    def test_analysis_scope_mode_and_context_mismatch_preserve_approval(self):
        cases = [
            (("--symbol", "other"), None),
            (("--scope", "full"), None),
            (("--symbol", "a", "--single-baseline"), None),
            (("--symbol", "a"), "context"),
            (("--symbol", "a"), "roles"),
        ]
        for options, altered in cases:
            with self.subTest(options=options, altered=altered), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                repo, sha, _ = self.fixture(
                    root, {"a.py": "def a(): return 1\n\ndef other(): return 2\n"})
                bundle, manifest, file, receipt = self.approved(root, repo, sha, 20000)
                if altered == "context":
                    manifest["analysis"]["contexts"][0]["sha256"] = "0" * 64
                elif altered == "roles":
                    manifest["analysis"]["mode"] = "single"
                    manifest["analysis"]["roles"] = ["all"]
                file.write_text(json.dumps(manifest))
                issue_approval(manifest, sha, receipt, manifest_hash(manifest))
                with patch("modules.diagnosis.model._request") as request:
                    with self.assertRaises(SystemExit) as rejected:
                        self.invoke(bundle, file, receipt, *options)
                self.assertEqual(rejected.exception.code, 2)
                request.assert_not_called()
                self.assertFalse(Path(str(receipt) + ".used").exists())
                self.assertFalse((root / "responses").exists())

    def test_response_output_required_without_consuming_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, sha, _ = self.fixture(root, {"a.py": "def a(): return 1\n"})
            bundle, manifest, file, receipt = self.approved(root, repo, sha, 20000)
            issue_approval(manifest, sha, receipt, manifest_hash(manifest))
            with patch.object(sys, "argv", [
                    "diagnose_approved.py", str(bundle), str(file), str(receipt),
                    "--symbol", "a"]), patch("modules.diagnosis.model._request") as request:
                with self.assertRaises(SystemExit) as rejected:
                    diagnose_approved.main()
            self.assertEqual(rejected.exception.code, 2)
            request.assert_not_called()
            self.assertFalse(Path(str(receipt) + ".used").exists())

    def test_response_storage_failure_stops_after_consuming_one_use_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, sha, _ = self.fixture(root, {"a.py": "def a(): return 1\n"})
            bundle, manifest, file, receipt = self.approved(root, repo, sha, 20000)
            issue_approval(manifest, sha, receipt, manifest_hash(manifest))
            output = root / "responses"

            def response(endpoint, payload, timeout):
                output.rmdir()
                output.write_text("storage became unavailable")
                return {"usage": {"input_tokens": 30, "output_tokens": 10},
                        "stop_reason": "end_turn",
                        "content": [{"type": "text", "text": '{"candidates": []}'}]}

            with patch("modules.diagnosis.model._request", side_effect=response) as request:
                with self.assertRaises(SystemExit) as rejected:
                    self.invoke(bundle, file, receipt, "--symbol", "a",
                                "--final-output", str(root / "final"))
            self.assertEqual(rejected.exception.code, 2)
            self.assertEqual(request.call_count, 1)
            self.assertTrue(Path(str(receipt) + ".used").exists())
            self.assertFalse((root / "final").exists())

    def test_boundary_mode_requires_matching_approval_before_transmission(self):
        cases = [
            (prompt_hash("five"), ("--boundary-review",)),
            (prompt_hash("boundary"), ()),
            (prompt_hash("boundary"), ("--boundary-review", "--single-baseline")),
            (prompt_hash("boundary"), ("--boundary-review", "--plain-baseline")),
        ]
        for approved_hash, options in cases:
            with self.subTest(options=options, prompt_hash=approved_hash), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                repo, sha, _ = self.fixture(root, {"a.py": "def a(): return 1\n"})
                bundle, manifest, file, receipt = self.approved(
                    root, repo, sha, 30000,
                    mode="boundary" if approved_hash == prompt_hash("boundary") else "five")
                manifest["model"]["prompt_sha256"] = approved_hash
                file.write_text(json.dumps(manifest))
                issue_approval(manifest, sha, receipt, manifest_hash(manifest))
                with patch("modules.diagnosis.model._request",
                           side_effect=AssertionError("unapproved mode transmitted source")):
                    with self.assertRaises(SystemExit) as error:
                        self.invoke(bundle, file, receipt, "--symbol", "a", *options)
                self.assertEqual(error.exception.code, 2)
                self.assertFalse(Path(str(receipt) + ".used").exists())

    def test_boundary_budget_defers_extra_role_and_remaining_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, sha, _ = self.fixture(root, {"a.py": "def a(): return 1\n",
                                              "b.py": "def b(): return 2\n"})
            bundle, manifest, file, receipt = self.approved(
                root, repo, sha, 24000, mode="boundary", symbol=None, scope="full")
            manifest["model"]["prompt_sha256"] = prompt_hash("boundary")
            file.write_text(json.dumps(manifest))
            issue_approval(manifest, sha, receipt, manifest_hash(manifest))
            response = {"usage": {"input_tokens": 3800, "output_tokens": 100},
                        "stop_reason": "end_turn",
                        "content": [{"type": "text", "text": '{"candidates": []}'}]}
            with patch("modules.diagnosis.model._request", return_value=response):
                result = self.invoke(bundle, file, receipt, "--scope", "full", "--boundary-review",
                                     "--final-output", str(root / "final"), expected_code=3)
            audit = result["perspectives"]
            self.assertEqual([row["status"] for row in audit[0]["perspectives"]],
                             ["completed"] * 5 + ["deferred"])
            self.assertEqual(audit[0]["perspectives"][-1]["reason"], "budget_exhausted")
            self.assertEqual([row["status"] for row in audit[1]["perspectives"]], ["deferred"] * 6)
            self.assertEqual(result["diagnosis_coverage"]["tokens_used"], 19500)
            self.assertEqual(result["diagnosis_coverage"]["analyzed_paths"], [])
            self.assertEqual(result["diagnosis_coverage"]["omitted_unknown_paths"], ["a.py", "b.py"])
            sealed = verify_final_bundle(Path(result["final_source_only_bundle"]), bundle)
            self.assertEqual(sealed["report"]["confirmed_count"], 0)

    def test_single_call_baseline_needs_approval_and_cannot_claim_final_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, sha, _ = self.fixture(root, {"a.py": "def a(): return 1\n"})
            bundle, manifest, manifest_file, receipt = self.approved(
                root, repo, sha, 10000, mode="single")
            manifest["tools"] = []
            manifest["nodes"] = []
            manifest["limits"]["per_node"] = {}
            manifest["model"].update(endpoint="http://127.0.0.1:10531/v1/responses",
                                     name_version="gpt-6-sol")
            manifest_file.write_text(json.dumps(manifest))
            evidence_id = verify_git_source(bundle)["evidence"][0]["id"]
            candidate = {"root_symbol": "a", "mechanism": "unexpected output",
                         "condition": "when called", "impact": "wrong result",
                         "trigger": "invoke a", "taxonomy": "correctness",
                         "severity": "Medium", "location": {"path": "a.py", "line": 1},
                         "evidence_ids": [evidence_id],
                         "next_action": {"action": "assert return value", "oracle": "equals one",
                                         "time_minutes": 1}}
            calls = []

            def response(endpoint, payload, timeout):
                calls.append(json.loads(payload["input"][0]["content"])["perspective"])
                return {"usage": {"input_tokens": 30, "output_tokens": 10},
                        "stop_reason": "end_turn",
                        "content": [{"type": "text", "text": json.dumps({"candidates": [candidate]})}]}

            with patch("modules.diagnosis.model._request", side_effect=AssertionError("network before consent")):
                with self.assertRaises(SystemExit):
                    self.invoke(bundle, manifest_file, receipt, "--symbol", "a", "--single-baseline")
            self.assertFalse(Path(str(receipt) + ".used").exists())
            issue_approval(manifest, sha, receipt, manifest_hash(manifest))
            with patch("modules.diagnosis.model._request", side_effect=response):
                result = self.invoke(bundle, manifest_file, receipt, "--symbol", "a", "--single-baseline")
            self.assertEqual(calls, ["all"])
            self.assertEqual(result["stage"], "pilot_baseline_provisional")
            self.assertEqual(result["model_version"], "gpt-6-sol")
            self.assertEqual(result["perspectives"][0]["tokens"], 40)
            self.assertEqual(result["findings"][0]["root_symbol"], "a")
            self.assertEqual(result["findings"][0]["state"], "deferred")
            self.assertEqual(result["findings"][0]["perspectives"], ["all"])
            self.assertTrue(Path(str(receipt) + ".used").exists())
            with self.assertRaises(SystemExit):
                self.invoke(bundle, manifest_file, receipt, "--symbol", "a", "--single-baseline",
                            "--final-output", str(root / "not-a-final-report"))
            self.assertFalse((root / "not-a-final-report").exists())

    def test_single_call_baseline_reviews_whole_small_scope_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, sha, _ = self.fixture(root, {"a.py": "from b import answer\n",
                                                "b.py": "def answer(): return 1\n"})
            bundle, manifest, file, receipt = self.approved(
                root, repo, sha, 20000, mode="single", symbol=None, scope="full")
            manifest["tools"] = []
            manifest["nodes"] = []
            manifest["limits"]["per_node"] = {}
            file.write_text(json.dumps(manifest))
            issue_approval(manifest, sha, receipt, manifest_hash(manifest))
            seen = []
            evidence_id = next(item["id"] for item in verify_git_source(bundle)["evidence"]
                               if item["path"] == "b.py")
            candidate = {"root_symbol": "answer", "mechanism": "unexpected output",
                         "condition": "when called", "impact": "wrong result",
                         "trigger": "invoke answer", "taxonomy": "correctness",
                         "severity": "Medium", "location": {"path": "b.py", "line": 1},
                         "evidence_ids": [evidence_id],
                         "next_action": {"action": "assert return value", "oracle": "equals one",
                                         "time_minutes": 1}}

            def respond(endpoint, payload, timeout):
                request = json.loads(payload["messages"][0]["content"])
                seen.append(request)
                return {"usage": {"input_tokens": 100, "output_tokens": 10},
                        "stop_reason": "end_turn",
                        "content": [{"type": "text", "text": json.dumps({"candidates": [candidate]})}]}

            with patch("modules.diagnosis.model._request", side_effect=respond):
                result = self.invoke(bundle, file, receipt, "--scope", "full", "--single-baseline")
            self.assertEqual(len(seen), 1)
            self.assertEqual(seen[0]["perspective"], "all")
            self.assertEqual({node["path"] for node in seen[0]["context"]["nodes"]}, {"a.py", "b.py"})
            self.assertEqual(seen[0]["context"]["edges"], [])
            self.assertEqual(result["scope"], "full_tracked_python_git_commit")
            self.assertEqual(result["diagnosis_coverage"]["analyzed_paths"], ["a.py", "b.py"])
            self.assertEqual(result["stage"], "pilot_baseline_provisional")
            self.assertEqual(result["findings"][0]["location"]["path"], "b.py")
            self.assertEqual(result["findings"][0]["state"], "deferred")

    def test_plain_baseline_sends_only_target_raw_source_after_matching_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, sha, _ = self.fixture(root, {
                "a.py": "def target(x):\n    return 1 / x\n",
                "oracle.py": "SECRET_EXPECTED_ZERO_DIVISION\n"})
            bundle, manifest, file, receipt = self.approved(
                root, repo, sha, 10000, mode="plain", symbol="target")
            manifest["tools"] = []
            manifest["nodes"] = []
            manifest["limits"]["per_node"] = {}
            manifest["model"].update(endpoint="http://127.0.0.1:10531/v1/responses",
                                     name_version="gpt-6-luna",
                                     prompt_sha256=prompt_hash("plain"))
            file.write_text(json.dumps(manifest))
            with patch("modules.diagnosis.model._request",
                       side_effect=AssertionError("network before approval")):
                with self.assertRaises(SystemExit):
                    self.invoke(bundle, file, receipt, "--symbol", "target", "--plain-baseline")
            self.assertFalse(Path(str(receipt) + ".used").exists())
            issue_approval(manifest, sha, receipt, manifest_hash(manifest))
            evidence_id = next(item["id"] for item in verify_git_source(bundle)["evidence"]
                               if item["path"] == "a.py")
            requests = []

            def respond(endpoint, payload, timeout):
                requests.append(payload)
                return {"usage": {"input_tokens": 30, "output_tokens": 10},
                        "stop_reason": "end_turn",
                        "content": [{"type": "text", "text": json.dumps({"candidates": [{
                            "root_symbol": "target", "mechanism": "division by zero",
                            "condition": "x=0", "trigger": "target(0)", "impact": "raises",
                            "taxonomy": "correctness", "severity": "High",
                            "location": {"path": "a.py", "line": 2},
                            "evidence_ids": [evidence_id],
                            "next_action": {"action": "handle zero", "oracle": "returns zero",
                                            "time_minutes": 1}}]})}]}

            with patch("modules.diagnosis.model._request", side_effect=respond):
                result = self.invoke(bundle, file, receipt, "--symbol", "target", "--plain-baseline")
            self.assertEqual(len(requests), 1)
            sent = json.loads(requests[0]["input"][0]["content"])
            self.assertEqual(sent["function"], "target")
            self.assertEqual([row["path"] for row in sent["source"]], ["a.py"])
            self.assertEqual(sent["source"][0]["text"], "def target(x):\n    return 1 / x\n")
            self.assertNotIn("SECRET_EXPECTED_ZERO_DIVISION", json.dumps(sent))
            self.assertNotIn("edges", sent)
            self.assertNotIn("static_counterexamples", sent)
            self.assertEqual(result["stage"], "pilot_plain_baseline_provisional")
            self.assertEqual(result["findings"][0]["location"]["line"], 2)
            self.assertEqual(result["perspectives"][0]["tokens"], 40)


    def test_failed_model_json_is_preserved_without_sealing_or_stdout_leak(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, sha, _ = self.fixture(root, {"a.py": "def a(): return 1\n"})
            bundle, manifest, file, receipt = self.approved(
                root, repo, sha, 10000, mode="single")
            manifest["tools"], manifest["nodes"], manifest["limits"]["per_node"] = [], [], {}
            file.write_text(json.dumps(manifest))
            output = root / "responses"
            with patch("modules.diagnosis.model._request",
                       side_effect=AssertionError("network before approval")) as request:
                with self.assertRaises(SystemExit):
                    self.invoke(bundle, file, receipt, "--symbol", "a", "--single-baseline",
                                "--response-output", str(output))
            request.assert_not_called()
            self.assertFalse(output.exists())
            issue_approval(manifest, sha, receipt, manifest_hash(manifest))
            reply = {"stop_reason": "end_turn", "usage": {"output_tokens": 5, "input_tokens": 30},
                     "content": [{"type": "text", "text": 'NOT JSON private-only marker ☃'}]}
            with patch("modules.diagnosis.model._request", return_value=reply):
                result = self.invoke(bundle, file, receipt, "--symbol", "a",
                                     "--single-baseline", "--response-output", str(output),
                                     expected_code=3)
            audit = result["perspectives"][0]
            self.assertEqual((audit["status"], audit["reason"]), ("failed", "output_json_invalid"))
            self.assertEqual(result["findings"], [])
            self.assertEqual(result["unverified_candidates"], [])
            artifact = result["response_artifacts"][0]
            raw = Path(artifact["path"]).read_bytes()
            self.assertEqual(raw, json.dumps(reply, sort_keys=True, ensure_ascii=False).encode())
            self.assertEqual(hashlib.sha256(raw).hexdigest(), artifact["response_sha256"])
            self.assertEqual(artifact["response_sha256"], audit["response_sha256"])
            self.assertEqual(len(list(output.iterdir())), 1)
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(Path(artifact["path"]).stat().st_mode), 0o600)
            self.assertNotIn("private-only marker", json.dumps(result))
            self.assertTrue(Path(str(receipt) + ".used").exists())

    def test_batch_responses_have_unique_paths_and_audit_hashes_on_candidate_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, sha, _ = self.fixture(root, {"a.py": "def a(): return 1\n"})
            bundle, manifest, file, receipt = self.approved(root, repo, sha, 20000)
            manifest["tools"], manifest["nodes"], manifest["limits"]["per_node"] = [], [], {}
            file.write_text(json.dumps(manifest))
            issue_approval(manifest, sha, receipt, manifest_hash(manifest))
            def respond(endpoint, payload, timeout):
                perspective = json.loads(payload["messages"][0]["content"])["perspective"]
                claim = {"taxonomy": perspective, "location": {"path": "a.py", "line": 1},
                         "evidence_ids": ["wrong-source"]}
                return {"usage": {"input_tokens": 30, "output_tokens": 10},
                        "stop_reason": "end_turn",
                        "content": [{"type": "text", "text": json.dumps(
                            {"candidates": [claim] if perspective == "structure" else []})}]}
            with patch("modules.diagnosis.model._request", side_effect=respond):
                result = self.invoke(bundle, file, receipt, "--symbol", "a",
                                     "--response-output", str(root / "responses"),
                                     "--final-output", str(root / "final"), expected_code=3)
            self.assertEqual(result["perspectives"][0]["status"], "completed")
            self.assertEqual(result["perspectives"][0]["candidates"][0]["reason"],
                             "candidate_source_invalid")
            self.assertEqual(result["findings"], [])
            self.assertEqual(verify_final_bundle(Path(result["final_source_only_bundle"]), bundle)
                             ["report"]["confirmed_count"], 0)
            refs = result["response_artifacts"]
            self.assertEqual(len(refs), 5)
            self.assertEqual(len({row["path"] for row in refs}), 5)
            self.assertEqual([row["response_sha256"] for row in refs],
                             [row["response_sha256"] for row in result["perspectives"]])
            for artifact in refs:
                self.assertEqual(hashlib.sha256(Path(artifact["path"]).read_bytes()).hexdigest(),
                                 artifact["response_sha256"])

    def test_unsafe_response_output_rejected_before_consuming_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, sha, _ = self.fixture(root, {"a.py": "def a(): return 1\n"})
            bundle, manifest, file, receipt = self.approved(
                root, repo, sha, 10000, mode="single")
            manifest["tools"], manifest["nodes"], manifest["limits"]["per_node"] = [], [], {}
            file.write_text(json.dumps(manifest))
            issue_approval(manifest, sha, receipt, manifest_hash(manifest))
            existing = root / "existing"
            existing.mkdir()
            linked = root / "linked"
            linked.symlink_to(existing, target_is_directory=True)
            for destination in (repo / "responses", bundle / "responses",
                                existing, linked / "responses", root / "missing" / "responses"):
                with self.subTest(destination=destination), patch(
                        "modules.diagnosis.model._request",
                        side_effect=AssertionError("unsafe response output must not transmit")) as request:
                    with self.assertRaises(SystemExit):
                        self.invoke(bundle, file, receipt, "--symbol", "a", "--single-baseline",
                                    "--response-output", str(destination))
                    request.assert_not_called()
                    self.assertFalse(Path(str(receipt) + ".used").exists())
            self.assertFalse((existing / "responses").exists())


    def test_full_baseline_refuses_partial_python_source_before_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, sha, _ = self.fixture(root, {"a.py": "def ready(): return 1\n",
                                                "broken.py": "def incomplete(\n"})
            bundle, manifest, file, receipt = self.approved(
                root, repo, sha, 20000, mode="single", symbol="ready")
            with self.assertRaises(ValueError):
                prepare_analysis(verify_git_source(bundle), mode="single", scope="full")
            manifest["tools"] = []
            manifest["nodes"] = []
            manifest["limits"]["per_node"] = {}
            file.write_text(json.dumps(manifest))
            issue_approval(manifest, sha, receipt, manifest_hash(manifest))
            with patch("modules.diagnosis.model._request",
                       side_effect=AssertionError("partial source must not be transmitted")):
                with self.assertRaises(SystemExit):
                    self.invoke(bundle, file, receipt, "--scope", "full", "--single-baseline")
            self.assertFalse(Path(str(receipt) + ".used").exists())

    def test_parser_mismatch_rejects_before_consuming_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, sha, _ = self.fixture(root, {"a.py": "def a(): return 1\n"})
            _, manifest, file, receipt = self.approved(root, repo, sha, 10000)
            staged = scan(repo, sha)
            staged["python_parser"] = "another-parser"
            other_bundle = write_source_run(root / "other-source", str(repo), staged)
            file.write_text(json.dumps(manifest))
            issue_approval(manifest, sha, receipt, manifest_hash(manifest))
            response = {"usage": {"input_tokens": 30, "output_tokens": 10},
                        "stop_reason": "end_turn",
                        "content": [{"type": "text", "text": '{"candidates": []}'}]}
            with patch("modules.diagnosis.model._request", return_value=response) as request:
                with self.assertRaises(SystemExit):
                    self.invoke(other_bundle, file, receipt, "--symbol", "a")
            request.assert_not_called()
            self.assertFalse(Path(str(receipt) + ".used").exists())

    def test_unsupported_model_plan_preserves_unused_approval(self):
        for field, value in (("prompt_sha256", "0" * 64),
                             ("endpoint", "https://example.invalid/v1/messages"),
                             ("transmitted_data", ["source"])):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                repo, sha, _ = self.fixture(root, {"a.py": "def a(): return 1\n"})
                bundle, manifest, file, receipt = self.approved(root, repo, sha, 10000)
                manifest["model"][field] = value
                file.write_text(json.dumps(manifest))
                issue_approval(manifest, sha, receipt, manifest_hash(manifest))
                with patch("modules.diagnosis.model._request",
                           side_effect=AssertionError("invalid plan must not contact model")):
                    with self.assertRaises(SystemExit):
                        self.invoke(bundle, file, receipt, "--symbol", "a")
                self.assertFalse(Path(str(receipt) + ".used").exists())

    def test_invalid_runtime_plan_preserves_unused_approval(self):
        for misplaced_output in (True, False):
            with self.subTest(misplaced_output=misplaced_output), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                repo, sha, _ = self.fixture(root, {"a.py": "def a(): return 1\n"})
                bundle, manifest, file, receipt = self.approved(root, repo, sha, 10000)
                output = bundle / "runtime" if misplaced_output else root / "runtime"
                if not misplaced_output:
                    manifest["nodes"][0]["argv"] = ["python", "missing.py"]
                file.write_text(json.dumps(manifest))
                issue_approval(manifest, sha, receipt, manifest_hash(manifest))
                with patch.object(diagnose_approved, "validate_runtime_host"), patch.object(
                        diagnose_approved, "execute_nodes",
                        side_effect=AssertionError("invalid plan must not run target")), patch(
                        "modules.diagnosis.model._request",
                        side_effect=AssertionError("invalid plan must not transmit source")):
                    with self.assertRaises(SystemExit):
                        self.invoke(bundle, file, receipt, "--symbol", "a",
                                    "--runtime-output", str(output))
                self.assertFalse(Path(str(receipt) + ".used").exists())

    def test_source_bundle_cannot_hold_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, sha, _ = self.fixture(root, {"a.py": "def a(): return 1\n"})
            bundle, manifest, file, _ = self.approved(root, repo, sha, 10000)
            receipt = bundle / "approval.json"
            issue_approval(manifest, sha, receipt, manifest_hash(manifest))
            with patch("modules.diagnosis.model._request",
                       side_effect=AssertionError("source bundle must not hold approval")):
                with self.assertRaises(SystemExit):
                    self.invoke(bundle, file, receipt, "--symbol", "a")
            self.assertFalse(Path(str(receipt) + ".used").exists())

    def test_selected_symbol_report_keeps_symbol_scope_through_both_sealers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = "def a(): return 1\n\ndef unrelated():\n" + "    # padding\n" * 2500 + "    return 3\n"
            repo, sha, _ = self.fixture(root, {"a.py": source, "b.py": "def b(): return 2\n"})
            bundle, manifest, manifest_file, receipt = self.approved(root, repo, sha, 15000)
            issue_approval(manifest, sha, receipt, manifest_hash(manifest))
            response = {"usage": {"input_tokens": 500, "output_tokens": 1},
                        "stop_reason": "end_turn",
                        "content": [{"type": "text", "text": '{"candidates": []}'}]}
            with patch("modules.diagnosis.model._request", return_value=response):
                review = self.invoke(bundle, manifest_file, receipt, "--symbol", "a",
                                     "--final-output", str(root / "reports"))
            first = verify_final_bundle(Path(review["final_source_only_bundle"]), bundle)
            self.assertEqual(first["run"]["scope"], "selected_symbol_only")
            self.assertEqual(first["run"]["diagnosis_coverage"]["symbol"], "a")
            self.assertEqual(first["report"]["coverage"]["diagnosis"],
                             review["diagnosis_coverage"])
            self.assertEqual(first["report"]["confirmed_count"], 0)
            review_file = root / "review.json"
            review_file.write_text(json.dumps(review))
            command = [sys.executable, str(ROOT / "src" / "seal_report.py"),
                       str(bundle), str(review_file), str(root / "resealed"),
                       "--run-manifest", str(manifest_file)]
            sealed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(sealed.returncode, 0, sealed.stderr)
            second = verify_final_bundle(Path(json.loads(sealed.stdout)["bundle"]), bundle)
            self.assertEqual(second["run"]["scope"], "selected_symbol_only")
            self.assertEqual(second["run"]["diagnosis_coverage"],
                             first["run"]["diagnosis_coverage"])
            review["diagnosis_coverage"]["context_node_ids"] = []
            review_file.write_text(json.dumps(review))
            rejected = subprocess.run([*command[:4], str(root / "invalid"), *command[5:]],
                                      capture_output=True, text=True)
            self.assertEqual(rejected.returncode, 2)
            self.assertFalse((root / "invalid").exists())
            review["diagnosis_coverage"] = first["run"]["diagnosis_coverage"]
            evidence_id = next(item["id"] for item in verify_git_source(bundle)["evidence"]
                               if item["path"] == "a.py")
            candidate = {"root_symbol": "unrelated", "mechanism": "incorrect return",
                         "condition": "when called", "impact": "wrong output",
                         "trigger": "invoke unrelated", "taxonomy": "correctness",
                         "severity": "Medium", "location": {"path": "a.py", "line": 3},
                         "evidence_ids": [evidence_id],
                         "next_action": {"action": "run a test", "oracle": "expect 3",
                                         "time_minutes": 1}, "perspective": "correctness"}
            review["findings"] = admit(bundle, [candidate])
            review_file.write_text(json.dumps(review))
            rejected = subprocess.run([*command[:4], str(root / "outside-context"), *command[5:]],
                                      capture_output=True, text=True)
            self.assertEqual(rejected.returncode, 2)
            self.assertFalse((root / "outside-context").exists())

    def test_oversized_selected_symbol_does_not_review_only_its_neighbor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = "def huge():\n" + "    # padding\n" * 2500 + "    return small()\n"
            source += "def small(): return 1\n"
            repo, sha, _ = self.fixture(root, {"a.py": source})
            bundle, manifest, manifest_file, receipt = self.approved(
                root, repo, sha, 6000, symbol="small")
            with self.assertRaises(ValueError):
                prepare_analysis(verify_git_source(bundle), symbol="huge")
            issue_approval(manifest, sha, receipt, manifest_hash(manifest))
            with patch("modules.diagnosis.model._request",
                       side_effect=AssertionError("model must not see neighbor-only context")):
                with self.assertRaises(SystemExit) as denied:
                    self.invoke(bundle, manifest_file, receipt, "--symbol", "huge",
                                "--final-output", str(root / "reports"))
            self.assertEqual(denied.exception.code, 2)
            self.assertFalse(Path(str(receipt) + ".used").exists())
            self.assertFalse((root / "reports").exists())

    def test_provisional_symbol_review_discards_claim_outside_supplied_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = "def a(): return 1\n\ndef unrelated():\n" + "    # padding\n" * 2500 + "    return 3\n"
            repo, sha, _ = self.fixture(root, {"a.py": source})
            bundle, manifest, manifest_file, receipt = self.approved(root, repo, sha, 6000)
            evidence_id = verify_git_source(bundle)["evidence"][0]["id"]
            candidate = {"root_symbol": "unrelated", "mechanism": "wrong result",
                         "condition": "when called", "impact": "incorrect output",
                         "trigger": "invoke unrelated", "taxonomy": "correctness",
                         "severity": "Medium", "location": {"path": "a.py", "line": 3},
                         "evidence_ids": [evidence_id],
                         "next_action": {"action": "run a test", "oracle": "expect 3",
                                         "time_minutes": 1}}
            crossing = {**candidate, "root_symbol": "a",
                        "location": {"path": "a.py", "line": 1, "end_line": 3},
                        "taxonomy": "structure"}
            grounded = {**candidate, "root_symbol": "a",
                        "location": {"path": "a.py", "line": 1},
                        "taxonomy": "performance"}

            def fake_request(endpoint, payload, timeout):
                perspective = json.loads(payload["messages"][0]["content"])["perspective"]
                rows = ([candidate] if perspective == "correctness" else
                        [crossing] if perspective == "structure" else
                        [grounded] if perspective == "performance" else [])
                return {"usage": {"input_tokens": 50, "output_tokens": 1},
                        "stop_reason": "end_turn",
                        "content": [{"type": "text", "text": json.dumps({"candidates": rows})}]}

            issue_approval(manifest, sha, receipt, manifest_hash(manifest))
            with patch("modules.diagnosis.model._request", side_effect=fake_request):
                review = self.invoke(bundle, manifest_file, receipt, "--symbol", "a",
                                     "--final-output", str(root / "reports"), expected_code=3)
            self.assertEqual([(row["root_symbol"], row["location"]) for row in review["findings"]],
                             [("a", {"path": "a.py", "line": 1})])
            correctness = next(row for row in review["perspectives"]
                               if row["perspective"] == "correctness")
            self.assertEqual(correctness["status"], "completed")
            self.assertEqual(correctness["candidates"][0]["reason"],
                             "candidate_location_outside_context")
            structure = next(row for row in review["perspectives"]
                             if row["perspective"] == "structure")
            performance = next(row for row in review["perspectives"]
                               if row["perspective"] == "performance")
            self.assertEqual(structure["status"], "completed")
            self.assertEqual(structure["candidates"][0]["reason"],
                             "candidate_location_outside_context")
            self.assertEqual(performance["status"], "completed")
            final = verify_final_bundle(Path(review["final_source_only_bundle"]), bundle)
            self.assertEqual(len(final["findings"]), 1)
            self.assertEqual(final["findings"][0]["state"], "deferred")

    def test_full_scope_requires_one_approval_and_marks_unobserved_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, sha, _ = self.fixture(root, {"a.py": "def a(): return 1\n",
                                                "b.py": "def b(): return 2\n"})
            bundle, manifest, manifest_file, receipt = self.approved(
                root, repo, sha, 1, symbol=None, scope="full")
            with patch("modules.diagnosis.model._request", side_effect=AssertionError("network contacted")):
                with self.assertRaises(SystemExit) as denied:
                    self.invoke(bundle, manifest_file, receipt, "--scope", "full",
                                "--final-output", str(root / "reports"))
                self.assertEqual(denied.exception.code, 2)
                self.assertFalse(Path(str(receipt) + ".used").exists())
                self.assertFalse((root / "reports").exists())
                issue_approval(manifest, sha, receipt, manifest_hash(manifest))
                result = self.invoke(bundle, manifest_file, receipt, "--scope", "full",
                                     expected_code=3)
            coverage = result["diagnosis_coverage"]
            self.assertEqual(coverage["selected_paths"], ["a.py", "b.py"])
            self.assertEqual(coverage["analyzed_paths"], [])
            self.assertEqual(coverage["omitted_unknown_paths"], ["a.py", "b.py"])
            self.assertEqual(coverage["tokens_used"], 0)
            self.assertEqual(coverage["source_bytes"], 0)
            self.assertEqual(coverage["scope"], "full_tracked_python_git_commit")
            self.assertEqual([row["scope_id"] for row in result["perspectives"]],
                             ["module:a.py", "module:b.py"])
            self.assertTrue(all(row["status"] == "deferred" for entry in result["perspectives"]
                                for row in entry["perspectives"]))
            self.assertEqual(result["findings"], [])
            self.assertTrue(Path(str(receipt) + ".used").exists())

    def test_impact_keeps_out_of_scope_and_partial_budget_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, base, git = self.fixture(root, {"a.py": "def work(): return 1\n",
                                                  "b.py": "def other(): return 2\n",
                                                  "c.py": "def unrelated(): return 3\n"})
            (repo / "a.py").write_text("def work(): return 4\n")
            git("add", "a.py")
            git("-c", "user.name=A", "-c", "user.email=a@b.c", "commit", "-qm", "candidate")
            sha = git("rev-parse", "HEAD")
            bundle, manifest, manifest_file, receipt = self.approved(
                root, repo, sha, 4500, symbol=None, scope="impact",
                main_ref=base, candidate_ref=sha)
            issue_approval(manifest, sha, receipt, manifest_hash(manifest))
            calls = []

            def fake_request(endpoint, payload, timeout):
                calls.append(json.loads(payload["messages"][0]["content"])["context"])
                return {"usage": {"input_tokens": 1100, "output_tokens": 1},
                        "stop_reason": "end_turn",
                        "content": [{"type": "text", "text": '{"candidates": []}'}]}

            with patch("modules.diagnosis.model._request", side_effect=fake_request):
                result = self.invoke(bundle, manifest_file, receipt, "--scope", "impact",
                                     "--main-ref", base, "--candidate-ref", sha, expected_code=3)
            coverage = result["diagnosis_coverage"]
            self.assertEqual(result["base_sha"], base)
            self.assertEqual(coverage["scope"], "candidate_impact")
            self.assertEqual(coverage["selected_paths"], ["a.py"])
            self.assertEqual(coverage["omitted_unknown_paths"], ["a.py", "b.py", "c.py"])
            self.assertEqual(coverage["analyzed_paths"], [])
            self.assertEqual(coverage["tokens_used"], 1101 * len(calls))
            self.assertLessEqual(coverage["tokens_used"], manifest["limits"]["tokens"])
            self.assertTrue(calls)
            self.assertTrue(any(row["status"] == "deferred" for row in result["perspectives"][0]["perspectives"]))
            self.assertEqual(result["findings"], [])

    def test_full_multi_module_shares_budget_without_elevating(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, sha, _ = self.fixture(root, {"a.py": "def first(): return 1\n",
                                                "b.py": "def second(): return 2\n"})
            bundle, manifest, manifest_file, receipt = self.approved(
                root, repo, sha, 4000, symbol=None, scope="full")
            issue_approval(manifest, sha, receipt, manifest_hash(manifest))
            sent = []

            def fake_request(endpoint, payload, timeout):
                context = json.loads(payload["messages"][0]["content"])["context"]
                sent.append(context["nodes"][0]["path"])
                return {"usage": {"input_tokens": 999, "output_tokens": 1},
                        "stop_reason": "end_turn",
                        "content": [{"type": "text", "text": '{"candidates": []}'}]}

            with patch("modules.diagnosis.model._request", side_effect=fake_request):
                result = self.invoke(bundle, manifest_file, receipt, "--scope", "full", expected_code=3)
            self.assertTrue(sent)
            self.assertEqual(set(sent), {"a.py"})
            self.assertEqual(result["perspectives"][1]["scope_id"], "module:b.py")
            self.assertEqual({row["status"] for row in result["perspectives"][1]["perspectives"]},
                             {"deferred"})
            self.assertEqual(result["diagnosis_coverage"]["tokens_used"], len(sent) * 1000)
            self.assertLessEqual(result["diagnosis_coverage"]["tokens_used"], 4000)
            self.assertEqual(result["diagnosis_coverage"]["omitted_unknown_paths"], ["a.py", "b.py"])

    def test_full_modules_use_separate_contexts_and_complete_under_shared_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, sha, _ = self.fixture(root, {"a.py": "def first(): return 1\n",
                                                "b.py": "def second(): return 2\n"})
            bundle, manifest, manifest_file, receipt = self.approved(
                root, repo, sha, 20000, symbol=None, scope="full")
            issue_approval(manifest, sha, receipt, manifest_hash(manifest))
            sent = []

            def fake_request(endpoint, payload, timeout):
                context = json.loads(payload["messages"][0]["content"])["context"]
                sent.append((context["nodes"][0]["id"], json.loads(payload["messages"][0]["content"])["perspective"]))
                return {"usage": {"input_tokens": 99, "output_tokens": 1},
                        "stop_reason": "end_turn",
                        "content": [{"type": "text", "text": '{"candidates": []}'}]}

            with patch("modules.diagnosis.model._request", side_effect=fake_request):
                result = self.invoke(bundle, manifest_file, receipt, "--scope", "full")
            self.assertEqual([scope for scope, _ in sent], ["module:a.py"] * 5 + ["module:b.py"] * 5)
            self.assertEqual([perspective for _, perspective in sent],
                             ["structure", "correctness", "performance", "concurrency", "tests"] * 2)
            self.assertEqual(result["diagnosis_coverage"]["analyzed_paths"], ["a.py", "b.py"])
            self.assertEqual(result["diagnosis_coverage"]["omitted_unknown_paths"], [])
            self.assertEqual(result["diagnosis_coverage"]["diagnostic_completeness"], "unknown")

    def test_neighbor_context_cannot_create_finding_for_unaudited_module(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, sha, _ = self.fixture(root, {"a.py": "from b import second\ndef first(): return second()\n",
                                                "b.py": "def second(): return 2\n"})
            bundle, manifest, manifest_file, receipt = self.approved(
                root, repo, sha, 20000, symbol=None, scope="full")
            issue_approval(manifest, sha, receipt, manifest_hash(manifest))

            def fake_request(endpoint, payload, timeout):
                request = json.loads(payload["messages"][0]["content"])
                candidates = []
                if request["context"]["nodes"][0]["path"] == "a.py" and request["perspective"] == "structure":
                    evidence = request["context"]["source_evidence"]
                    self.assertIn("b.py", evidence)
                    candidates.append({
                        "root_symbol": "b.second", "mechanism": "unrelated module hypothesis",
                        "condition": "a condition", "impact": "some impact", "trigger": "a trigger",
                        "taxonomy": "structure", "severity": "Low",
                        "location": {"path": "b.py", "line": 1},
                        "evidence_ids": [evidence["b.py"]],
                        "next_action": {"action": "inspect", "oracle": "falsify with isolated test",
                                        "time_minutes": 5}})
                return {"usage": {"input_tokens": 99, "output_tokens": 1},
                        "stop_reason": "end_turn",
                        "content": [{"type": "text", "text": json.dumps({"candidates": candidates})}]}

            with patch("modules.diagnosis.model._request", side_effect=fake_request):
                result = self.invoke(bundle, manifest_file, receipt, "--scope", "full", expected_code=3)
            self.assertEqual(result["findings"], [])
            call = result["perspectives"][0]["perspectives"][0]
            self.assertEqual(call["status"], "completed")
            self.assertEqual(call["candidates"][0]["status"], "unverified")
            self.assertEqual(result["diagnosis_coverage"]["analyzed_paths"], ["a.py", "b.py"])
            self.assertEqual(result["diagnosis_coverage"]["omitted_unknown_paths"], [])


    def test_unknown_model_usage_stops_subsequent_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, sha, _ = self.fixture(root, {"a.py": "def first(): return 1\n",
                                                "b.py": "def second(): return 2\n"})
            bundle, manifest, manifest_file, receipt = self.approved(
                root, repo, sha, 20000, symbol=None, scope="full")
            issue_approval(manifest, sha, receipt, manifest_hash(manifest))
            response = {"stop_reason": "end_turn", "content": [{"type": "text",
                                                                 "text": '{"candidates": []}'}]}
            with patch("modules.diagnosis.model._request", return_value=response) as request:
                result = self.invoke(bundle, manifest_file, receipt, "--scope", "full", expected_code=3)
            self.assertEqual(request.call_count, 1)
            self.assertEqual(result["perspectives"][0]["perspectives"][0]["status"], "failed")
            self.assertEqual({row["status"] for row in result["perspectives"][1]["perspectives"]},
                             {"deferred"})
            self.assertEqual(result["diagnosis_coverage"]["omitted_unknown_paths"], ["a.py", "b.py"])
            self.assertEqual(result["findings"], [])

    def test_incomplete_and_invalid_json_preserve_usage_and_fail_separately(self):
        for response, reason in (
                ({"usage": {"input_tokens": 20, "output_tokens": 4},
                  "stop_reason": "incomplete", "content": []}, "response_incomplete"),
                ({"usage": {"input_tokens": 20, "output_tokens": 4},
                  "stop_reason": "end_turn", "content": [{"type": "text", "text": "{"}]},
                 "output_json_invalid")):
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                repo, sha, _ = self.fixture(root, {"a.py": "def a(): return 1\n"})
                bundle, manifest, file, receipt = self.approved(root, repo, sha, 20000)
                issue_approval(manifest, sha, receipt, manifest_hash(manifest))
                with patch("modules.diagnosis.model._request", return_value=response):
                    result = self.invoke(bundle, file, receipt, "--symbol", "a",
                                         "--final-output", str(root / "final"), expected_code=3)
                self.assertEqual(result["perspectives"][0]["reason"], reason)
                self.assertEqual(result["perspectives"][0]["tokens"], 24)
                sealed = verify_final_bundle(Path(result["final_source_only_bundle"]), bundle)
                self.assertEqual(sealed["run"]["model_audit"][0]["reason"], reason)

    def test_admission_failure_is_not_a_location_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, sha, _ = self.fixture(root, {"a.py": "def a(): return 1\n"})
            bundle, manifest, file, receipt = self.approved(root, repo, sha, 20000)
            evidence_id = verify_git_source(bundle)["evidence"][0]["id"]
            candidate = {"root_symbol": "a", "mechanism": "incorrect output",
                         "condition": "on call", "impact": "wrong answer", "trigger": "a()",
                         "taxonomy": "correctness", "severity": "Low",
                         "location": {"path": "a.py", "line": 1}, "evidence_ids": [evidence_id],
                         "next_action": {"action": "check return", "time_minutes": 1}}
            bad_source = {**candidate, "taxonomy": "structure",
                          "evidence_ids": ["wrong-source-id"]}

            def respond(endpoint, payload, timeout):
                perspective = json.loads(payload["messages"][0]["content"])["perspective"]
                rows = ([bad_source] if perspective == "structure" else
                        [candidate] if perspective == "correctness" else [])
                return {"usage": {"input_tokens": 20, "output_tokens": 4},
                        "stop_reason": "end_turn",
                        "content": [{"type": "text", "text": json.dumps({"candidates": rows})}]}

            issue_approval(manifest, sha, receipt, manifest_hash(manifest))
            with patch("modules.diagnosis.model._request", side_effect=respond):
                result = self.invoke(bundle, file, receipt, "--symbol", "a",
                                     "--final-output", str(root / "final"), expected_code=3)
            self.assertEqual(result["findings"], [])
            self.assertEqual(result["perspectives"][1]["status"], "completed")
            self.assertEqual(result["perspectives"][1]["candidates"][0]["reason"],
                             "candidate_schema_invalid")
            self.assertEqual(
                [(row["perspective"], row["reason"], row["candidate"])
                 for row in result["unverified_candidates"]],
                [("structure", "candidate_source_invalid", bad_source),
                 ("correctness", "candidate_schema_invalid", candidate)])
            for row in result["unverified_candidates"]:
                self.assertEqual(row["candidate_index"], 0)
                self.assertEqual(row["candidate_sha256"], context_hash(row["candidate"]))
                self.assertEqual(row["response_sha256"], next(
                    call["response_sha256"] for call in result["perspectives"]
                    if call["perspective"] == row["perspective"]))
            self.assertEqual(verify_final_bundle(Path(result["final_source_only_bundle"]),
                                                 bundle)["findings"], [])

    def test_runtime_failure_is_observed_before_review_and_not_confirmed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, sha, _ = self.fixture(root, {"a.py": "def a(): return 1\n"})
            bundle, manifest, file, receipt = self.approved(root, repo, sha, 30000)
            output = root / "runtime"
            manifest["model"]["transmitted_data"] += ["log", "evidence"]
            file.write_text(json.dumps(manifest))
            issue_approval(manifest, sha, receipt, manifest_hash(manifest))

            def failed_execution(verified, approved, digest, destination, *, run_deadline):
                destination.mkdir(mode=0o700)
                stdout, stderr = b"", b"AssertionError: got 2\n"
                (destination / "work-0.stdout").write_bytes(stdout)
                (destination / "work-0.stderr").write_bytes(stderr)
                trace = {"schema_version": "approved-execution-v1", "snapshot_sha": sha,
                         "source_run_id": verified["run"]["id"], "manifest_sha256": digest,
                         "runtime_attested": False,
                         "runtime_provenance": "caller_declared_unattested",
                         "limitations": "A container trace is not an oracle or confirmed finding.",
                         "nodes": [{"node_id": "work", "trial": 0, "status": "failed",
                                    "reason": "nonzero_exit", "exit_code": 1, "wall_seconds": 0.1,
                                    "command_argv": approved["nodes"][0]["argv"],
                                    "image_digest": approved["image_digest"],
                                    "manifest_sha256": digest, "stdout_path": "work-0.stdout",
                                    "stderr_path": "work-0.stderr",
                                    "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
                                    "stderr_sha256": hashlib.sha256(stderr).hexdigest()}]}
                (destination / "execution.json").write_text(
                    json.dumps(trace, sort_keys=True, separators=(",", ":")) + "\n")
                return trace

            seen = []
            def review(endpoint, payload, timeout):
                seen.append(json.loads(payload["messages"][0]["content"])["runtime_context"])
                return {"usage": {"input_tokens": 30, "output_tokens": 10},
                        "stop_reason": "end_turn",
                        "content": [{"type": "text", "text": '{"candidates": []}'}]}

            with patch.object(diagnose_approved, "validate_runtime_host"), patch.object(
                    diagnose_approved, "execute_nodes", side_effect=failed_execution), patch(
                    "modules.diagnosis.model._request", side_effect=review):
                result = self.invoke(bundle, file, receipt, "--symbol", "a",
                                     "--runtime-output", str(output),
                                     "--final-output", str(root / "final"), expected_code=3)
            self.assertEqual(len(seen), 5)
            self.assertIn("AssertionError", seen[0]["nodes"][0]["stderr"])
            self.assertEqual(seen[0]["nodes"][0]["exit_code"], 1)
            final = verify_final_bundle(Path(result["final_source_only_bundle"]), bundle,
                                        runtime_trace_dir=output)
            self.assertEqual(final["report"]["confirmed_count"], 0)
            self.assertEqual(final["run"]["runtime_trace"]["nodes"][0]["status"], "failed")
            (output / "work-0.stderr").write_bytes(b"altered")
            with self.assertRaises(ValueError):
                verify_final_bundle(Path(result["final_source_only_bundle"]), bundle,
                                    runtime_trace_dir=output)

    def test_runtime_transmission_scope_denied_before_consumption(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, sha, _ = self.fixture(root, {"a.py": "def a(): return 1\n"})
            bundle, manifest, file, receipt = self.approved(root, repo, sha, 20000)
            issue_approval(manifest, sha, receipt, manifest_hash(manifest))
            with patch.object(diagnose_approved, "validate_runtime_host"), patch.object(
                    diagnose_approved, "execute_nodes",
                    side_effect=AssertionError("must not execute")), patch(
                    "modules.diagnosis.model._request",
                    side_effect=AssertionError("must not transmit")):
                with self.assertRaises(SystemExit) as denied:
                    self.invoke(bundle, file, receipt, "--symbol", "a",
                                "--runtime-output", str(root / "runtime"))
            self.assertEqual(denied.exception.code, 2)
            self.assertFalse(Path(str(receipt) + ".used").exists())

    def test_large_or_empty_neighbor_does_not_abort_complete_primary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, sha, _ = self.fixture(root, {
                "a.py": "import b\nimport c\ndef first(): return 1\n",
                "b.py": "VALUE = " + repr("x" * 25_000) + "\n",
                "c.py": ""})
            bundle, manifest, manifest_file, receipt = self.approved(
                root, repo, sha, 20000, symbol=None, scope="full")
            issue_approval(manifest, sha, receipt, manifest_hash(manifest))
            seen = []

            def fake_request(endpoint, payload, timeout):
                context = json.loads(payload["messages"][0]["content"])["context"]
                seen.append(context)
                self.assertEqual(context["nodes"][0]["id"], "module:a.py")
                self.assertTrue(context["truncated"])
                self.assertEqual({node["path"] for node in context["nodes"]}, {"a.py"})
                self.assertEqual(set(context["source_evidence"]), {"a.py"})
                return {"usage": {"input_tokens": 99, "output_tokens": 1},
                        "stop_reason": "end_turn",
                        "content": [{"type": "text", "text": '{"candidates": []}'}]}

            with patch("modules.diagnosis.model._request", side_effect=fake_request):
                result = self.invoke(bundle, manifest_file, receipt, "--scope", "full", expected_code=3)
            self.assertEqual(len(seen), 5)
            self.assertEqual(result["diagnosis_coverage"]["analyzed_paths"], ["a.py"])
            self.assertEqual(result["diagnosis_coverage"]["omitted_unknown_paths"], ["b.py", "c.py"])
            self.assertEqual(result["findings"], [])

    @staticmethod
    def model_analysis(context):
        return {"mode": "five", "roles": list(PERSPECTIVES), "scope": "full",
                "symbol": None, "base_sha": None, "context_policy": "git-ast-context-v1",
                "contexts": [{"scope_id": "full", "sha256": context_hash(context)}]}

    def test_measured_input_budget_reaches_fifth_perspective(self):
        parts = [f"def f{i}():\n    return {i}\n\n" for i in range(6)]
        source = "".join(parts)
        digest = hashlib.sha256(source.encode()).hexdigest()
        metadata = {"path": "unit.py", "source_sha256": digest, "blob_oid": "b" * 40}
        nodes = [{"id": "module:unit.py", "kind": "module", "line": 1,
                  "source_slice": source, **metadata}]
        nodes.extend({"id": f"function:unit.py:f{i}", "kind": "function", "line": i * 3 + 1,
                      "source_slice": part, **metadata} for i, part in enumerate(parts))
        context = {"nodes": nodes, "edges": [], "truncated": False}
        evidence = [{"path": "unit.py", "id": "source-id", "source_sha256": digest}]
        manifest = {"schema_version": "run-manifest-v3",
                    "model": {"endpoint": "http://127.0.0.1:10531/v1/responses",
                              "name_version": "gpt-6-luna", "prompt_sha256": prompt_hash("five"),
                              "transmitted_data": ["source", "context"]},
                    "network": {"model": True}, "limits": {"wall_seconds": 30, "tokens": 12000}}
        manifest["analysis"] = self.model_analysis(context)
        sent = []

        def fake_request(endpoint, payload, timeout):
            sent.append(json.loads(payload["input"][0]["content"])["perspective"])
            return {"usage": {"input_tokens": 899, "output_tokens": 1},
                    "stop_reason": "end_turn",
                    "content": [{"type": "text", "text": '{"candidates": []}'}]}

        with patch("modules.diagnosis.model._request", side_effect=fake_request):
            candidates, audit = analyze(context, evidence, manifest)
        self.assertEqual(candidates, [])
        self.assertEqual(sent, ["structure", "correctness", "performance", "concurrency", "tests"])
        self.assertEqual([row["status"] for row in audit], ["completed"] * 5)

    def test_untrusted_usage_cannot_release_shared_budget(self):
        evidence = [{"path": "worker.py", "id": "source-id", "source_sha256": "a" * 64}]
        context = {"nodes": [{"path": "worker.py", "source_slice": "def work(): return 1",
                              "source_sha256": "a" * 64}], "edges": [], "truncated": False}
        manifest = {"schema_version": "run-manifest-v3",
                    "model": {"endpoint": "https://api.anthropic.com/v1/messages",
                              "name_version": "pinned-model", "prompt_sha256": prompt_hash("five"),
                              "transmitted_data": ["source", "context"]},
                    "network": {"model": True}, "limits": {"wall_seconds": 30, "tokens": 5000}}
        manifest["analysis"] = self.model_analysis(context)
        for input_tokens, reason in ((0, "usage_invalid"), (5001, "budget_exceeded")):
            with self.subTest(reason=reason), patch(
                    "modules.diagnosis.model._request",
                    return_value={"usage": {"input_tokens": input_tokens, "output_tokens": 1},
                                  "stop_reason": "end_turn",
                                  "content": [{"type": "text", "text": '{"candidates": []}'}]}) as request:
                candidates, audit = analyze(context, evidence, manifest)
            self.assertEqual(candidates, [])
            self.assertEqual(request.call_count, 1)
            self.assertEqual((audit[0]["status"], audit[0]["reason"]), ("failed", reason))
            self.assertEqual([row["status"] for row in audit[1:]], ["deferred"] * 4)

    def test_insufficient_token_budget_defers_all_perspectives_without_transmission(self):
        evidence = [{"path": "worker.py", "id": "source-id", "source_sha256": "a" * 64}]
        context = {"nodes": [{"path": "worker.py", "source_slice": "def work(): return 1",
                              "source_sha256": "a" * 64}], "edges": [], "truncated": False}
        manifest = {"schema_version": "run-manifest-v3",
                    "model": {"endpoint": "https://api.anthropic.com/v1/messages",
                              "name_version": "pinned-model", "prompt_sha256": prompt_hash("five"),
                              "transmitted_data": ["source", "context"]},
                    "network": {"model": True}, "limits": {"wall_seconds": 30, "tokens": 1}}
        manifest["analysis"] = self.model_analysis(context)
        candidates, audit = analyze(context, evidence, manifest)
        self.assertEqual(candidates, [])
        self.assertEqual(len(audit), 5)
        self.assertEqual({row["status"] for row in audit}, {"deferred"})
        self.assertEqual({row["reason"] for row in audit}, {"budget_exhausted"})

    def test_prompt_hash_and_no_approval_never_contact_model(self):
        command = [sys.executable, str(ROOT / "src" / "diagnose_approved.py")]
        fingerprint = subprocess.run([*command, "--prompt-hash"], capture_output=True, text=True)
        self.assertEqual(fingerprint.returncode, 0, fingerprint.stderr)
        self.assertEqual(fingerprint.stdout.strip(), prompt_hash("five"))
        for mode, flag in (("boundary", "--boundary-review"),
                           ("single", "--single-baseline"), ("plain", "--plain-baseline")):
            with self.subTest(mode=mode):
                selected = subprocess.run([*command, flag, "--prompt-hash"],
                                          capture_output=True, text=True)
                self.assertEqual(selected.returncode, 0, selected.stderr)
                self.assertEqual(selected.stdout.strip(), prompt_hash(mode))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            def git(*args):
                return subprocess.run(["git", "-C", str(repo), *args], check=True,
                                      capture_output=True, text=True).stdout.strip()
            git("init", "-q")
            (repo / "sample.py").write_text("def work(): return 1\n")
            git("add", "sample.py")
            git("-c", "user.name=A", "-c", "user.email=a@b.c", "commit", "-qm", "frozen")
            sha = git("rev-parse", "HEAD")
            bundle = write_source_run(root / "source", str(repo), scan(repo, sha))
            bounds = {"wall_seconds": 30, "cpu_seconds": 30, "memory_bytes": 1048576,
                      "tokens": 1000, "tool_seconds": 30}
            analysis, _, _ = prepare_analysis(verify_git_source(bundle), symbol="work")
            manifest = {"schema_version": "run-manifest-v3", "snapshot_sha": sha,
                        "analysis": analysis,
                        "image_digest": "sha256:" + "a" * 64,
                        "tools": ["python"],
                        "nodes": [{"id": "work", "argv": ["python", "sample.py"],
                                   "cwd": "/workspace", "workload": "sample.py",
                                   "trigger": "always", "tool": "python"}],
                        "limits": {**bounds, "per_node": {"work": bounds}},
                        "network": {"dependency": False, "model": True, "workload": False},
                        "writable_paths": ["/work/evidence"],
                        "model": {"endpoint": "https://api.anthropic.com/v1/messages",
                                  "name_version": "pinned-model", "prompt_sha256": prompt_hash("five"),
                                  "transmitted_data": ["source", "context"]}}
            file = root / "manifest.json"
            file.write_text(json.dumps(manifest))
            receipt = root / "missing-approval"
            denied = subprocess.run([*command, str(bundle), str(file), str(receipt),
                                     "--symbol", "work", "--final-output", str(root / "reports"),
                                     "--response-output", str(root / "responses")],
                                    capture_output=True, text=True)
            self.assertEqual(denied.returncode, 2)
            self.assertIn("approval", denied.stderr)
            self.assertFalse((root / "reports").exists())
            self.assertFalse(Path(str(receipt) + ".used").exists())


if __name__ == "__main__":
    unittest.main()
