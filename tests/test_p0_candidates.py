"""Row isolation preserves independent hypotheses and authenticated raw provenance."""

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from modules.diagnosis.model import (PERSPECTIVES, ResponseArtifacts, analyze,
                                     prompt_hash, verify_responses)
from modules.diagnosis.plan import context_hash
from modules.diagnosis.screening import isolate_conflicts, screen_candidates
from modules.evidence.authenticity import verify_git_source
from modules.evidence.provenance import write_source_run
from modules.findings.admission import admit
from modules.static_scan.orchestrator import scan


class CandidateIsolationTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.source = "def a(value):\n    return 1 / value\n"
        for path in ("a.py", "b.py"):
            (self.repo / path).write_text(self.source)
        self.git("add", ".")
        self.git("-c", "user.name=A", "-c", "user.email=a@b.c", "commit", "-qm", "fixture")
        sha = self.git("rev-parse", "HEAD")
        self.bundle = write_source_run(self.root / "source", str(self.repo), scan(self.repo, sha))
        self.verified = verify_git_source(self.bundle)
        self.evidence = {item["path"]: item for item in self.verified["evidence"]}
        self.context = {"nodes": [
            {"path": path, "kind": "module", "line": 1, "end_line": 2,
             "source_slice": self.source, "source_sha256": self.evidence[path]["source_sha256"]}
            for path in ("a.py", "b.py")], "edges": [], "truncated": False}
        bounds = {"wall_seconds": 30, "cpu_seconds": 30, "memory_bytes": 1048576,
                  "tokens": 100000, "tool_seconds": 30}
        self.manifest = {
            "schema_version": "run-manifest-v3", "snapshot_sha": sha,
            "image_digest": "sha256:" + "a" * 64, "tools": [], "nodes": [],
            "limits": {**bounds, "per_node": {}},
            "network": {"dependency": False, "model": True, "workload": False},
            "writable_paths": ["/work/evidence"],
            "model": {"endpoint": "https://api.anthropic.com/v1/messages",
                      "name_version": "fixture-model", "prompt_sha256": prompt_hash("five"),
                      "transmitted_data": ["source", "context"]},
            "analysis": {"mode": "five", "roles": list(PERSPECTIVES), "scope": "full",
                         "symbol": None, "base_sha": None, "context_policy": "git-ast-context-v1",
                         "contexts": [{"scope_id": "full", "sha256": context_hash(self.context)}]}}

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def candidate(self, **changes):
        return {"root_symbol": "a", "mechanism": "zero reaches division", "condition": "zero input",
                "trigger": "a(0)", "impact": "request fails", "taxonomy": "correctness",
                "severity": "High", "location": {"path": "a.py", "line": 2},
                "evidence_ids": [self.evidence["a.py"]["id"]],
                "next_action": {"action": "verify zero handling", "oracle": "defined zero behavior",
                                "time_minutes": 2}, **changes}

    def generate(self, rows, *, mode="five", artifacts=None):
        self.manifest["model"]["prompt_sha256"] = prompt_hash(mode)
        def reply(endpoint, payload, timeout):
            role = json.loads(payload["messages"][0]["content"])["perspective"]
            return {"usage": {"input_tokens": 100, "output_tokens": 20}, "stop_reason": "end_turn",
                    "content": [{"type": "text", "text": json.dumps({
                        "candidates": rows if role in ("tests", "all") else []})}]}

        unverified = []
        with patch("modules.diagnosis.model._request", side_effect=reply):
            candidates, audit = analyze(self.context, self.verified["evidence"], self.manifest,
                                        mode=mode, unverified=unverified, response_artifacts=artifacts)
        candidates = screen_candidates(candidates, self.verified, self.bundle,
                                       self.context, unverified)
        return candidates, audit, unverified

    def test_mixed_rows_keep_valid_cross_taxonomy_and_original_json(self):
        original = self.candidate(perspective="spoofed")
        bad_source = self.candidate(evidence_ids=["invented"])
        rows = [original, bad_source, None, "not an object", self.candidate(next_action=[])]
        before = copy.deepcopy(rows)
        candidates, audit, unverified = self.generate(rows)
        findings = admit(self.bundle, candidates)
        self.assertEqual([row["taxonomy"] for row in findings], ["correctness"])
        self.assertEqual(findings[0]["perspectives"], ["tests"])
        self.assertEqual((findings[0]["state"], findings[0]["basis"]), ("deferred", "source_only"))
        self.assertEqual(rows, before)
        call = audit[-1]
        self.assertEqual(call["status"], "completed")
        self.assertEqual([entry["status"] for entry in call["candidates"]],
                         ["accepted", "unverified", "unverified", "unverified", "unverified"])
        self.assertEqual(call["candidates"][0]["finding_id"], findings[0]["id"])
        self.assertEqual(call["candidates"][0]["candidate"]["perspective"], "spoofed")
        self.assertEqual([entry["index"] for entry in call["candidates"]], list(range(5)))
        self.assertEqual([entry["candidate_sha256"] for entry in call["candidates"]],
                         [context_hash(row) for row in before])
        self.assertEqual([row["candidate"] for row in unverified], before[1:])
        self.assertEqual([row["reason"] for row in unverified],
                         ["candidate_source_invalid"] + ["candidate_schema_invalid"] * 3)
        self.assertEqual({row["response_sha256"] for row in unverified}, {call["response_sha256"]})
        self.assertEqual([row["candidate_index"] for row in unverified], [1, 2, 3, 4])

    def test_single_mode_retains_actual_all_role(self):
        self.manifest["analysis"].update(mode="single", roles=["all"])
        candidates, audit, unverified = self.generate([self.candidate()], mode="single")
        self.assertEqual(admit(self.bundle, candidates)[0]["perspectives"], ["all"])
        self.assertEqual(audit[0]["candidates"][0]["status"], "accepted")
        self.assertEqual(unverified, [])

    def test_bad_location_does_not_remove_other_rows(self):
        for end_line, reason in ((2, "candidate_location_outside_context"),
                                 (999, "candidate_git_line_invalid")):
            with self.subTest(reason=reason):
                self.context["nodes"][0]["end_line"] = end_line
                self.manifest["analysis"]["contexts"][0]["sha256"] = context_hash(self.context)
                candidates, audit, unverified = self.generate([
                    self.candidate(), self.candidate(location={"path": "a.py", "line": 3})])
                self.assertEqual([row["location"]["line"] for row in admit(self.bundle, candidates)], [2])
                self.assertEqual(audit[-1]["status"], "completed")
                self.assertEqual(unverified[0]["reason"], reason)
                self.assertIsNone(audit[-1]["candidates"][1]["finding_id"])

    def test_entire_conflicting_identity_is_quarantined(self):
        variations = [
            {"trigger": "another trigger"}, {"taxonomy": "tests"},
            {"next_action": {"action": "different verification", "oracle": "different expected result",
                             "time_minutes": 3}},
            {"location": {"path": "b.py", "line": 2},
             "evidence_ids": [self.evidence["b.py"]["id"]]},
        ]
        for changes in variations:
            with self.subTest(changes=changes):
                candidates, audit, unverified = self.generate([
                    self.candidate(), self.candidate(root_symbol=" a ", **changes),
                    self.candidate(mechanism="independent risk")])
                survivors = isolate_conflicts(self.bundle, candidates, unverified)
                findings = admit(self.bundle, survivors)
                self.assertEqual([row["mechanism"] for row in findings], ["independent risk"])
                self.assertEqual([entry["status"] for entry in audit[-1]["candidates"]],
                                 ["unverified", "unverified", "accepted"])
                self.assertEqual([row["reason"] for row in unverified],
                                 ["candidate_identity_conflict"] * 2)
                self.assertEqual([row["candidate_index"] for row in unverified], [0, 1])
                self.assertTrue(all(entry["finding_id"] is None
                                    for entry in audit[-1]["candidates"][:2]))

    def test_compatible_duplicates_merge_without_false_conflict(self):
        candidates, audit, unverified = self.generate([
            self.candidate(), self.candidate(severity="Critical", location={"path": "a.py", "line": 1})])
        survivors = isolate_conflicts(self.bundle, candidates, unverified)
        findings = admit(self.bundle, survivors)
        self.assertEqual([(row["severity"], row["location"]["line"]) for row in findings], [("Critical", 1)])
        self.assertEqual({entry["finding_id"] for entry in audit[-1]["candidates"]}, {findings[0]["id"]})
        self.assertEqual(unverified, [])

    def test_mode_role_and_context_changes_never_transmit(self):
        for change in ("mode", "roles", "context", "schema"):
            with self.subTest(change=change):
                manifest = copy.deepcopy(self.manifest)
                context = copy.deepcopy(self.context)
                if change == "mode":
                    manifest["analysis"]["mode"] = "single"
                elif change == "roles":
                    manifest["analysis"]["roles"].reverse()
                elif change == "context":
                    context["nodes"][0]["source_slice"] += "# changed\n"
                else:
                    manifest["schema_version"] = "run-manifest-v1"
                with patch("modules.diagnosis.model._request") as request:
                    with self.assertRaises(ValueError):
                        analyze(context, self.verified["evidence"], manifest)
                request.assert_not_called()

    def test_response_failures_never_expose_partially_trusted_candidates(self):
        valid = {"usage": {"input_tokens": 100, "output_tokens": 20}, "stop_reason": "end_turn",
                 "content": [{"type": "text", "text": json.dumps({"candidates": [self.candidate()]})}]}
        malformed = [None, {**valid, "usage": {}}, {**valid, "content": {}},
                     {**valid, "content": [{"type": "text", "text": "null"}]},
                     {**valid, "content": [{"type": "text", "text": '{"candidates": [NaN]}' }]}]
        for response in malformed:
            with self.subTest(response=response), patch("modules.diagnosis.model._request", return_value=response):
                candidates, audit = analyze(self.context, self.verified["evidence"], self.manifest)
                self.assertEqual(candidates, [])
                self.assertEqual(audit[0]["status"], "failed")
                self.assertTrue(all(row["candidates"] == [] for row in audit))

    def test_next_role_reserves_both_instruction_fields_and_keeps_prior_candidate(self):
        from modules.diagnosis.model import AnalysisBudget, instructions_for

        first = PERSPECTIVES[0]
        second = PERSPECTIVES[1]
        response = {"usage": {"input_tokens": 2500, "cache_read_input_tokens": 50,
                              "output_tokens": 20}, "stop_reason": "end_turn",
                    "content": [{"type": "text", "text": json.dumps({
                        "candidates": [self.candidate()]})}]}
        reserve = 2550 + sum(len(value.encode("utf-8")) for value in (
            first, second, instructions_for("five", first), instructions_for("five", second)))
        self.manifest["limits"]["tokens"] = 2570 + reserve + 256
        budget = AnalysisBudget(self.manifest)
        with patch("modules.diagnosis.model._request", return_value=response) as request:
            candidates, audit = analyze(self.context, self.verified["evidence"],
                                        self.manifest, budget=budget)
        self.assertEqual(request.call_count, 1)
        self.assertEqual([row["status"] for row in audit],
                         ["completed"] + ["deferred"] * 4)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(budget.remaining, reserve + 256)

    def test_raw_response_replay_rejects_missing_tampered_and_rebound_bytes(self):
        artifacts = ResponseArtifacts(self.root / "responses", self.repo, self.bundle)
        self.addCleanup(artifacts.close)
        _, audit, _ = self.generate([self.candidate(), None], artifacts=artifacts)
        verify_responses(artifacts.references, [{"scope_id": "full", "perspectives": audit}])
        path = Path(artifacts.references[-1]["path"])
        original = path.read_bytes()
        path.unlink()
        with self.assertRaises(ValueError):
            verify_responses(artifacts.references, audit)
        path.write_bytes(original + b" ")
        path.chmod(0o600)
        with self.assertRaises(ValueError):
            verify_responses(artifacts.references, audit)
        changed = json.loads(original)
        changed["content"][0]["text"] = json.dumps({"candidates": [self.candidate(impact="different"), None]})
        rebound = json.dumps(changed, sort_keys=True, ensure_ascii=False).encode()
        path.write_bytes(rebound)
        digest = hashlib.sha256(rebound).hexdigest()
        references = copy.deepcopy(artifacts.references)
        references[-1]["response_sha256"] = digest
        rebound_audit = copy.deepcopy(audit)
        rebound_audit[-1]["response_sha256"] = digest
        with self.assertRaises(ValueError):
            verify_responses(references, rebound_audit)
        path.write_bytes(original)
        changed_usage = copy.deepcopy(audit)
        changed_usage[-1]["tokens"] += 1
        with self.assertRaises(ValueError):
            verify_responses(artifacts.references, changed_usage)
        with self.assertRaises(ValueError):
            verify_responses(artifacts.references[:-1], audit)


if __name__ == "__main__":
    unittest.main()
