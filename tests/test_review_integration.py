"""AST review units remain scoped, auditable and provisional."""

import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import diagnose_approved
from modules.diagnosis.plan import prepare_analysis
from modules.diagnosis.model import instructions_for, prompt_hash
from modules.evidence.authenticity import verify_git_source
from modules.evidence.final_bundle import verify_final_bundle, write_final_bundle
from modules.evidence.report import render_report
from test_diagnose_approved import ManifestDiagnosisTest


class ReviewIntegrationTest(unittest.TestCase):
    def test_review_units_require_exact_manifest_and_survive_sealing(self):
        for review in ("outline", "cards"):
            with self.subTest(review=review), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                fixture = ManifestDiagnosisTest()
                repo, sha, _ = fixture.fixture(root, {
                    "unit.py": "def work(value):\n    while value < 5:\n        value += 1\n    return 1 / value\n"})
                bundle, manifest, file = fixture.manifest_fixture(root, repo, sha, 60000, symbol="work")
                verified = verify_git_source(bundle)
                analysis, contexts, _ = prepare_analysis(verified, symbol="work", review=review)
                manifest["analysis"] = analysis
                file.write_text(json.dumps(manifest))
                

                with patch("modules.diagnosis.model._request") as request:
                    with patch.object(sys, "argv", ["diagnose_approved.py", str(bundle),
                                                      str(file), "--symbol", "work",
                                                      "--review-units", "raw", "--response-output",
                                                      str(root / "denied")]):
                        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as rejected:
                            diagnose_approved.main()
                    self.assertEqual(rejected.exception.code, 2)
                    request.assert_not_called()
                

                source_id = verified["evidence"][0]["id"]
                candidate = {"root_symbol": "work", "mechanism": "unverified division condition",
                             "condition": "value may be zero", "trigger": "work(0)",
                             "impact": "division failure", "taxonomy": "correctness",
                             "severity": "Medium", "location": {"path": "unit.py", "line": 4},
                             "evidence_ids": [source_id],
                             "next_action": {"action": "check input contract", "oracle": "zero permitted or excluded",
                                             "time_minutes": 2}}
                sent = []

                def respond(endpoint, payload, timeout):
                    message = json.loads(payload["messages"][0]["content"])
                    sent.append(message)
                    rows = [candidate] if message["perspective"] == "structure" else []
                    return {"usage": {"input_tokens": 120, "output_tokens": 10},
                            "stop_reason": "end_turn", "content": [{"type": "text",
                            "text": json.dumps({"candidates": rows})}]}

                output = io.StringIO()
                with patch("modules.diagnosis.model._request", side_effect=respond), patch.object(
                        sys, "argv", ["diagnose_approved.py", str(bundle), str(file),
                                      "--symbol", "work", "--review-units", review,
                                      "--response-output", str(root / "responses"),
                                      "--final-output", str(root / "final")]), contextlib.redirect_stdout(output):
                    self.assertEqual(diagnose_approved.main(), 0)
                result = json.loads(output.getvalue())
                self.assertEqual(len(sent), 5)
                self.assertTrue(all(item["context"]["review_units"]["level"] == review for item in sent))
                audited = result["perspectives"][0]["review"]
                self.assertEqual(audited["delivered_ids"],
                                 [unit["id"] for unit in contexts["symbol:work"]["review_units"]["delivered"]])
                self.assertEqual([match["index"] for match in audited["candidate_matches"]], [0])
                self.assertEqual(result["findings"][0]["state"], "deferred")
                sealed = verify_final_bundle(Path(result["final_source_only_bundle"]), bundle)
                self.assertEqual(sealed["run"]["model_audit"][0]["review"], audited)
                self.assertIn("AST 점검 항목", render_report(bundle, Path(result["final_source_only_bundle"])))

                altered = copy.deepcopy(result["perspectives"])
                altered[0]["review"]["delivered_ids"] = []
                with self.assertRaisesRegex(ValueError, "Review unit audit differs"):
                    write_final_bundle(bundle, result["findings"], root / "forged-final",
                                       manifest=manifest, model_audit=altered,
                                       diagnosis_coverage=result["diagnosis_coverage"])


    def test_generic_sixth_has_distinct_prompt_and_no_candidate_hint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = ManifestDiagnosisTest()
            repo, sha, _ = fixture.fixture(root, {
                "unit.py": "def work(value):\n    return 1 / value\n"})
            bundle, manifest, file = fixture.manifest_fixture(root, repo, sha, 60000, symbol="work", mode="generic")
            file.write_text(json.dumps(manifest))
            
            self.assertNotEqual(prompt_hash("generic"), prompt_hash("five"))
            self.assertEqual([instructions_for("generic", role)
                              for role in ("structure", "correctness", "performance",
                                           "concurrency", "tests")],
                             [instructions_for("five", role)
                              for role in ("structure", "correctness", "performance",
                                           "concurrency", "tests")])

            with patch("modules.diagnosis.model._request") as request:
                with patch.object(sys, "argv", ["diagnose_approved.py", str(bundle),
                                               str(file), "--symbol", "work",
                                               "--boundary-review", "--response-output",
                                               str(root / "denied")]):
                    with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as rejected:
                        diagnose_approved.main()
                self.assertEqual(rejected.exception.code, 2)
                request.assert_not_called()
            

            source_id = verify_git_source(bundle)["evidence"][0]["id"]
            candidate = {"root_symbol": "work", "mechanism": "zero can reach division",
                         "condition": "zero is permitted", "trigger": "work(0)",
                         "impact": "division failure", "taxonomy": "correctness",
                         "severity": "Medium", "location": {"path": "unit.py", "line": 2},
                         "evidence_ids": [source_id],
                         "next_action": {"action": "check zero contract", "oracle": "zero excluded",
                                         "time_minutes": 2}}
            inputs = []

            def respond(endpoint, payload, timeout):
                message = json.loads(payload["messages"][0]["content"])
                inputs.append(message)
                rows = [candidate] if message["perspective"] == "structure" else []
                return {"usage": {"input_tokens": 120, "output_tokens": 10},
                        "stop_reason": "end_turn", "content": [{"type": "text",
                        "text": json.dumps({"candidates": rows})}]}

            output = io.StringIO()
            with patch("modules.diagnosis.model._request", side_effect=respond), patch.object(
                    sys, "argv", ["diagnose_approved.py", str(bundle), str(file),
                                  "--symbol", "work", "--generic-review",
                                  "--response-output", str(root / "responses"),
                                  "--final-output", str(root / "final")]), contextlib.redirect_stdout(output):
                self.assertEqual(diagnose_approved.main(), 0)
            result = json.loads(output.getvalue())
            self.assertEqual([row["perspective"] for row in result["perspectives"]],
                             ["structure", "correctness", "performance", "concurrency", "tests", "generic"])
            self.assertEqual(result["stage"], "pilot_generic_review_provisional")
            self.assertEqual(result["perspectives"][-1]["candidates"], [])
            self.assertEqual(set(inputs[-1]), {"context", "perspective"})
            self.assertEqual(inputs[-1]["perspective"], "generic")
            sealed = verify_final_bundle(Path(result["final_source_only_bundle"]), bundle)
            self.assertEqual(len(sealed["findings"]), 1)
            self.assertEqual(sealed["report"]["confirmed_count"], 0)
            self.assertIn("일반 재검토자", render_report(bundle, Path(result["final_source_only_bundle"])))

if __name__ == "__main__":
    unittest.main()
