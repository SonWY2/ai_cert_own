"""Offline comparison fixtures are not model, independent judge, or truth evidence."""

import copy
import hashlib
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from modules.diagnosis.model import prompt_hash  # noqa: E402
from modules.diagnosis.plan import context_hash  # noqa: E402
from modules.evaluation import development  # noqa: E402

SHA = "a" * 64


def _artifact(directory, rows):
    response = {"usage": {"input_tokens": 2, "cache_read_input_tokens": 3,
                          "output_tokens": 4}, "stop_reason": "end_turn",
                "content": [{"type": "text", "text": json.dumps({"candidates": rows})}]}
    raw = json.dumps(response, ensure_ascii=False, sort_keys=True).encode()
    digest = hashlib.sha256(raw).hexdigest()
    path = directory / digest
    path.write_bytes(raw)
    path.chmod(0o600)
    return {"path": str(path), "response_sha256": digest}


def _patch(test, target, name, replacement):
    patcher = mock.patch.object(target, name, replacement)
    patcher.start()
    test.addCleanup(patcher.stop)


def _document(test, directory, experiment="sixth_role", gold=None, claims=None):
    _patch(test, development, "verify_git_source", lambda _path: {
        "run": {"commit": SHA}, "evidence": [{"path": "pkg/a.py"}]})
    _patch(test, development, "prepare_analysis", lambda *_args, **_kwargs: (
        {}, {"symbol:pkg.a.f": {"nodes": [{"path": "pkg/a.py", "distance": 0}],
                                "static_counterexamples": []}}, None))
    roles = development.SIXTH_ROLES if experiment == "sixth_role" else development.BASELINE_ROLES
    claims = claims or {}
    case = {"id": "case", "snapshot_sha": SHA, "source_bundle": str(directory),
            "scope": {"path": "pkg/a.py", "symbol": "pkg.a.f"},
            "trials": ["t1", "t2", "t3"], "gold": gold, "strong_candidate_causes": None}
    order = [["case", trial, arm] for trial in case["trials"] for arm in roles]
    random.Random(17).shuffle(order)
    plan = {"version": "development-comparison-v1", "experiment": experiment,
            "arms": {arm: list(names) for arm, names in roles.items()},
            "profiles": {arm: {"mode": ("generic" if arm == "B_generic" else
                                       "boundary" if arm == "B_assumptions" else
                                       "single" if arm.endswith("_single") else "five"),
                               "model_version": "strong-v1" if arm == "strong_single" else "small-v1",
                               "prompt_sha256": prompt_hash("generic" if arm == "B_generic" else
                                                             "boundary" if arm == "B_assumptions" else
                                                             "single" if arm.endswith("_single") else "five"),
                               "context_policy": "git-ast-context-v1"}
                         for arm in roles},
            "seed": 17, "budget": {"tokens_per_trial": 100, "wall_seconds_per_trial": 60},
            "cases": [case], "order": order}
    records = []
    for trial in case["trials"]:
        for arm, names in roles.items():
            calls = []
            for index, perspective in enumerate(names):
                candidates = claims.get((arm, index), [])
                artifact = _artifact(directory, candidates)
                audit = {"perspective": perspective, "status": "completed", "reason": None,
                         "tokens": 9, "request_sha256": hashlib.sha256(str(index).encode()).hexdigest(),
                         "response_sha256": artifact["response_sha256"], "wall_seconds": .1,
                         "candidates": [{"index": n, "candidate": candidate,
                                         "candidate_sha256": context_hash(candidate),
                                         "status": "accepted", "reason": None,
                                         "finding_id": f"finding-{n}"}
                                        for n, candidate in enumerate(candidates)]}
                calls.append({"audit": audit, "response": artifact,
                              "billed_usd": None, "receipt_sha256": None})
            records.append({"case_id": "case", "trial_id": trial, "arm": arm,
                            "final_bundle": str(directory / f"{trial}-{arm}") if arm not in
                            ("small_single", "strong_single") else None,
                            "wall_seconds": 1, "calls": calls})
    ordered = {tuple(item): index for index, item in enumerate(plan["order"])}
    records.sort(key=lambda item: ordered[("case", item["trial_id"], item["arm"])])

    def verified_final(path, _source):
        record = next(row for row in records if row["final_bundle"] == str(path))
        profile = plan["profiles"][record["arm"]]
        return {"run": {"id": f"{record['trial_id']}-{record['arm']}", "target_sha": SHA,
                        "manifest": {"analysis": {"symbol": case["scope"]["symbol"],
                                                  "mode": profile["mode"],
                                                  "context_policy": profile["context_policy"]},
                                     "model": {"name_version": profile["model_version"],
                                               "prompt_sha256": profile["prompt_sha256"]},
                                     "limits": {"tokens": plan["budget"]["tokens_per_trial"],
                                                "wall_seconds": plan["budget"]["wall_seconds_per_trial"]}},
                        "model_audit": [call["audit"] for call in record["calls"]]}}

    _patch(test, development, "verify_final_bundle", verified_final)
    return {"plan": plan, "executions": records, "judgments": []}


def _judgment(document, trial, arm, call, index, verdict, cause=None):
    record = next(row for row in document["executions"] if row["trial_id"] == trial and row["arm"] == arm)
    entry = record["calls"][call]["audit"]["candidates"][index]
    return {"case_id": "case", "trial_id": trial, "arm": arm, "call_index": call,
            "candidate_index": index, "candidate_sha256": entry["candidate_sha256"],
            "verdict": verdict, "cause_id": cause,
            "independent_ref": f"external:{cause}" if verdict != "U" else None,
            "causal_position": True if verdict != "U" else None}


class DevelopmentComparisonTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)

    def test_explicit_same_cause_collapses_distinct_causes_survive(self):
        gold = [{"cause_id": name, "independent_ref": f"regression:{name}"}
                for name in ("cause-1", "cause-2")]
        doc = _document(self, self.directory, gold=gold, claims={
            ("B", 0): [{"claim": "EOF branch one"}, {"claim": "EOF branch two"},
                       {"claim": "different condition"}]})
        for trial in ("t1", "t2", "t3"):
            for index, cause in enumerate(("cause-1", "cause-1", "cause-2")):
                doc["judgments"].append(_judgment(doc, trial, "B", 0, index, "TP", cause))
        report = development.evaluate(doc)
        self.assertEqual((report["actual"]["B"]["raw_claims"], report["actual"]["B"]["tp"]), (9, 6))
        self.assertEqual(report["actual"]["B"]["known_gold_misses"], 0)
        self.assertEqual(report["paired"][0]["actual_trials"]["B"]["tp"], 2)
        self.assertEqual(report["actual"]["B"]["precision_conditional"], 1)
        self.assertIsNone(report["actual"]["B"]["reported_billed_usd"])
        self.assertIsNone(report["derived_fixed_B"]["B_plus_generic"]["reported_billed_usd"])

    def test_missing_gold_and_missing_judgment_remain_unknown(self):
        doc = _document(self, self.directory, claims={
            ("B", 0): [{"claim": "first"}, {"claim": "second"}]})
        doc["judgments"].append(_judgment(doc, "t1", "B", 0, 0, "TP", "cause-1"))
        summary = development.evaluate(doc)["actual"]["B"]
        self.assertEqual((summary["tp"], summary["u"]), (0, 6))
        self.assertIsNone(summary["precision_conditional"])
        self.assertEqual((summary["precision_lower"], summary["precision_upper"]), (0, 1))
        self.assertIsNone(summary["known_gold_recall"])
        self.assertIsNone(development.evaluate(_document(self, self.directory, gold=[]))
                          ["actual"]["B"]["precision_upper"])

    def test_overbudget_failure_cost_and_missing_trial_preserve_denominator(self):
        doc = _document(self, self.directory, gold=[{"cause_id": "cause-1", "independent_ref": "regression:1"}])
        doc["plan"]["budget"]["tokens_per_trial"] = 1
        missing = doc["executions"].pop()
        failed = doc["executions"][0]["calls"][0]
        failed["audit"] = {"perspective": failed["audit"]["perspective"], "status": "failed",
                           "reason": "provider_http_error", "tokens": 0,
                           "request_sha256": failed["audit"]["request_sha256"],
                           "candidates": [], "wall_seconds": .1}
        failed.update(response=None, billed_usd=.5, receipt_sha256=SHA)
        report = development.evaluate(doc)
        self.assertIn("overbudget_comparison_bundle", report["blocking_reasons"])
        self.assertIn("missing_or_failed_trial", report["blocking_reasons"])
        self.assertEqual(report["planned_actual_calls"], 51)
        self.assertEqual(report["actual"][missing["arm"]]["calls"]["missing"], len(missing["calls"]))
        self.assertEqual(report["actual"][doc["executions"][0]["arm"]]
                         ["reported_billed_usd_known_items"], .5)
        self.assertEqual(report["actual"]["B"]["known_gold_misses"], 3)
        self.assertIsNone(report["actual"]["B"]["reported_billed_usd"])

    def test_fixed_base_recombination_never_borrows_other_first_five(self):
        gold = [{"cause_id": name, "independent_ref": f"regression:{name}"}
                for name in ("cause-1", "cause-2")]
        doc = _document(self, self.directory, gold=gold, claims={
            ("B", 0): [{"claim": "base cause"}],
            ("B_generic", 0): [{"claim": "different first five"}],
            ("B_assumptions", 5): [{"claim": "assumption extra"}]})
        for trial in ("t1", "t2", "t3"):
            for arm, position, cause in (("B", 0, "cause-1"), ("B_generic", 0, "cause-2"),
                                         ("B_assumptions", 5, "cause-1")):
                doc["judgments"].append(_judgment(doc, trial, arm, position, 0, "TP", cause))
        report = development.evaluate(doc)
        self.assertEqual(report["actual"]["B_generic"]["tp"], 3)
        self.assertEqual(report["derived_fixed_B"]["B_plus_generic"]["tp"], 3)
        self.assertEqual(report["derived_fixed_B"]["B_plus_assumptions"]["tp"], 3)
        changed = copy.deepcopy(doc)
        generic = next(row for row in changed["executions"] if row["arm"] == "B_generic")
        generic["calls"][0]["audit"]["request_sha256"] = SHA
        with self.assertRaisesRegex(ValueError, "verified final bundle"):
            development.evaluate(changed)

    def test_baseline_candidate_overlap_not_gold_recall(self):
        doc = _document(self, self.directory, experiment="baseline", claims={
            ("strong_single", 0): [{"claim": "strong"}],
            ("small_single", 0): [{"claim": "same cause"}],
            ("small_five", 0): [{"claim": "unjudged"}]})
        for trial in ("t1", "t2", "t3"):
            doc["judgments"].append(_judgment(doc, trial, "strong_single", 0, 0, "FP", "false-cause"))
            doc["judgments"].append(_judgment(doc, trial, "small_single", 0, 0, "FP", "false-cause"))
        report = development.evaluate(doc)
        self.assertEqual(report["planned_actual_calls"], 21)
        self.assertEqual(report["paired"][0]["strong_candidate_overlap_not_recall"]["small_single"]["ratio"], 1)
        self.assertEqual(report["paired"][0]["strong_candidate_overlap_not_recall"]["small_five"]["ratio"], 0)
        self.assertEqual(report["actual"]["small_five"]["unknown_claims"], 3)
        self.assertIsNone(report["actual"]["strong_single"]["known_gold_recall"])

    def test_unplanned_duplicate_or_changed_provenance_rejected(self):
        doc = _document(self, self.directory, gold=[])
        doc["executions"].append(copy.deepcopy(doc["executions"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate execution"):
            development.evaluate(doc)
        doc["executions"].pop()
        first, second = doc["executions"][:2]
        doc["executions"][:2] = [second, first]
        with self.assertRaisesRegex(ValueError, "execution order"):
            development.evaluate(doc)
        doc["executions"][:2] = [first, second]
        doc["plan"]["cases"][0]["snapshot_sha"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "snapshot"):
            development.evaluate(doc)

    def test_plan_rejects_posthoc_strong_answers_wrong_order_and_scope(self):
        doc = _document(self, self.directory, gold=[])
        self.assertEqual(development.validate_plan(doc["plan"])["planned_actual_calls"], 51)
        doc["plan"]["cases"][0]["strong_candidate_causes"] = ["postrun"]
        with self.assertRaisesRegex(ValueError, "not preregistered"):
            development.validate_plan(doc["plan"])
        doc["plan"]["cases"][0]["strong_candidate_causes"] = None
        doc["plan"]["order"].reverse()
        with self.assertRaisesRegex(ValueError, "Order"):
            development.validate_plan(doc["plan"])
        doc["plan"]["order"].reverse()
        doc["plan"]["profiles"]["B_generic"]["prompt_sha256"] = SHA
        with self.assertRaisesRegex(ValueError, "current ordered role instructions"):
            development.validate_plan(doc["plan"])
        doc["plan"]["profiles"]["B_generic"]["prompt_sha256"] = prompt_hash("generic")
        self.assertEqual(development.validate_plan(doc["plan"])["planned_actual_calls"], 51)
        doc["plan"]["cases"][0]["scope"]["symbol"] = None
        with self.assertRaisesRegex(ValueError, "selected symbol"):
            development.validate_plan(doc["plan"])

    def test_static_artifact_must_replay_existing_counterexamples(self):
        doc = _document(self, self.directory, gold=[])
        doc["plan"]["static_baseline"] = {"enabled": True, "max_probes": 8,
                                          "kinds": ["zero_denominator", "empty_index"]}
        rows = [{"kind": "zero_denominator", "status": "static_hypothesis",
                 "path": "pkg/a.py", "entry_symbol": "pkg.a.f", "entry_line": 1,
                 "parameter": "x", "input_value": 0, "call_line": None,
                 "sink_symbol": "pkg.a.f", "sink_line": 2}]
        _patch(self, development, "prepare_analysis", lambda *_args, **_kwargs: (
            {}, {"symbol:pkg.a.f": {"nodes": [{"path": "pkg/a.py", "distance": 0}],
                                    "static_counterexamples": rows}}, None))
        body = {"case_id": "case", "snapshot_sha": SHA, "rows": rows}
        digest = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False,
                                           separators=(",", ":")).encode()).hexdigest()
        doc["static_baseline"] = [{**body, "sha256": digest}]
        report = development.evaluate(doc)
        self.assertEqual(report["N_static"]["status"], "git_static_replay_verified")
        self.assertEqual(report["N_static"]["cases"]["case"]["hypotheses"], 1)
        self.assertEqual(report["actual"]["B"]["tp"], 0)
        changed = copy.deepcopy(doc)
        changed["static_baseline"][0]["rows"][0]["sink_line"] = 3
        body = {key: changed["static_baseline"][0][key] for key in ("case_id", "snapshot_sha", "rows")}
        changed["static_baseline"][0]["sha256"] = hashlib.sha256(json.dumps(
            body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        with self.assertRaisesRegex(ValueError, "deterministic counterexamples"):
            development.evaluate(changed)


if __name__ == "__main__":
    unittest.main()
