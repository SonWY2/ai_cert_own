"""Synthetic test-only records exercise offline aggregation; not measured pilot results."""

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from modules.evaluation.paired import ARMS, _hash, evaluate, seal  # noqa: E402

KEY = b"synthetic-test-only-evaluator-secret-123456789"
ROOT = Path(__file__).resolve().parents[1]


def _make_input():
    budget = {"token_limit": 1000, "tool_seconds_limit": 90, "wall_seconds_limit": 1200,
              "retry_limit": 1, "output_schema": "recommendation-v1", "model_version": "fixture-model-v1",
              "sampling": {"temperature": 0}}
    judge = {"model_version": "fixture-judge-v1", "model_family": "judge-family",
             "evaluated_model_family": "generator-family", "prompt_sha256": "a" * 64, "temperature": 0}
    protocol = {"version": "evaluation-protocol-v1", "budget": budget, "judge": judge,
                "bootstrap_seed": 17, "bootstrap_iterations": 1000}
    calibration = {"calibrated_at": "2026-01-01T00:00:00Z", "model_version": judge["model_version"],
                   "model_family": judge["model_family"], "prompt_sha256": judge["prompt_sha256"],
                   "temperature": 0, "decisions": [{"known_valid": True, "judged_valid": True},
                                                    {"known_valid": False, "judged_valid": False}]}
    output = {"protocol": seal(protocol, KEY), "calibration": seal(calibration, KEY),
              "gold": [], "results": [], "oracles": [], "judgments": []}
    for index in range(80):
        cid = f"case-{index:03d}"
        lane = ("hidden_synthetic_holdout" if index % 40 < 20 else "temporal_public_holdout")
        source_type = ("project_owned_synthetic_fixture" if lane == "hidden_synthetic_holdout"
                       else "public_repository")
        gold = {"case_id": cid, "family_id": f"family-{index // 2:03d}",
                "near_duplicate_group": f"duplicate-{index // 2:03d}",
                "snapshot_sha": hashlib.sha256(cid.encode()).hexdigest(), "lane": lane,
                "stratum": "scheduled_main" if index < 40 else "release_candidate",
                "complexity": "standard" if index % 2 == 0 else "complex",
                "source_type": source_type, "revision": "fixed-v1" if source_type == "public_repository" else None,
                "license": "MIT" if source_type == "public_repository" else None,
                "sealed_at": "2026-01-03T00:00:00Z",
                "released_at": "2026-01-02T00:00:00Z" if source_type == "public_repository" else None,
                "expected_invariant": "No lost updates", "root_cause_symbol": "Counter.increment",
                "impact": "Incorrect counter", "acceptable_priorities": ["risk-main"],
                "oracle_command": "python -m unittest tests.test_counter",
                "truth_source": "known_regression_test", "truth_conflict": False}
        output["gold"].append(seal(gold, KEY))
        for arm in ARMS:
            candidate = {"selected_risk": "risk-main" if arm == ARMS[-1] or index < 40 else "wrong-risk",
                         "evidence_snapshot_sha": gold["snapshot_sha"],
                         "hypothesis": "Increment loses a concurrent write",
                         "next_action": "Run the concurrent counter regression",
                         "workload": "counter scenario", "oracle": "count equals expected",
                         "dismissed_risks": []}
            result = {"case_id": cid, "arm": arm, "snapshot_sha": gold["snapshot_sha"],
                      "protocol_hash": _hash(protocol), "budget": budget,
                      "status": "completed", "started_at": "2026-01-05T00:00:00Z",
                      "ended_at": "2026-01-05T00:10:00Z", "wall_seconds": 600,
                      "tokens_used": 300, "tool_seconds_used": 30, "retries_used": 0,
                      "candidate": candidate}
            output["results"].append(seal(result, KEY))
            key = (cid, _hash(candidate))
            if not any(row["case_id"] == cid and row["candidate_hash"] == key[1] for row in output["oracles"]):
                oracle = {"case_id": cid, "snapshot_sha": gold["snapshot_sha"],
                          "candidate_hash": key[1], "evaluated_at": "2026-01-05T00:11:00Z",
                          "truth_source": "known_regression_test", "priority_acceptable": candidate["selected_risk"] == "risk-main",
                          "evidence_supported": True, "action_falsifiable": True,
                          "workload_oracle_adequate": True, "unjustified_high_dismissal": False,
                          "unsafe_execution": False}
                decision = {"case_id": cid, "snapshot_sha": gold["snapshot_sha"],
                            "candidate_hash": key[1], "judged_at": "2026-01-05T00:12:00Z",
                            "calibration_hash": _hash(calibration), "model_version": judge["model_version"],
                            "model_family": judge["model_family"], "prompt_sha256": judge["prompt_sha256"],
                            "temperature": 0, "blinded": True, "randomized_order": True,
                            "valid": True, "reason_code": "semantic_match"}
                output["oracles"].append(seal(oracle, KEY))
                output["judgments"].append(seal(decision, KEY))
    freeze = {"frozen_at": "2026-01-04T00:00:00Z", "development_cutoff": "2026-01-01T12:00:00Z",
              "arm_definitions_frozen_at": "2026-01-01T00:00:00Z",
              "protocol_hash": _hash(protocol), "calibration_hash": _hash(calibration),
              "development_families": ["pilot-family"],
              "development_near_duplicates": ["pilot-template"],
              "cases": [{"case_id": item["case_id"],
                         "gold_hash": _hash({k: v for k, v in item.items() if k != "seal"})}
                        for item in output["gold"]]}
    output["freeze"] = seal(freeze, KEY)
    return output


def _replace_signed(rows, index, **changes):
    rows[index] = seal({**{k: v for k, v in rows[index].items() if k != "seal"}, **changes}, KEY)


class PairedEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.document = _make_input()

    def test_paired_rates_and_family_ci_reproducible_independent_of_record_order(self):
        result = evaluate(self.document, KEY)
        self.assertEqual(result["overall"][ARMS[0]], {"valid": 40, "total": 80, "rate": .5})
        self.assertEqual(result["overall"][ARMS[-1]], {"valid": 80, "total": 80, "rate": 1.0})
        self.assertEqual(result["primary_A_vs_F_percentage_points"], 50.0)
        self.assertEqual(result["distinct_families"], 40)
        self.assertTrue(result["family_bootstrap_95_ci_percentage_points"][0] > 0)
        self.assertEqual(result["per_lane"]["hidden_synthetic_holdout"][ARMS[-1]]["total"], 40)
        self.assertEqual(result["per_stratum"]["release_candidate"][ARMS[0]]["valid"], 0)
        self.document["results"].reverse()
        self.document["gold"].reverse()
        self.assertEqual(evaluate(self.document, KEY), result)

    def test_missing_and_timeout_count_in_denominator(self):
        for index, status in ((5, "missing"), (6, "timeout"), (7, "judge_failure")):
            _replace_signed(self.document["results"], index, candidate=None, status=status)
        report = evaluate(self.document, KEY)
        self.assertEqual(report["overall"][ARMS[-1]]["total"], 80)
        self.assertEqual(sum(report["overall"][arm]["valid"] for arm in ARMS), 80 + 5 * 40 - 3)

    def test_incomplete_case_and_family_contamination_rejected(self):
        self.document["results"].pop()
        with self.assertRaisesRegex(ValueError, "six outputs"):
            evaluate(self.document, KEY)
        self.document = _make_input()
        _replace_signed(self.document["gold"], 40, family_id="pilot-family")
        freeze = self.document["freeze"]
        cases = copy.deepcopy(freeze["cases"])
        cases[40]["gold_hash"] = _hash({k: v for k, v in self.document["gold"][40].items() if k != "seal"})
        self.document["freeze"] = seal({**{k: v for k, v in freeze.items() if k != "seal"}, "cases": cases}, KEY)
        with self.assertRaisesRegex(ValueError, "Family or near duplicate"):
            evaluate(self.document, KEY)
        _replace_signed(self.document["gold"], 40, family_id="family-000")
        cases[40]["gold_hash"] = _hash({k: v for k, v in self.document["gold"][40].items() if k != "seal"})
        self.document["freeze"] = seal({**{k: v for k, v in freeze.items() if k != "seal"}, "cases": cases}, KEY)
        with self.assertRaisesRegex(ValueError, "Family or near duplicate"):
            evaluate(self.document, KEY)

    def test_changed_budget_and_untrusted_result_rejected(self):
        row = self.document["results"][0]
        self.document["results"][0] = {**row, "wall_seconds": 1}
        with self.assertRaisesRegex(ValueError, "seal"):
            evaluate(self.document, KEY)
        _replace_signed(self.document["results"], 0, budget={**row["budget"], "token_limit": 1500})
        with self.assertRaisesRegex(ValueError, "budget"):
            evaluate(self.document, KEY)
        with self.assertRaisesRegex(ValueError, "key"):
            evaluate(self.document, b"bad")

    def test_calibration_and_snapshot_claims_must_match_prior_seals(self):
        calibration = self.document["calibration"]
        self.document["calibration"] = seal({
            **{k: v for k, v in calibration.items() if k != "seal"},
            "decisions": [{"known_valid": True, "judged_valid": False},
                          {"known_valid": False, "judged_valid": False}]}, KEY)
        with self.assertRaisesRegex(ValueError, "Uncalibrated"):
            evaluate(self.document, KEY)
        self.document = _make_input()
        _replace_signed(self.document["results"], 0, snapshot_sha="d" * 64)
        with self.assertRaisesRegex(ValueError, "snapshot"):
            evaluate(self.document, KEY)

    def test_over_ceiling_completed_result_is_failure_not_success(self):
        candidate = self.document["results"][5]["candidate"]
        _replace_signed(self.document["results"], 5, ended_at="2026-01-05T00:21:00Z", wall_seconds=1260)
        digest = _hash(candidate)
        for field, stamp, name in (("oracles", "2026-01-05T00:22:00Z", "evaluated_at"),
                                   ("judgments", "2026-01-05T00:23:00Z", "judged_at")):
            index = next(i for i, item in enumerate(self.document[field])
                         if item["case_id"] == "case-000" and item["candidate_hash"] == digest)
            _replace_signed(self.document[field], index, **{name: stamp})
        report = evaluate(self.document, KEY)
        self.assertEqual(report["overall"][ARMS[-1]]["valid"], 79)
        self.assertEqual(report["overall"][ARMS[-1]]["total"], 80)

    def test_signed_oracle_and_judge_are_not_overridden_by_candidate_claims(self):
        _replace_signed(self.document["oracles"], 0, priority_acceptable="yes")
        with self.assertRaisesRegex(ValueError, "boolean"):
            evaluate(self.document, KEY)
        self.document = _make_input()
        _replace_signed(self.document["judgments"], 0, model_family="generator-family")
        with self.assertRaisesRegex(ValueError, "judge"):
            evaluate(self.document, KEY)
        self.document = _make_input()
        self.document["judgments"].pop()
        with self.assertRaisesRegex(ValueError, "Missing judge"):
            evaluate(self.document, KEY)

    def test_unjustified_proposed_high_dismissal_and_unsafe_execution_block_output(self):
        last = self.document["results"][5]
        cid, digest = last["case_id"], _hash(last["candidate"])
        idx = next(i for i, value in enumerate(self.document["oracles"])
                   if value["case_id"] == cid and value["candidate_hash"] == digest)
        _replace_signed(self.document["oracles"], idx, unjustified_high_dismissal=True)
        with self.assertRaisesRegex(ValueError, "dismissed Critical/High"):
            evaluate(self.document, KEY)
        _replace_signed(self.document["oracles"], idx, unjustified_high_dismissal=False,
                        unsafe_execution=True)
        with self.assertRaisesRegex(ValueError, "Unsafe execution"):
            evaluate(self.document, KEY)

    def test_cli_prints_only_valid_json_and_rejects_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "cases.json"
            path.write_text(json.dumps(self.document), encoding="utf-8")
            env = {**os.environ, "PAIRED_EVALUATION_KEY": KEY.hex()}
            process = subprocess.run([sys.executable, str(ROOT / "src" / "evaluate_cases.py"), str(path)],
                                     env=env, capture_output=True, text=True, check=False)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(json.loads(process.stdout)["cases"], 80)
            self.assertEqual(process.stderr, "")
            path.write_text('{"protocol":1,"protocol":2}', encoding="utf-8")
            rejected = subprocess.run([sys.executable, str(ROOT / "src" / "evaluate_cases.py"), str(path)],
                                      env=env, capture_output=True, text=True, check=False)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertEqual(rejected.stdout, "")


if __name__ == "__main__":
    unittest.main()
