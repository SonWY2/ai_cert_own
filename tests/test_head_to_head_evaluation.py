"""Test-only sealed observations; these are not actual model or project results."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from modules.evaluation.head_to_head import ARMS, evaluate  # noqa: E402
from modules.evaluation.paired import _hash, seal  # noqa: E402

KEY = b"fixture-only-head-to-head-evaluator-key-123"
ROOT = Path(__file__).resolve().parents[1]


def _sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _change(rows, index, **fields):
    rows[index] = seal({**{name: value for name, value in rows[index].items() if name != "seal"}, **fields}, KEY)


def _fixture():
    models = {ARMS[0]: {"version": "strong-fixture", "family": "strong-family",
                        "prompt_sha256": "a" * 64, "pricing_sha256": "d" * 64,
                        "sampling": {"temperature": 0}},
              ARMS[1]: {"version": "small-fixture", "family": "small-family",
                        "prompt_sha256": "b" * 64, "pricing_sha256": "e" * 64,
                        "sampling": {"temperature": 0}}}
    judge = {"model_version": "judge-fixture", "model_family": "third-family",
             "prompt_sha256": "c" * 64, "temperature": 0}
    protocol = {"version": "evaluation-protocol-v2", "models": models, "judge": judge,
                "budget": {"token_limit": 1000, "wall_seconds_limit": 1200},
                "strength_rationale": "Precommitted fixture model ordering, not a real comparison",
                "bootstrap_seed": 12, "bootstrap_iterations": 1000}
    calibration = {"calibrated_at": "2026-01-01T00:00:00Z", **judge,
                   "decisions": [{"known_valid": True, "judged_valid": True},
                                 {"known_valid": False, "judged_valid": False}]}
    document = {"protocol": seal(protocol, KEY), "calibration": seal(calibration, KEY),
                "gold": [], "results": [], "judgments": []}
    for index in range(80):
        cid = f"case-{index:03d}"
        lane = "hidden_synthetic_holdout" if index % 40 < 20 else "temporal_public_holdout"
        source_type = "project_owned_synthetic_fixture" if lane == "hidden_synthetic_holdout" else "public_repository"
        findings = []
        if index % 4:
            for part in ("a", "b"):
                findings.append({"finding_id": f"{cid}-{part}", "risk_type": "concurrency" if part == "a" else "performance",
                                 "severity": "high" if part == "a" else "medium", "cross_file": part == "b",
                                 "root_cause_symbol": "svc.counter", "truth_source": "known_regression_test",
                                 "oracle_sha256": _sha(f"oracle-{cid}-{part}")})
        gold = {"case_id": cid, "family_id": f"family-{index // 2:03d}",
                "near_duplicate_group": f"template-{index // 2:03d}", "snapshot_sha": _sha(cid),
                "lane": lane, "stratum": "scheduled_main" if index < 40 else "release_candidate",
                "source_type": source_type, "revision": "fixed-v1" if source_type == "public_repository" else None,
                "license": "MIT" if source_type == "public_repository" else None,
                "sealed_at": "2026-01-03T00:00:00Z",
                "released_at": "2026-01-02T00:00:00Z" if source_type == "public_repository" else None,
                "findings": findings}
        document["gold"].append(seal(gold, KEY))
        for arm in ARMS:
            predictions = []
            if index % 4:
                selected = findings[:1] if arm == ARMS[0] else findings[1:] if index == 1 else findings
                for finding in selected:
                    predictions.append({"risk_type": finding["risk_type"], "severity": finding["severity"],
                                        "root_cause_symbol": finding["root_cause_symbol"],
                                        "hypothesis": f"Testable defect {finding['finding_id']}",
                                        "next_action": "Run the sealed regression", "evidence_snapshot_sha": gold["snapshot_sha"]})
            elif arm == ARMS[1]:
                predictions.append({"risk_type": "concurrency", "severity": "medium",
                                    "root_cause_symbol": "svc.counter", "hypothesis": "False alarm in clean case",
                                    "next_action": "Run the sealed regression", "evidence_snapshot_sha": gold["snapshot_sha"]})
            calls = [{"model_version": models[arm]["version"], "input_tokens": 20 if arm == ARMS[1] else 30,
                      "cache_input_tokens": 5, "output_tokens": 10 if arm == ARMS[1] else 20,
                      "billed_micro_usd": 250 if arm == ARMS[1] else 1000,
                      "receipt_sha256": _sha(f"receipt-{cid}-{arm}-{n}")}
                     for n in range(2 if arm == ARMS[1] else 1)]
            result = {"case_id": cid, "arm": arm, "snapshot_sha": gold["snapshot_sha"],
                      "protocol_hash": _hash(protocol), "status": "completed",
                      "started_at": "2026-01-05T00:00:00Z", "ended_at": "2026-01-05T00:01:00Z",
                      "tokens_used": sum(call["input_tokens"] + call["output_tokens"] for call in calls),
                      "tool_seconds_used": 0, "calls": calls, "predictions": predictions,
                      "unsafe_execution": False, "unjustified_high_dismissal": False}
            document["results"].append(seal(result, KEY))
            for prediction in predictions:
                if any(item["case_id"] == cid and item["prediction_hash"] == _hash(prediction)
                       for item in document["judgments"]):
                    continue
                matched = next((item["finding_id"] for item in findings
                                if prediction["hypothesis"].endswith(item["finding_id"])), None)
                judgment = {"case_id": cid, "snapshot_sha": gold["snapshot_sha"],
                            "prediction_hash": _hash(prediction), "gold_finding_id": matched,
                            "oracle_sha256": next((item["oracle_sha256"] for item in findings
                                                   if item["finding_id"] == matched), None),
                            "oracle_supported": matched is not None, "judged_valid": matched is not None,
                            "reason_code": "matched" if matched else "no_gold_match",
                            "judged_at": "2026-01-05T00:02:00Z", "calibration_hash": _hash(calibration),
                            **judge, "blinded": True, "randomized_order": True,
                            "unsafe_execution": False, "unjustified_high_dismissal": False}
                document["judgments"].append(seal(judgment, KEY))
    freeze = {"frozen_at": "2026-01-04T00:00:00Z", "development_cutoff": "2026-01-01T12:00:00Z",
              "arm_definitions_frozen_at": "2026-01-01T00:00:00Z", "protocol_hash": _hash(protocol),
              "calibration_hash": _hash(calibration), "development_families": ["pilot-family"],
              "development_near_duplicates": ["pilot-template"],
              "cases": [{"case_id": item["case_id"],
                         "gold_hash": _hash({k: v for k, v in item.items() if k != "seal"})}
                        for item in document["gold"]]}
    document["freeze"] = seal(freeze, KEY)
    return document


class HeadToHeadTests(unittest.TestCase):
    def setUp(self):
        self.document = _fixture()

    def test_multiple_findings_exclusive_misses_clean_false_alarms_and_total_cost(self):
        result = evaluate(self.document, KEY)
        self.assertEqual(result["gold_findings"], 120)
        self.assertEqual((result["overall"][ARMS[0]]["tp"], result["overall"][ARMS[0]]["fn"]), (60, 60))
        self.assertEqual((result["overall"][ARMS[1]]["tp"], result["overall"][ARMS[1]]["fn"]), (119, 1))
        self.assertEqual(result["overall"][ARMS[1]]["fp"], 20)
        self.assertEqual(result["overall"][ARMS[0]]["reported_api_cost_micro_usd"], 80000)
        self.assertEqual(result["overall"][ARMS[1]]["reported_api_cost_micro_usd"], 40000)
        self.assertEqual(len(result["exclusive_gold_findings"]["strong_only"]), 1)
        self.assertEqual(len(result["exclusive_gold_findings"]["system_only"]), 60)
        self.assertEqual(len(result["exclusive_gold_findings"]["missed_by_both"]), 0)
        self.assertEqual(result["per_stratum"]["release_candidate"][ARMS[1]]["tp"], 60)
        self.assertEqual(result["exclusive_gold_findings"]["strong_only"][0]["severity"], "high")
        self.assertTrue(result["meets_head_to_head_gate"])
        self.assertGreater(result["family_bootstrap_95_ci_percentage_points"][0], 0)
        self.document["results"].reverse()
        self.document["gold"].reverse()
        self.assertEqual(evaluate(self.document, KEY), result)

    def test_timeout_and_failed_calls_keep_cost_and_gold_false_negatives(self):
        system = self.document["results"][3]
        _change(self.document["results"], 3, status="timeout", predictions=[])
        failed_hashes = {_hash(prediction) for prediction in system["predictions"]}
        self.document["judgments"] = [item for item in self.document["judgments"]
                                      if not (item["case_id"] == system["case_id"] and
                                              item["prediction_hash"] in failed_hashes)]
        report = evaluate(self.document, KEY)
        self.assertEqual(report["overall"][ARMS[1]]["tp"], 118)
        self.assertEqual(report["overall"][ARMS[1]]["reported_api_cost_micro_usd"], 40000)
        self.assertEqual(report["overall"][ARMS[1]]["fn"], 2)
        self.assertEqual(report["overall"][ARMS[1]]["status_counts"]["timeout"], 1)
        self.assertEqual(len(report["exclusive_gold_findings"]["missed_by_both"]), 1)
        self.assertGreater(len(system["predictions"]), 0)

    def test_seal_and_precommit_reject_posthoc_changes(self):
        self.document["results"][1]["calls"][0]["billed_micro_usd"] = 0
        with self.assertRaisesRegex(ValueError, "seal"):
            evaluate(self.document, KEY)
        self.document = _fixture()
        gold = self.document["gold"][1]
        _change(self.document["gold"], 1, findings=gold["findings"][:1])
        with self.assertRaisesRegex(ValueError, "precommitted"):
            evaluate(self.document, KEY)

    def test_wrong_model_and_hidden_extra_calls_are_rejected(self):
        row = self.document["results"][0]
        calls = [{**row["calls"][0], "model_version": "small-fixture"}]
        _change(self.document["results"], 0, calls=calls)
        with self.assertRaisesRegex(ValueError, "Wrong model"):
            evaluate(self.document, KEY)
        self.document = _fixture()
        row = self.document["results"][0]
        calls = [*row["calls"], {**row["calls"][0], "receipt_sha256": _sha("extra")}]
        _change(self.document["results"], 0, calls=calls, tokens_used=100)
        with self.assertRaisesRegex(ValueError, "one model call"):
            evaluate(self.document, KEY)
        self.document = _fixture()
        row = self.document["results"][2]
        calls = [{**row["calls"][0], "receipt_sha256": self.document["results"][0]["calls"][0]["receipt_sha256"]}]
        _change(self.document["results"], 2, calls=calls)
        with self.assertRaisesRegex(ValueError, "Reused model billing receipt"):
            evaluate(self.document, KEY)

    def test_missing_or_unblinded_judgment_rejected(self):
        self.document["judgments"].pop()
        with self.assertRaisesRegex(ValueError, "Missing independent judgment"):
            evaluate(self.document, KEY)
        self.document = _fixture()
        _change(self.document["judgments"], 0, blinded=False)
        with self.assertRaisesRegex(ValueError, "Uncalibrated, unblinded"):
            evaluate(self.document, KEY)

    def test_semantic_match_cannot_switch_to_unrelated_oracle_evidence(self):
        _change(self.document["judgments"], 1, oracle_sha256="f" * 64)
        with self.assertRaisesRegex(ValueError, "Oracle evidence hash mismatch"):
            evaluate(self.document, KEY)
        self.document = _fixture()
        _change(self.document["judgments"], 0, oracle_supported=True)
        with self.assertRaisesRegex(ValueError, "cannot claim oracle support"):
            evaluate(self.document, KEY)

    def test_no_oracle_match_cannot_be_true_positive_and_duplicate_match_is_fp(self):
        judgment = self.document["judgments"][1]
        _change(self.document["judgments"], 1, oracle_supported=False)
        result = evaluate(self.document, KEY)
        self.assertEqual(result["overall"][ARMS[0]]["tp"], 59)
        self.assertEqual(result["overall"][ARMS[0]]["fp"], 1)
        self.assertEqual(judgment["gold_finding_id"], "case-001-a")
        self.document = _fixture()
        row = self.document["results"][3]
        duplicate = {**row["predictions"][0], "hypothesis": "Second wording of the same defect"}
        _change(self.document["results"], 3, predictions=[*row["predictions"], duplicate])
        original = next(item for item in self.document["judgments"]
                        if item["case_id"] == "case-001" and item["gold_finding_id"] == "case-001-b")
        self.document["judgments"].append(seal({**{name: value for name, value in original.items() if name != "seal"},
                                                "prediction_hash": _hash(duplicate)}, KEY))
        report = evaluate(self.document, KEY)
        self.assertEqual(report["overall"][ARMS[1]]["tp"], 119)
        self.assertEqual(report["overall"][ARMS[1]]["fp"], 21)

    def test_important_defect_recall_guard_blocks_apparent_overall_win(self):
        for index in (5, 6, 7, 9, 10, 11, 13):
            row = self.document["results"][index * 2 + 1]
            _change(self.document["results"], index * 2 + 1,
                    predictions=[prediction for prediction in row["predictions"]
                                 if prediction["risk_type"] != "concurrency"])
        report = evaluate(self.document, KEY)
        self.assertGreater(report["recall_difference_percentage_points"], 0)
        self.assertLess(report["system_critical_high_recall"], .90)
        self.assertFalse(report["meets_head_to_head_gate"])

    def test_unsafe_result_and_dismissal_block_output(self):
        _change(self.document["results"], 1, unsafe_execution=True)
        with self.assertRaisesRegex(ValueError, "Unsafe execution"):
            evaluate(self.document, KEY)
        self.document = _fixture()
        _change(self.document["results"], 1, unjustified_high_dismissal=True)
        with self.assertRaisesRegex(ValueError, "Critical/High dismissal"):
            evaluate(self.document, KEY)

    def test_cli_reports_v2_and_rejects_mutated_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "cases.json"
            path.write_text(json.dumps(self.document), encoding="utf-8")
            env = {**os.environ, "PAIRED_EVALUATION_KEY": KEY.hex()}
            command = [sys.executable, str(ROOT / "src" / "evaluate_cases.py"), str(path)]
            success = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
            self.assertEqual(success.returncode, 0, success.stderr)
            self.assertEqual(json.loads(success.stdout)["gold_findings"], 120)
            self.document["results"][0]["calls"][0]["receipt_sha256"] = "0" * 64
            path.write_text(json.dumps(self.document), encoding="utf-8")
            failure = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
            self.assertNotEqual(failure.returncode, 0)
            self.assertEqual(failure.stdout, "")


if __name__ == "__main__":
    unittest.main()
