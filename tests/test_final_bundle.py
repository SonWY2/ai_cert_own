"""Final reports preserve source lineage and cannot launder provisional claims."""

import copy
import hashlib
import json
import os
import pty
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from modules.diagnosis.model import PERSPECTIVES, prompt_hash  # noqa: E402
from modules.diagnosis.plan import context_hash, prepare_analysis  # noqa: E402
from modules.evidence.authenticity import verify_git_source  # noqa: E402
from modules.findings.actions import append_action  # noqa: E402
from modules.evidence.final_bundle import verify_final_bundle, write_final_bundle  # noqa: E402
from modules.evidence.provenance import verify_source_run, write_source_run  # noqa: E402
from modules.git_modes import plan_candidate  # noqa: E402
from modules.run_policy import manifest_hash  # noqa: E402
from modules.findings.admission import admit  # noqa: E402
from modules.static_scan.orchestrator import scan  # noqa: E402


class FinalBundleTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        (self.repo / "worker.py").write_text("def busy():\n    return 3\n")
        (self.repo / "helper.py").write_text("def helper():\n    return 1\n")
        self.git("add", "-A")
        self.git("-c", "user.email=a@b.c", "-c", "user.name=A", "commit", "-qm", "fixture")
        self.source = write_source_run(self.root / "source", str(self.repo), scan(self.repo, "HEAD"))
        self.source_bytes = {p.name: p.read_bytes() for p in self.source.iterdir()}
        self.source_records = verify_source_run(self.source)
        source_id = next(row["id"] for row in self.source_records["evidence"] if row["path"] == "worker.py")
        self.candidate = {"root_symbol": "busy", "mechanism": "repeated work may be slow",
                          "condition": "repeated requests", "impact": "latency may grow",
                          "trigger": "many requests", "taxonomy": "performance", "severity": "High",
                          "location": {"path": "worker.py", "line": 1},
                          "evidence_ids": [source_id], "perspective": "performance",
                          "next_action": {"action": "benchmark under a pinned workload",
                                          "oracle": "latency is bounded by 50 ms", "time_minutes": 7}}
        self.findings = admit(self.source, [self.candidate])
        self.output = self.root / "final"

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)

    @staticmethod
    def seal(row):
        row["content_hash"] = hashlib.sha256(json.dumps(
            {key: value for key, value in row.items() if key != "content_hash"},
            sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode()).hexdigest()
        return json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode() + b"\n"

    def manifest(self):
        bounds = {"wall_seconds": 30, "cpu_seconds": 30, "memory_bytes": 1024 * 1024,
                  "tokens": 100, "tool_seconds": 30}
        return {"schema_version": "run-manifest-v3", "analysis": None,
                "snapshot_sha": self.source_records["run"]["commit"],
                "image_digest": "sha256:" + "b" * 64, "tools": ["pytest"],
                "nodes": [{"id": "focused", "argv": ["pytest", "tests/test_worker.py"],
                           "cwd": "/workspace", "workload": "tests/test_worker.py",
                           "trigger": "approved focused test", "tool": "pytest"}],
                "limits": {**bounds, "per_node": {"focused": bounds}},
                "network": {"dependency": False, "model": False, "workload": False},
                "writable_paths": ["/work/evidence"],
                "model": {"endpoint": None, "name_version": None,
                          "prompt_sha256": None, "transmitted_data": []}}

    def model_manifest(self, *, mode="five", symbol="busy", scope=None, source=None,
                       main_ref=None, candidate_ref=None):
        manifest = self.manifest()
        verified = verify_git_source(source or self.source)
        manifest["snapshot_sha"] = verified["run"]["commit"]
        manifest["analysis"], _, _ = prepare_analysis(
            verified, mode=mode, symbol=symbol, scope=scope,
            main_ref=main_ref, candidate_ref=candidate_ref)
        manifest["network"]["model"] = True
        manifest["model"] = {
            "endpoint": "https://api.anthropic.com/v1/messages",
            "name_version": "model-approved-by-owner",
            "prompt_sha256": prompt_hash(mode),
            "transmitted_data": ["source", "context"]}
        return manifest

    def candidate_row(self, candidate=..., *, index=0, reason=None):
        candidate = self.candidate if candidate is ... else candidate
        return {"index": index, "candidate": copy.deepcopy(candidate),
                "candidate_sha256": context_hash(candidate),
                "status": "unverified" if reason else "accepted", "reason": reason,
                "finding_id": None if reason else self.findings[0]["id"]}

    def model_audit(self, candidates=None):
        rows = []
        for perspective in PERSPECTIVES:
            if perspective == "performance":
                rows.append({"perspective": perspective, "status": "completed",
                             "reason": None, "tokens": 3, "request_sha256": "a" * 64,
                             "response_sha256": "b" * 64, "wall_seconds": 0.1,
                             "candidates": [self.candidate_row()] if candidates is None else candidates})
            elif perspective == "tests":
                rows.append({"perspective": perspective, "status": "failed",
                             "reason": "output_json_invalid",
                             "tokens": 2, "request_sha256": "c" * 64,
                             "response_sha256": "d" * 64, "wall_seconds": 0.2, "candidates": []})
            elif perspective == "correctness":
                rows.append({"perspective": perspective, "status": "failed",
                             "reason": "ValueError", "tokens": 0,
                             "request_sha256": "e" * 64, "wall_seconds": 0.3, "candidates": []})
            else:
                rows.append({"perspective": perspective, "status": "deferred",
                             "reason": "budget_exhausted", "tokens": 0, "candidates": []})
        return rows

    def completed_audit(self, candidates, perspective="performance"):
        return [{"perspective": role, "status": "completed", "reason": None,
                 "tokens": 3, "request_sha256": "a" * 64,
                 "response_sha256": "b" * 64, "wall_seconds": 0.1,
                 "candidates": candidates if role == perspective else []}
                for role in PERSPECTIVES]

    def test_completed_calls_preserve_partial_rows_and_actual_role(self):
        raw = {**self.candidate, "taxonomy": "tests", "perspective": "correctness"}
        admitted = admit(self.source, [{**raw, "perspective": "performance"}])
        candidates = [
            self.candidate_row(raw),
            self.candidate_row(None, index=1, reason="candidate_schema_invalid"),
            self.candidate_row("not an object", index=2, reason="candidate_schema_invalid"),
            self.candidate_row({**raw, "evidence_ids": ["invented"]}, index=3,
                               reason="candidate_source_invalid"),
        ]
        audit = self.completed_audit(candidates)
        bundle = write_final_bundle(self.source, admitted, self.output,
                                    manifest=self.model_manifest(), model_audit=audit)
        result = verify_final_bundle(bundle, self.source)
        self.assertEqual(result["report"]["analysis_status"], "incomplete")
        self.assertEqual(result["report"]["candidate_counts"], {"accepted": 1, "unverified": 3})
        self.assertEqual(result["report"]["confirmed_count"], 0)
        self.assertEqual(result["findings"][0]["perspectives"], ["performance"])
        self.assertEqual(result["findings"][0]["taxonomy"], "tests")
        self.assertEqual(result["findings"][0]["state"], "deferred")
        self.assertTrue(all(row["status"] == "completed" for row in result["run"]["model_audit"]))
        self.assertEqual(result["run"]["model_audit"][2]["candidates"], candidates)
        for index in (1, 2, 3):
            corrupted = copy.deepcopy(audit)
            corrupted[2]["candidates"][index].update(
                status="accepted", reason=None, finding_id=admitted[0]["id"])
            with self.subTest(index=index), self.assertRaises(ValueError):
                write_final_bundle(self.source, admitted, self.output,
                                   manifest=self.model_manifest(), model_audit=corrupted)

    def test_accepted_rows_reconstruct_exact_fields_before_merging(self):
        manifest = self.model_manifest()
        original = self.candidate_row()
        changed = [
            {**original, "index": 1},
            {**original, "index": True},
            {**original, "candidate_sha256": "0" * 64},
            {**original, "finding_id": "F" + "0" * 24},
            self.candidate_row({**self.candidate, "severity": "Critical"}),
            self.candidate_row({**self.candidate, "location": {"path": "worker.py", "line": 2}}),
            self.candidate_row({**self.candidate, "trigger": "different trigger"}),
            self.candidate_row({**self.candidate, "next_action": {
                **self.candidate["next_action"], "oracle": "different oracle"}}),
        ]
        for entry in changed:
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                write_final_bundle(self.source, self.findings, self.output, manifest=manifest,
                                   model_audit=self.completed_audit([entry]))
        invalid_duplicate = self.candidate_row({
            **self.candidate, "location": {"path": "worker.py", "line": 999}}, index=1)
        with self.assertRaises(ValueError):
            write_final_bundle(self.source, self.findings, self.output, manifest=manifest,
                               model_audit=self.completed_audit([original, invalid_duplicate]))
        for status in ("failed", "deferred"):
            audit = self.model_audit()
            audit[0]["candidates"] = [original]
            if status == "failed":
                audit[0] = {**audit[2], "perspective": "structure",
                            "status": "failed", "reason": "output_json_invalid"}
            with self.subTest(status=status), self.assertRaises(ValueError):
                write_final_bundle(self.source, self.findings, self.output,
                                   manifest=manifest, model_audit=audit)

    def test_compatible_rows_merge_without_losing_call_roles(self):
        first = {**self.candidate, "severity": "Low", "perspective": "spoofed",
                 "location": {"path": "worker.py", "line": 2}}
        second = {**self.candidate, "severity": "Critical", "perspective": "spoofed"}
        admitted = admit(self.source, [
            {**first, "perspective": "performance"}, {**second, "perspective": "tests"}])
        audit = self.completed_audit([self.candidate_row(first)])
        audit[4]["candidates"] = [self.candidate_row(second)]
        bundle = write_final_bundle(self.source, admitted, self.output,
                                    manifest=self.model_manifest(), model_audit=audit)
        result = verify_final_bundle(bundle, self.source)
        self.assertEqual(result["report"]["analysis_status"], "completed")
        self.assertEqual(result["report"]["candidate_counts"], {"accepted": 2, "unverified": 0})
        self.assertEqual(result["findings"][0]["perspectives"], ["performance", "tests"])
        self.assertEqual(result["findings"][0]["location"]["line"], 1)
        self.assertEqual(result["findings"][0]["severity"], "Critical")
        self.assertEqual(result["report"]["confirmed_count"], 0)

    def test_conflicting_identity_cannot_retain_one_accepted_row(self):
        conflict = {**self.candidate, "taxonomy": "tests"}
        unrelated = {**self.candidate, "mechanism": "an independent risk"}
        admitted = admit(self.source, [unrelated])
        independent = self.candidate_row(unrelated, index=2)
        independent["finding_id"] = admitted[0]["id"]
        candidates = [
            self.candidate_row(reason="candidate_identity_conflict"),
            self.candidate_row(conflict, index=1, reason="candidate_identity_conflict"),
            independent,
        ]
        manifest = self.model_manifest()
        audit = self.completed_audit(candidates)
        bundle = write_final_bundle(self.source, admitted, self.output,
                                    manifest=manifest, model_audit=audit)
        result = verify_final_bundle(bundle, self.source)
        self.assertEqual([row["id"] for row in result["findings"]], [admitted[0]["id"]])
        self.assertEqual(result["report"]["candidate_counts"], {"accepted": 1, "unverified": 2})
        candidates[0] = self.candidate_row()
        with self.assertRaises(ValueError):
            write_final_bundle(self.source, admit(self.source, [self.candidate, unrelated]),
                               self.output, manifest=manifest, model_audit=audit)

    def test_embedded_candidate_tampering_fails_even_with_resealed_run(self):
        manifest = self.model_manifest()
        bundle = write_final_bundle(self.source, self.findings, self.output,
                                    manifest=manifest,
                                    model_audit=self.completed_audit([self.candidate_row()]))
        run_path = bundle / "run.json"
        original = json.loads(run_path.read_bytes())
        for redigest in (False, True):
            run = copy.deepcopy(original)
            entry = run["model_audit"][2]["candidates"][0]
            entry["candidate"]["trigger"] = "forged trigger"
            if redigest:
                entry["candidate_sha256"] = context_hash(entry["candidate"])
            run_path.write_bytes(self.seal(run))
            with self.subTest(redigest=redigest), self.assertRaises(ValueError):
                verify_final_bundle(bundle, self.source)
        run_path.write_bytes(self.seal(original))

    def test_final_rejects_old_manifest_and_cross_mode_prompt_hash(self):
        for mode in ("five", "boundary"):
            manifest = self.model_manifest(mode=mode)
            for old_version in ("run-manifest-v28", "run-manifest-v2"):
                outdated = copy.deepcopy(manifest)
                outdated["schema_version"] = old_version
                with self.subTest(mode=mode, version=old_version), self.assertRaisesRegex(
                        ValueError, "unsupported manifest version"):
                    write_final_bundle(self.source, [], self.output,
                                       manifest=outdated, model_audit=[])
            manifest["model"]["prompt_sha256"] = prompt_hash(
                "boundary" if mode == "five" else "five")
            with self.subTest(mode=mode, mismatch=True), self.assertRaisesRegex(
                    ValueError, "prompt"):
                write_final_bundle(self.source, [], self.output,
                                   manifest=manifest, model_audit=[])

    def test_model_disabled_v3_manifest_seals_without_audit(self):
        bundle = write_final_bundle(self.source, [], self.output, manifest=self.manifest())
        verified = verify_final_bundle(bundle, self.source)
        self.assertEqual(verified["run"]["manifest"]["schema_version"], "run-manifest-v3")
        self.assertEqual(verified["run"]["schema_version"], "evidence-contract-v2")
        self.assertIsNone(verified["run"]["model_audit"])

    def test_final_audit_requires_first_five_roles_in_order(self):
        manifest = self.model_manifest(mode="boundary")
        audit = self.completed_audit([]) + [{
            "perspective": "assumptions", "status": "completed", "reason": None,
            "tokens": 3, "request_sha256": "a" * 64,
            "response_sha256": "b" * 64, "wall_seconds": 0.1, "candidates": []}]
        bundle = write_final_bundle(self.source, [], self.output,
                                    manifest=manifest, model_audit=audit)
        self.assertEqual([row["perspective"] for row in verify_final_bundle(
            bundle, self.source)["run"]["model_audit"]],
            list(PERSPECTIVES) + ["assumptions"])
        shuffled = copy.deepcopy(audit)
        shuffled[0], shuffled[1] = shuffled[1], shuffled[0]
        with self.assertRaisesRegex(ValueError, "perspective"):
            write_final_bundle(self.source, [], self.output,
                               manifest=manifest, model_audit=shuffled)

    def test_single_and_plain_baselines_cannot_create_final_bundle(self):
        for mode in ("single", "plain"):
            manifest = self.model_manifest(mode=mode)
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, "Single baselines"):
                write_final_bundle(self.source, [], self.output, manifest=manifest, model_audit=[])

    def test_seal_cli_reports_partial_rows_as_exit_three(self):
        manifest = self.model_manifest()
        audit = self.completed_audit([
            self.candidate_row(),
            self.candidate_row(None, index=1, reason="candidate_schema_invalid"),
        ])
        manifest_path = self.root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        review_path = self.root / "review.json"
        review_path.write_text(json.dumps({
            "stage": "provisional_hypotheses", "source_run_id": self.source_records["run"]["id"],
            "findings": self.findings, "perspectives": audit}))
        result = subprocess.run([
            sys.executable, str(ROOT / "src" / "seal_report.py"), str(self.source),
            str(review_path), str(self.output), "--run-manifest", str(manifest_path)],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 3, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["analysis_status"], "incomplete")
        sealed = verify_final_bundle(Path(output["bundle"]), self.source)
        self.assertEqual(sealed["report"]["candidate_counts"], {"accepted": 1, "unverified": 1})
        self.assertEqual(sealed["report"]["confirmed_count"], 0)

    def test_batch_row_failure_does_not_erase_completed_call_coverage(self):
        manifest = self.model_manifest(symbol=None, scope="full")
        selected = sorted(row["path"] for row in self.source_records["evidence"])
        rows = [{"scope_id": "module:" + path, "perspectives": self.completed_audit(
            [self.candidate_row()] if path == "worker.py" else [
                self.candidate_row(None, reason="candidate_schema_invalid")])}
                for path in selected]
        coverage = {"scope": "full_tracked_python_git_commit", "base_sha": None,
                    "selected_paths": selected, "analyzed_paths": selected,
                    "omitted_unknown_paths": [], "source_bytes": 100,
                    "tokens_used": 30, "diagnostic_completeness": "unknown"}
        bundle = write_final_bundle(self.source, self.findings, self.output, manifest=manifest,
                                    model_audit=rows, diagnosis_coverage=coverage)
        result = verify_final_bundle(bundle, self.source)
        self.assertEqual(result["report"]["coverage"]["diagnosis"]["analyzed_paths"], selected)
        self.assertEqual(result["report"]["analysis_status"], "incomplete")
        self.assertEqual(result["report"]["candidate_counts"], {"accepted": 1, "unverified": 1})
        self.assertEqual(result["report"]["confirmed_count"], 0)

    def test_boundary_audit_binds_roles(self):
        manifest = self.model_manifest(mode="boundary")
        candidates = [{**self.candidate, "perspective": "assumptions"}]
        findings = admit(self.source, candidates)
        extra = {"perspective": "assumptions", "status": "completed", "reason": None,
                 "tokens": 4, "request_sha256": "f" * 64,
                 "response_sha256": "1" * 64, "wall_seconds": 0.1,
                 "candidates": [self.candidate_row(candidates[0])]}
        valid = self.model_audit(candidates=[]) + [extra]
        bundle = write_final_bundle(self.source, findings, self.output,
                                    manifest=manifest, model_audit=valid)
        verified = verify_final_bundle(bundle, self.source)
        self.assertEqual(verified["findings"][0]["perspectives"], ["assumptions"])
        self.assertEqual(verified["findings"][0]["taxonomy"], "performance")
        self.assertEqual(verified["report"]["confirmed_count"], 0)
        for rows in (
                self.model_audit(),
                valid + [extra],
                self.model_audit() + [{**extra, "perspective": "invented"}],
                self.model_audit() + [{**extra, "status": "failed", "reason": "output_json_invalid"}]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                write_final_bundle(self.source, findings, self.output,
                                   manifest=manifest, model_audit=rows)
        with self.assertRaises(ValueError):
            write_final_bundle(self.source, findings, self.output,
                               manifest=self.model_manifest(), model_audit=valid)

    def test_runtime_trace_requires_log_replay_and_cannot_confirm_a_finding(self):
        manifest = self.manifest()
        manifest["nodes"][0]["trigger"] = "always"
        manifest["nodes"][0]["argv"] = ["pytest", "worker.py"]
        manifest["nodes"][0]["workload"] = "worker.py"
        trace_dir = self.root / "runtime"
        trace_dir.mkdir(mode=0o700)
        stderr = b"docker: image unavailable\n"
        (trace_dir / "focused-0.stdout").write_bytes(b"")
        (trace_dir / "focused-0.stderr").write_bytes(stderr)
        trace = {
            "schema_version": "approved-execution-v1",
            "snapshot_sha": self.source_records["run"]["commit"],
            "source_run_id": self.source_records["run"]["id"],
            "manifest_sha256": manifest_hash(manifest),
            "runtime_attested": False,
            "runtime_provenance": "caller_declared_unattested",
            "limitations": "A container trace is not an oracle or confirmed finding.",
            "nodes": [{"node_id": "focused", "trial": 0, "status": "failed",
                       "reason": "nonzero_exit", "exit_code": 125, "wall_seconds": 0.5,
                       "command_argv": manifest["nodes"][0]["argv"],
                       "image_digest": manifest["image_digest"],
                       "manifest_sha256": manifest_hash(manifest),
                       "stdout_path": "focused-0.stdout", "stderr_path": "focused-0.stderr",
                       "stdout_sha256": hashlib.sha256(b"").hexdigest(),
                       "stderr_sha256": hashlib.sha256(stderr).hexdigest()}],
        }
        (trace_dir / "execution.json").write_text(
            json.dumps(trace, sort_keys=True, separators=(",", ":")) + "\n")
        bundle = write_final_bundle(self.source, self.findings, self.output, manifest=manifest,
                                    runtime_trace_dir=trace_dir)
        confirmed = verify_final_bundle(bundle, self.source, runtime_trace_dir=trace_dir)
        self.assertEqual(confirmed["run"]["runtime_trace"], trace)
        self.assertEqual(confirmed["report"]["coverage"]["runtime_execution"],
                         "caller_declared_unattested")
        self.assertEqual(confirmed["report"]["confirmed_count"], 0)
        with self.assertRaisesRegex(ValueError, "Invalid final bundle lineage"):
            verify_final_bundle(bundle, self.source)
        (trace_dir / "focused-0.stderr").write_bytes(b"altered\n")
        with self.assertRaisesRegex(ValueError, "Invalid final bundle lineage"):
            verify_final_bundle(bundle, self.source, runtime_trace_dir=trace_dir)

    def test_confirmed_owner_action_creates_distinct_immutable_successor(self):
        initial = write_final_bundle(self.source, self.findings, self.output)
        original = (initial / "report.json").read_bytes()
        directory = self.root / "owner-actions"
        directory.mkdir(mode=0o700)
        saved = append_action(self.source, self.findings, self.findings[0]["id"],
                              "verify", directory, explicit_owner_confirmation=True)
        successor = write_final_bundle(self.source, self.findings, self.output,
                                       action_directory=directory)
        self.assertNotEqual(initial, successor)
        self.assertEqual((initial / "report.json").read_bytes(), original)
        replay = verify_final_bundle(successor, self.source)
        self.assertEqual(replay["run"]["action_hash"], hashlib.sha256(json.dumps(
            [saved], sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest())
        self.assertEqual(replay["actions"][0]["source_action"]["id"], saved["id"])
        self.assertEqual(replay["actions"][0]["run_id"], replay["run"]["id"])
        self.assertEqual(replay["report"]["user_actions"], "owner_declared_local")
        self.assertEqual(replay["report"]["confirmed_count"], 0)
        path = successor / "actions.jsonl"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "Noncanonical|Invalid final"):
            verify_final_bundle(successor, self.source)

    def test_owner_action_requires_terminal_and_preserves_deferred_report(self):
        bundle = write_final_bundle(self.source, self.findings, self.output)
        report_before = (bundle / "report.json").read_bytes()
        directory = self.root / "actions"
        directory.mkdir(mode=0o700)
        command = [sys.executable, str(ROOT / "src" / "record_final_action.py"),
                   str(self.source), str(bundle), str(directory),
                   self.findings[0]["id"], "verify"]
        rejected = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("interactive terminal", rejected.stderr)
        self.assertFalse(list(directory.iterdir()))
        master, slave = pty.openpty()
        try:
            process = subprocess.Popen(command, stdin=slave, stdout=slave, stderr=slave)
            os.close(slave)
            time.sleep(0.1)
            os.write(master, f"{self.findings[0]['id']}\nverify\n".encode())
            self.assertEqual(process.wait(timeout=10), 0)
            output = os.read(master, 8192).decode()
        finally:
            os.close(master)
        self.assertIn('"latest_action": "verify"', output)
        self.assertEqual((bundle / "report.json").read_bytes(), report_before)
        self.assertEqual(verify_final_bundle(bundle, self.source)["report"]["confirmed_count"], 0)
        self.assertEqual(len(list(directory.iterdir())), 1)

    def test_complete_five_type_source_only_report_and_deterministic_replay(self):
        bundle = write_final_bundle(self.source, self.findings, self.output)
        result = verify_final_bundle(bundle, self.source)
        self.assertEqual({p.name for p in bundle.iterdir()}, {
            "run.json", "evidence.jsonl", "findings.jsonl", "report.json", "actions.jsonl"})
        self.assertEqual(result["actions"], [])
        self.assertEqual((bundle / "actions.jsonl").read_bytes(), b"")
        self.assertEqual(result["run"]["source_run_id"], self.source_records["run"]["id"])
        self.assertEqual(result["run"]["target_sha"], self.source_records["run"]["commit"])
        self.assertEqual(result["run"]["manifest_hash"], None)
        self.assertEqual(result["run"]["run_status"], "source_only_deferred")
        self.assertEqual(len(result["evidence"]), 2)
        original = {row["id"]: row for row in self.source_records["evidence"]}
        for record in result["evidence"]:
            prior = original[record["source_evidence_id"]]
            self.assertEqual(record["source_sha256"], prior["source_sha256"])
            self.assertEqual(record["source_record_hash"], prior["content_hash"])
        self.assertEqual(result["findings"][0]["state"], "deferred")
        self.assertEqual(result["findings"][0]["basis"], "source_only")
        self.assertEqual(result["findings"][0]["source_sha256"], next(
            row["source_sha256"] for row in original.values() if row["path"] == "worker.py"))
        self.assertEqual(result["report"]["ordered_finding_ids"], [self.findings[0]["id"]])
        self.assertEqual(result["report"]["priority_rows"][0]["evidence_status"], "deferred")
        self.assertEqual(result["report"]["coverage"]["diagnostic_completeness"], "unknown")
        self.assertEqual(result["report"]["coverage"]["runtime_execution"], "not_observed")
        self.assertEqual(result["report"]["confirmed_count"], 0)
        original_bytes = {p.name: p.read_bytes() for p in bundle.iterdir()}
        self.assertEqual(write_final_bundle(self.source, list(reversed(self.findings)), self.output), bundle)
        self.assertEqual({p.name: p.read_bytes() for p in bundle.iterdir()}, original_bytes)
        self.assertEqual({p.name: p.read_bytes() for p in self.source.iterdir()}, self.source_bytes)
        alternative = admit(self.source, [{**self.candidate, "severity": "Critical"}])
        second_bundle = write_final_bundle(self.source, alternative, self.output)
        self.assertNotEqual(second_bundle, bundle)
        self.assertEqual(verify_final_bundle(second_bundle, self.source)["findings"][0]["severity"],
                         "Critical")
        self.assertEqual(verify_final_bundle(bundle, self.source)["findings"][0]["severity"], "High")
        self.assertEqual({p.name: p.read_bytes() for p in bundle.iterdir()}, original_bytes)
        (bundle / "actions.jsonl").write_bytes(b"{\"forged\":true}\n")
        with self.assertRaises(FileExistsError):
            write_final_bundle(self.source, self.findings, self.output)
        self.assertEqual((bundle / "actions.jsonl").read_bytes(), b"{\"forged\":true}\n")

    def test_priority_order_and_pinned_manifest_declaration(self):
        second = {**self.candidate, "root_symbol": "helper", "severity": "Critical",
                  "location": {"path": "helper.py", "line": 1},
                  "evidence_ids": [next(row["id"] for row in self.source_records["evidence"]
                                        if row["path"] == "helper.py")]}
        rows = admit(self.source, [self.candidate, second])
        manifest = self.manifest()
        with self.assertRaises(ValueError):
            write_final_bundle(self.source, rows, self.output,
                               manifest={**manifest, "snapshot_sha": "a" * 40})
        bundle = write_final_bundle(self.source, list(reversed(rows)), self.output, manifest=manifest)
        self.assertEqual(write_final_bundle(self.source, rows, self.output, manifest=manifest),
                         bundle)
        result = verify_final_bundle(bundle, self.source)
        self.assertEqual(result["report"]["ordered_finding_ids"],
                         [next(row["id"] for row in rows if row["severity"] == "Critical"),
                          next(row["id"] for row in rows if row["severity"] == "High")])
        self.assertEqual([row["evidence_status"] for row in result["report"]["priority_rows"]],
                         ["deferred", "deferred"])
        self.assertEqual(result["run"]["manifest_hash"],
                         hashlib.sha256(json.dumps(manifest, sort_keys=True, ensure_ascii=False,
                                                   separators=(",", ":")).encode()).hexdigest())
        self.assertIsNone(result["run"]["model_io_hash"])

    def test_batch_full_marks_unprocessed_python_sources_unknown(self):
        selected = sorted(row["path"] for row in self.source_records["evidence"])
        rows = [{"scope_id": f"module:{path}", "perspectives": [
            {"perspective": perspective, "status": "deferred",
             "reason": "budget_exhausted", "tokens": 0, "candidates": []} for perspective in PERSPECTIVES]}
                for path in selected]
        coverage = {"scope": "full_tracked_python_git_commit", "base_sha": None,
                    "selected_paths": selected, "analyzed_paths": [],
                    "omitted_unknown_paths": selected, "source_bytes": 0,
                    "tokens_used": 0, "diagnostic_completeness": "unknown"}
        manifest = self.model_manifest(symbol=None, scope="full")
        bundle = write_final_bundle(self.source, [], self.output, manifest=manifest,
                                    model_audit=rows, diagnosis_coverage=coverage)
        report = verify_final_bundle(bundle, self.source)
        self.assertEqual(report["run"]["diagnosis_coverage"], coverage)
        self.assertEqual(report["report"]["coverage"]["diagnosis"]["omitted_unknown_paths"], selected)
        self.assertEqual(report["report"]["confirmed_count"], 0)
        for corrupt in ({**coverage, "omitted_unknown_paths": []},
                        {**coverage, "selected_paths": selected[:1]},
                        {**coverage, "analyzed_paths": selected},
                        {**coverage, "tokens_used": 1},
                        {**coverage, "scope": "candidate_impact"}):
            with self.subTest(corrupt=corrupt), self.assertRaises((ValueError, TypeError)):
                write_final_bundle(self.source, [], self.output, manifest=manifest,
                                   model_audit=rows, diagnosis_coverage=corrupt)

    def test_batch_impact_preserves_git_plan_omissions(self):
        original_commit = self.source_records["run"]["commit"]
        (self.repo / "worker.py").write_text("def busy():\n    return 4\n")
        self.git("add", "worker.py")
        self.git("-c", "user.email=a@b.c", "-c", "user.name=A", "commit", "-qm", "candidate")
        source = write_source_run(self.root / "candidate-source", str(self.repo), scan(self.repo, "HEAD"))
        frozen = verify_source_run(source)
        plan = plan_candidate(self.repo, original_commit, frozen["run"]["commit"], scope="impact")
        selected = plan["observed_target_paths"]
        rows = [{"scope_id": f"module:{path}", "perspectives": [
            {"perspective": perspective, "status": "deferred",
             "reason": "source_slice_unavailable", "tokens": 0, "candidates": []} for perspective in PERSPECTIVES]}
                for path in selected]
        coverage = {"scope": "candidate_impact", "base_sha": original_commit,
                    "selected_paths": selected, "analyzed_paths": [],
                    "omitted_unknown_paths": sorted(set(plan["omitted_unknown_paths"]) | set(selected)),
                    "source_bytes": 0, "tokens_used": 0, "diagnostic_completeness": "unknown"}
        manifest = self.model_manifest(symbol=None, scope="impact", source=source,
                                       main_ref=original_commit, candidate_ref=frozen["run"]["commit"])
        bundle = write_final_bundle(source, [], self.output, manifest=manifest,
                                    model_audit=rows, diagnosis_coverage=coverage)
        report = verify_final_bundle(bundle, source)
        self.assertEqual(report["run"]["base_sha"], original_commit)
        self.assertEqual(report["report"]["coverage"]["diagnosis"], coverage)
        with self.assertRaises(ValueError):
            write_final_bundle(source, [], self.output, manifest=manifest,
                               model_audit=rows, diagnosis_coverage={
                                   **coverage, "omitted_unknown_paths": selected})

    def test_batch_finding_cites_completed_perspective_in_same_module(self):
        selected = sorted(row["path"] for row in self.source_records["evidence"])
        rows = [{"scope_id": f"module:{path}", "perspectives": (
            self.model_audit() if path == "worker.py" else [
                {"perspective": perspective, "status": "deferred",
                 "reason": "budget_exhausted", "tokens": 0, "candidates": []} for perspective in PERSPECTIVES])}
                for path in selected]
        coverage = {"scope": "full_tracked_python_git_commit", "base_sha": None,
                    "selected_paths": selected, "analyzed_paths": [],
                    "omitted_unknown_paths": selected, "source_bytes": 100,
                    "tokens_used": 5, "diagnostic_completeness": "unknown"}
        manifest = self.model_manifest(symbol=None, scope="full")
        bundle = write_final_bundle(self.source, self.findings, self.output,
                                    manifest=manifest, model_audit=rows,
                                    diagnosis_coverage=coverage)
        self.assertEqual(verify_final_bundle(bundle, self.source)["findings"][0]["state"], "deferred")
        wrong = [{"scope_id": entry["scope_id"],
                  "perspectives": (self.model_audit() if entry["scope_id"] == "module:helper.py"
                                   else [{"perspective": perspective, "status": "deferred",
                                          "reason": "budget_exhausted", "tokens": 0, "candidates": []}
                                         for perspective in PERSPECTIVES])}
                 for entry in rows]
        with self.assertRaises(ValueError):
            write_final_bundle(self.source, self.findings, self.output,
                               manifest=manifest, model_audit=wrong,
                               diagnosis_coverage=coverage)

    def test_model_audit_is_hashed_provenance_never_evidence(self):
        manifest = self.model_manifest()
        audit = self.model_audit()
        with self.assertRaises(ValueError):
            write_final_bundle(self.source, self.findings, self.output,
                               manifest=manifest, model_audit=list(reversed(audit)))
        bundle = write_final_bundle(self.source, self.findings, self.output,
                                    manifest=manifest, model_audit=audit)
        result = verify_final_bundle(bundle, self.source)
        canonical = json.dumps(audit, sort_keys=True, ensure_ascii=False,
                               separators=(",", ":")).encode()
        expected_hash = hashlib.sha256(canonical).hexdigest()
        self.assertEqual(result["run"]["model_audit"], audit)
        self.assertEqual(result["run"]["model_io_hash"], expected_hash)
        self.assertEqual(result["run"]["model_provenance"], "caller_declared_unattested")
        self.assertEqual(result["findings"][0]["model_io_hash"], expected_hash)
        self.assertEqual({row["kind"] for row in result["evidence"]}, {"source"})
        self.assertEqual(result["report"]["confirmed_count"], 0)
        self.assertEqual(result["findings"][0]["state"], "deferred")
        changed = [{**row} for row in audit]
        changed[2]["response_sha256"] = "f" * 64
        other = write_final_bundle(self.source, self.findings, self.output,
                                   manifest=manifest, model_audit=changed)
        self.assertNotEqual(other, bundle)
        self.assertEqual(verify_final_bundle(other, self.source)["run"]["model_audit"], changed)
        run_file = bundle / "run.json"
        row = json.loads(run_file.read_bytes())
        row["model_audit"][2]["response_sha256"] = "0" * 64
        run_file.write_bytes(self.seal(row))
        with self.assertRaises(ValueError):
            verify_final_bundle(bundle, self.source)

    def test_model_audit_rejects_malformed_rows_and_unattributed_findings(self):
        manifest = self.model_manifest()
        audit = self.model_audit()
        malformed = [
            audit[:-1],
            [*audit[:-1], {**audit[-1], "perspective": "performance"}],
            [{**audit[0], "status": "confirmed"}, *audit[1:]],
            [*audit[:2], {**audit[2], "response_sha256": "not-a-sha"}, *audit[3:]],
            [*audit[:2], {**audit[2], "tokens": True}, *audit[3:]],
            [*audit[:2], {**audit[2], "tokens": 101}, *audit[3:]],
            [*audit[:2], {**audit[2], "status": "deferred"}, *audit[3:]],
        ]
        for rows in malformed:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                write_final_bundle(self.source, self.findings, self.output,
                                   manifest=manifest, model_audit=rows)
        with self.assertRaises(ValueError):
            write_final_bundle(self.source, self.findings, self.output,
                               model_audit=audit)
        with self.assertRaises(ValueError):
            write_final_bundle(self.source, self.findings, self.output,
                               manifest=self.manifest(), model_audit=audit)
        candidate = {**self.candidate, "perspective": "tests"}
        with self.assertRaises(ValueError):
            write_final_bundle(self.source, admit(self.source, [candidate]), self.output,
                               manifest=manifest, model_audit=audit)

    def test_rejects_claimed_runtime_confirmation_and_foreign_source(self):
        for payload in ([], [{"kind": "runtime", "success": True}]):
            with self.assertRaisesRegex(ValueError, "Runtime records"):
                write_final_bundle(self.source, self.findings, self.output, runtime_records=payload)
        with self.assertRaises(ValueError):
            write_final_bundle(self.source, [{**self.findings[0], "state": "confirmed"}], self.output)
        with self.assertRaises(ValueError):
            write_final_bundle(self.source, [{**self.findings[0], "evidence_ids": ["invented"]}], self.output)
        bundle = write_final_bundle(self.source, self.findings, self.output)
        (self.repo / "worker.py").write_text("def busy():\n    return 4\n")
        self.git("add", "-A")
        self.git("-c", "user.email=a@b.c", "-c", "user.name=A", "commit", "-qm", "other")
        foreign = write_source_run(self.root / "foreign", str(self.repo), scan(self.repo, "HEAD"))
        with self.assertRaises(ValueError):
            verify_final_bundle(bundle, foreign)
        self.assertEqual(verify_final_bundle(bundle, self.source)["report"]["confirmed_count"], 0)

    def test_output_cannot_redirect_writes_into_source(self):
        with self.assertRaises(ValueError):
            write_final_bundle(self.source, self.findings, self.source)
        with self.assertRaises(ValueError):
            write_final_bundle(self.source, self.findings, self.repo)
        self.output.mkdir()
        (self.output / "runs").symlink_to(self.repo, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            write_final_bundle(self.source, self.findings, self.output)
        self.assertEqual({p.name: p.read_bytes() for p in self.source.iterdir()}, self.source_bytes)

    def test_forged_hashes_report_and_evidence_fail_closed(self):
        bundle = write_final_bundle(self.source, self.findings, self.output)
        finding_path = bundle / "findings.jsonl"
        original = finding_path.read_bytes()
        row = json.loads(original)
        row["state"] = "confirmed"
        finding_path.write_bytes(self.seal(row))
        with self.assertRaises(ValueError):
            verify_final_bundle(bundle, self.source)
        finding_path.write_bytes(original)
        evidence_path = bundle / "evidence.jsonl"
        original = evidence_path.read_bytes()
        lines = original.splitlines()
        row = json.loads(lines[0])
        row["source_sha256"] = "0" * 64
        lines[0] = self.seal(row).rstrip(b"\n")
        evidence_path.write_bytes(b"\n".join(lines) + b"\n")
        with self.assertRaises(ValueError):
            verify_final_bundle(bundle, self.source)
        evidence_path.write_bytes(original)
        report_path = bundle / "report.json"
        report = json.loads(report_path.read_bytes())
        report["confirmed_count"] = 1
        report_path.write_bytes(self.seal(report))
        with self.assertRaises(ValueError):
            verify_final_bundle(bundle, self.source)

    def test_empty_findings_are_deferred_no_diagnosis_not_zero_defects(self):
        bundle = write_final_bundle(self.source, [], self.output)
        report = verify_final_bundle(bundle, self.source)["report"]
        self.assertEqual(report["priority_rows"], [])
        self.assertEqual(report["coverage"]["diagnostic_completeness"], "unknown")
        self.assertEqual(report["finding_status"], "all_deferred_source_only")
        self.assertEqual(report["confirmed_count"], 0)
        self.assertEqual({p.name: p.read_bytes() for p in self.source.iterdir()}, self.source_bytes)


if __name__ == "__main__":
    unittest.main()
