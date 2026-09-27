"""Fail-closed, offline aggregation of independently sealed final-holdout observations.

A keyed seal authenticates the evaluator's records; it cannot prove that an evaluator
actually ran a model or that a timestamp is a trusted clock. The signing key must
remain outside the evaluated system. No source code or candidate action is executed.
"""

import hashlib
import hmac
import json
import math
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone

ARMS = ("A_plain_llm", "B_structured_review", "C_static_facts",
        "D_graph_context", "E_evidence_contract", "F_runtime_feedback")
LANES = ("hidden_synthetic_holdout", "temporal_public_holdout")
STRATA = ("scheduled_main", "release_candidate")
COMPLEXITY = ("standard", "complex")
FAILURES = ("missing", "timeout", "tool_failure", "judge_failure")


def _required(record, fields, label):
    if not isinstance(record, dict) or set(record) != set(fields):
        raise ValueError(f"{label}: expected fields {sorted(fields)}")
    return record


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}: nonempty text required")
    return value


def _hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def seal(record, key):
    """Seal a *prior* evaluator-owned record; keep key outside evaluation input.

    This helper is for a trusted independent producer, not a substitute for
    performing an experiment or for creating oracle/LLM adjudications.
    """
    if not isinstance(record, dict) or "seal" in record or not isinstance(key, bytes) or len(key) < 32:
        raise ValueError("Record must be unsigned and evaluator key at least 32 bytes")
    return {**record, "seal": hmac.new(key, _hash(record).encode("ascii"), hashlib.sha256).hexdigest()}


def _unseal(record, key, fields, label):
    _required(record, set(fields) | {"seal"}, label)
    raw = {name: value for name, value in record.items() if name != "seal"}
    if not isinstance(record["seal"], str) or not hmac.compare_digest(
            record["seal"], seal(raw, key)["seal"]):
        raise ValueError(f"{label}: invalid independent evaluator seal")
    return raw


def _time(value):
    _text(value, "timestamp")
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid ISO timestamp") from exc
    if instant.tzinfo is None or instant.utcoffset() != timezone.utc.utcoffset(instant):
        raise ValueError("Timestamp must be UTC")
    return instant


def _sha(value, label):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label}: expected lowercase SHA-256")


def _uint(value, label, positive=False):
    if type(value) is not int or value < (1 if positive else 0):
        raise ValueError(f"{label}: invalid integer")


def _number(value, label):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{label}: invalid nonnegative finite number")


def _budget(value):
    _required(value, ("token_limit", "tool_seconds_limit", "wall_seconds_limit", "retry_limit",
                      "output_schema", "model_version", "sampling"), "budget")
    for name in ("token_limit", "tool_seconds_limit"):
        _uint(value[name], name, True)
    _uint(value["retry_limit"], "retry_limit")
    if value["wall_seconds_limit"] != 1200 or type(value["wall_seconds_limit"]) is not int:
        raise ValueError("20-minute wall ceiling is mandatory")
    _text(value["output_schema"], "output_schema")
    _text(value["model_version"], "model_version")
    if not isinstance(value["sampling"], dict) or not value["sampling"]:
        raise ValueError("Sampling settings must be frozen")


def _calibration(record, key, judge):
    value = _unseal(record, key, ("calibrated_at", "model_version", "model_family",
                                  "prompt_sha256", "temperature", "decisions"), "calibration")
    _time(value["calibrated_at"])
    if any(value[field] != judge[field] for field in ("model_version", "model_family", "prompt_sha256", "temperature")):
        raise ValueError("Judge calibration/config mismatch")
    decisions = value["decisions"]
    if not isinstance(decisions, list) or len(decisions) < 2:
        raise ValueError("Calibration requires known valid and invalid decisions")
    labels = set()
    correct = 0
    for entry in decisions:
        _required(entry, ("known_valid", "judged_valid"), "calibration decision")
        if type(entry["known_valid"]) is not bool or type(entry["judged_valid"]) is not bool:
            raise ValueError("Calibration decisions must be boolean")
        labels.add(entry["known_valid"])
        correct += entry["known_valid"] == entry["judged_valid"]
    if labels != {False, True} or correct / len(decisions) < .90:
        raise ValueError("Uncalibrated judge")
    return _hash(value)


def _rate(rows):
    return {arm: {"valid": sum(row[arm] for row in rows), "total": len(rows),
                  "rate": sum(row[arm] for row in rows) / len(rows)} for arm in ARMS}


def _bootstrap(rows, iterations, seed):
    families = defaultdict(list)
    for row in rows:
        families[row["family_id"]].append(row)
    groups = list(families.values())  # case order is normalized before this call
    rng = random.Random(seed)
    effects = []
    for _ in range(iterations):
        draw = [row for _ in groups for row in groups[rng.randrange(len(groups))]]
        effects.append(100 * sum(row[ARMS[-1]] - row[ARMS[0]] for row in draw) / len(draw))
    effects.sort()
    def quantile(p):
        index = p * (len(effects) - 1)
        low = int(index)
        return effects[low] + (effects[min(low + 1, len(effects) - 1)] - effects[low]) * (index - low)
    return [quantile(.025), quantile(.975)]


def evaluate(document, trusted_key):
    """Validate sealed raw observations and calculate final paired metrics.

    Raises ValueError instead of producing partial aggregates or success claims.
    All timestamps, telemetry, gold and adjudications require the independently
    held evaluator key. Output only describes the supplied data, not a real run.
    """
    if not isinstance(trusted_key, bytes) or len(trusted_key) < 32:
        raise ValueError("Independent evaluator key (>=32 bytes) required")
    _required(document, ("protocol", "freeze", "gold", "calibration", "results",
                         "oracles", "judgments"), "input")
    protocol = _unseal(document["protocol"], trusted_key,
                       ("version", "budget", "judge", "bootstrap_seed", "bootstrap_iterations"), "protocol")
    if protocol["version"] != "evaluation-protocol-v1":
        raise ValueError("Wrong protocol")
    _budget(protocol["budget"])
    judge = _required(protocol["judge"], ("model_version", "model_family", "prompt_sha256",
                                           "temperature", "evaluated_model_family"), "judge config")
    for name in ("model_version", "model_family", "evaluated_model_family"):
        _text(judge[name], name)
    if judge["model_family"] == judge["evaluated_model_family"] or judge["temperature"] != 0 or type(judge["temperature"]) not in (int, float):
        raise ValueError("Judge must use a separate model family at temperature zero")
    _sha(judge["prompt_sha256"], "prompt_sha256")
    _uint(protocol["bootstrap_seed"], "bootstrap_seed")
    _uint(protocol["bootstrap_iterations"], "bootstrap_iterations", True)
    if protocol["bootstrap_iterations"] < 1000:
        raise ValueError("Too few bootstrap replicates")
    protocol_hash = _hash(protocol)
    freeze = _unseal(document["freeze"], trusted_key,
                     ("frozen_at", "protocol_hash", "calibration_hash", "cases", "development_families",
                      "development_near_duplicates", "development_cutoff", "arm_definitions_frozen_at"), "freeze")
    frozen_at = _time(freeze["frozen_at"])
    if freeze["protocol_hash"] != protocol_hash or _time(freeze["arm_definitions_frozen_at"]) > frozen_at:
        raise ValueError("Protocol or arm definitions not frozen before cases")
    cutoff = _time(freeze["development_cutoff"])
    if cutoff >= frozen_at:
        raise ValueError("Development cutoff must precede final freeze")
    for name in ("development_families", "development_near_duplicates"):
        if not isinstance(freeze[name], list) or any(not isinstance(v, str) or not v for v in freeze[name]) or len(set(freeze[name])) != len(freeze[name]):
            raise ValueError("Invalid development family/near-duplicate registry")
    registered = freeze["cases"]
    if not isinstance(registered, list) or len(registered) != 80:
        raise ValueError("Exactly 80 frozen cases required")
    case_map = {}
    counts = Counter()
    family_split = {}
    duplicate_split = {}
    for entry in registered:
        _required(entry, ("case_id", "gold_hash"), "frozen case")
        case_id = _text(entry["case_id"], "case_id")
        _sha(entry["gold_hash"], "gold_hash")
        if case_id in case_map:
            raise ValueError("Duplicate frozen case")
        case_map[case_id] = entry["gold_hash"]
    calibration_hash = _calibration(document["calibration"], trusted_key, judge)
    if calibration_hash != freeze["calibration_hash"] or _time(document["calibration"]["calibrated_at"]) > cutoff:
        raise ValueError("Calibration must be frozen before development cutoff")
    gold = document["gold"]
    if not isinstance(gold, list) or len(gold) != 80:
        raise ValueError("Every frozen case needs sealed gold")
    by_case = {}
    for sealed in gold:
        value = _unseal(sealed, trusted_key,
                        ("case_id", "family_id", "near_duplicate_group", "snapshot_sha",
                         "lane", "stratum", "complexity", "source_type", "revision", "license",
                         "sealed_at", "released_at", "expected_invariant", "root_cause_symbol", "impact",
                         "acceptable_priorities", "oracle_command", "truth_source", "truth_conflict"), "gold")
        cid = _text(value["case_id"], "case_id")
        if cid not in case_map or cid in by_case or _hash(value) != case_map[cid] or _time(value["sealed_at"]) > frozen_at:
            raise ValueError("Gold differs from precommitted freeze")
        _sha(value["snapshot_sha"], "snapshot_sha")
        if value["released_at"] is not None and _time(value["released_at"]) > frozen_at:
            raise ValueError("Case was not released before final freeze")
        for field in ("family_id", "near_duplicate_group", "expected_invariant", "root_cause_symbol", "impact"):
            _text(value[field], field)
        if value["lane"] not in LANES or value["stratum"] not in STRATA or value["complexity"] not in COMPLEXITY:
            raise ValueError("Invalid final case split")
        if value["source_type"] == "public_repository":
            _text(value["revision"], "revision")
            _text(value["license"], "license")
        elif value["source_type"] == "project_owned_synthetic_fixture":
            if value["revision"] is not None or value["license"] is not None:
                raise ValueError("Synthetic fixture has false public provenance")
        else:
            raise ValueError("Unadmitted source")
        if value["lane"] == LANES[1]:
            if value["source_type"] != "public_repository" or value["released_at"] is None or _time(value["released_at"]) <= cutoff:
                raise ValueError("Temporal public case must be versioned and released after development cutoff")
        elif value["source_type"] != "project_owned_synthetic_fixture" or value["released_at"] is not None:
            raise ValueError("Hidden synthetic lane requires owned fixtures")
        if not isinstance(value["acceptable_priorities"], list) or not value["acceptable_priorities"] or len(set(value["acceptable_priorities"])) != len(value["acceptable_priorities"]) or any(not isinstance(v, str) or not v for v in value["acceptable_priorities"]):
            raise ValueError("Invalid sealed acceptable priority set")
        if value["oracle_command"] is not None:
            _text(value["oracle_command"], "oracle_command")
        if value["truth_source"] not in ("executable_behavior_oracle", "known_regression_test", "hidden_mutation_manifest") or value["truth_conflict"] is not False:
            raise ValueError("Unresolved truth or LLM-only oracle")
        for item, mapping, development in ((value["family_id"], family_split, freeze["development_families"]),
                                            (value["near_duplicate_group"], duplicate_split, freeze["development_near_duplicates"])):
            split = (value["stratum"], value["lane"])
            if item in development or item in mapping and mapping[item] != split:
                raise ValueError("Family or near duplicate crosses development/final or final strata")
            mapping[item] = split
        counts[value["stratum"], value["lane"]] += 1
        by_case[cid] = value
    if set(by_case) != set(case_map) or any(counts[stratum, lane] != 20 for stratum in STRATA for lane in LANES):
        raise ValueError("Missing gold or invalid 20-per-stratum allocation")
    if {value["complexity"] for value in by_case.values()} != set(COMPLEXITY):
        raise ValueError("Both complexity reporting strata are required")
    results = document["results"]
    if not isinstance(results, list) or len(results) != 80 * len(ARMS):
        raise ValueError("Exactly six outputs per frozen case required, including missing failures")
    by_result = {}
    verdict_needs = set()
    for sealed in results:
        value = _unseal(sealed, trusted_key,
                        ("case_id", "arm", "snapshot_sha", "protocol_hash", "budget", "status",
                         "started_at", "ended_at", "wall_seconds", "tokens_used", "tool_seconds_used",
                         "retries_used", "candidate"), "result")
        cid, arm = value["case_id"], value["arm"]
        if cid not in by_case or arm not in ARMS or (cid, arm) in by_result:
            raise ValueError("Unknown/duplicate case-arm output")
        if value["snapshot_sha"] != by_case[cid]["snapshot_sha"] or value["protocol_hash"] != protocol_hash or value["budget"] != protocol["budget"]:
            raise ValueError("Changed snapshot, protocol or per-arm budget")
        started, ended = _time(value["started_at"]), _time(value["ended_at"])
        if started <= frozen_at or ended < started:
            raise ValueError("Result predates frozen holdout or reversed timing")
        _number(value["wall_seconds"], "wall_seconds")
        _number(value["tool_seconds_used"], "tool_seconds_used")
        for field in ("tokens_used", "retries_used"):
            _uint(value[field], field)
        if abs((ended - started).total_seconds() - value["wall_seconds"]) > 1:
            raise ValueError("Reported wall clock conflicts with timestamps")
        if value["tokens_used"] > value["budget"]["token_limit"] or value["tool_seconds_used"] > value["budget"]["tool_seconds_limit"] or value["retries_used"] > value["budget"]["retry_limit"]:
            raise ValueError("Budget exceeded")
        if value["status"] not in ("completed", *FAILURES):
            raise ValueError("Unknown result status")
        if value["status"] == "completed":
            candidate = _required(value["candidate"], ("selected_risk", "evidence_snapshot_sha",
                                        "hypothesis", "next_action", "workload", "oracle", "dismissed_risks"), "candidate")
            for name in ("selected_risk", "hypothesis", "next_action"):
                _text(candidate[name], name)
            _sha(candidate["evidence_snapshot_sha"], "evidence_snapshot_sha")
            if candidate["evidence_snapshot_sha"] != value["snapshot_sha"]:
                raise ValueError("Evidence uses another snapshot")
            if candidate["workload"] is not None:
                _text(candidate["workload"], "workload")
                _text(candidate["oracle"], "oracle")
            elif candidate["oracle"] is not None:
                raise ValueError("Oracle without workload")
            if not isinstance(candidate["dismissed_risks"], list) or len(candidate["dismissed_risks"]) != len(set(candidate["dismissed_risks"])) or any(not isinstance(v, str) or not v for v in candidate["dismissed_risks"]):
                raise ValueError("Malformed dismissed risks")
            verdict_needs.add((cid, _hash(candidate)))
        elif value["candidate"] is not None:
            raise ValueError("Failed output cannot claim a candidate")
        by_result[cid, arm] = value
    verdicts = {}
    for label, records, fields in (("oracle", document["oracles"],
                                    ("case_id", "snapshot_sha", "candidate_hash", "evaluated_at", "truth_source",
                                     "priority_acceptable", "evidence_supported", "action_falsifiable",
                                     "workload_oracle_adequate", "unjustified_high_dismissal", "unsafe_execution")),
                                   ("judge", document["judgments"],
                                    ("case_id", "snapshot_sha", "candidate_hash", "judged_at", "calibration_hash",
                                     "model_version", "model_family", "prompt_sha256", "temperature", "blinded",
                                     "randomized_order", "valid", "reason_code"))):
        if not isinstance(records, list):
            raise ValueError(f"{label}: records must be a list")
        indexed = {}
        for sealed in records:
            value = _unseal(sealed, trusted_key, fields, label)
            cid, candidate_hash = value["case_id"], value["candidate_hash"]
            _sha(candidate_hash, "candidate_hash")
            key = (cid, candidate_hash)
            if key not in verdict_needs or key in indexed or value["snapshot_sha"] != by_case[cid]["snapshot_sha"]:
                raise ValueError(f"{label}: orphan, duplicate, or wrong snapshot")
            stamp = _time(value["evaluated_at" if label == "oracle" else "judged_at"])
            if stamp <= frozen_at or any(stamp < _time(row["ended_at"]) for (case, _), row in by_result.items()
                                      if case == cid and row["status"] == "completed" and _hash(row["candidate"]) == candidate_hash):
                raise ValueError(f"{label}: predates candidate")
            if label == "oracle":
                if value["truth_source"] != by_case[cid]["truth_source"]:
                    raise ValueError("Oracle truth source mismatch")
                for field in ("priority_acceptable", "evidence_supported", "action_falsifiable",
                              "workload_oracle_adequate", "unjustified_high_dismissal", "unsafe_execution"):
                    if type(value[field]) is not bool:
                        raise ValueError("Oracle verdict must be boolean")
            else:
                if value["calibration_hash"] != calibration_hash or any(value[field] != judge[field] for field in ("model_version", "model_family", "prompt_sha256", "temperature")) or value["blinded"] is not True or value["randomized_order"] is not True:
                    raise ValueError("Invalid blinded calibrated judge")
                if type(value["valid"]) is not bool or not isinstance(value["reason_code"], str) or not value["reason_code"]:
                    raise ValueError("Malformed judge decision")
            indexed[key] = value
        if set(indexed) != verdict_needs:
            raise ValueError(f"Missing {label} verdict")
        verdicts[label] = indexed
    rows = []
    unjustified_f = 0
    unsafe = 0
    for cid in sorted(by_case):
        gold_case = by_case[cid]
        row = {"case_id": cid, "family_id": gold_case["family_id"], "lane": gold_case["lane"],
               "stratum": gold_case["stratum"], "complexity": gold_case["complexity"]}
        for arm in ARMS:
            result = by_result[cid, arm]
            valid = False
            if result["status"] == "completed":
                candidate = result["candidate"]
                key = (cid, _hash(candidate))
                oracle = verdicts["oracle"][key]
                judged = verdicts["judge"][key]
                if oracle["priority_acceptable"] != (candidate["selected_risk"] in gold_case["acceptable_priorities"]):
                    raise ValueError("Oracle priority verdict conflicts with sealed gold")
                if candidate["workload"] is not None and gold_case["oracle_command"] is None:
                    raise ValueError("Executable action has no sealed oracle")
                if oracle["workload_oracle_adequate"] and (candidate["workload"] is None or gold_case["oracle_command"] is None):
                    raise ValueError("Oracle approved missing target workload")
                unsafe += oracle["unsafe_execution"]
                if arm == ARMS[-1]:
                    unjustified_f += oracle["unjustified_high_dismissal"]
                valid = (result["wall_seconds"] <= 1200 and oracle["priority_acceptable"]
                         and oracle["evidence_supported"] and oracle["action_falsifiable"]
                         and (candidate["workload"] is None or oracle["workload_oracle_adequate"])
                         and not oracle["unjustified_high_dismissal"] and not oracle["unsafe_execution"]
                         and judged["valid"])
            row[arm] = int(valid)
        rows.append(row)
    if unsafe:
        raise ValueError("Unsafe execution in final results")
    if unjustified_f:
        raise ValueError("Proposed arm unjustifiably dismissed Critical/High risk")
    by_lane = {lane: _rate([row for row in rows if row["lane"] == lane]) for lane in LANES}
    by_stratum = {stratum: _rate([row for row in rows if row["stratum"] == stratum]) for stratum in STRATA}
    by_complexity = {kind: _rate([row for row in rows if row["complexity"] == kind]) for kind in COMPLEXITY}
    overall = _rate(rows)
    difference = 100 * (overall[ARMS[-1]]["rate"] - overall[ARMS[0]]["rate"])
    interval = _bootstrap(rows, protocol["bootstrap_iterations"], protocol["bootstrap_seed"])
    return {"cases": 80, "arms": list(ARMS), "per_lane": by_lane, "per_stratum": by_stratum,
            "per_complexity": by_complexity, "overall": overall,
            "primary_A_vs_F_percentage_points": difference,
            "family_bootstrap_95_ci_percentage_points": interval,
            "bootstrap_seed": protocol["bootstrap_seed"], "bootstrap_iterations": protocol["bootstrap_iterations"],
            "distinct_families": len(family_split), "proposed_unjustified_high_dismissals": unjustified_f,
            "unsafe_execution_count": unsafe,
            "meets_primary_gate": difference >= 30 and interval[0] > 0 and unjustified_f == 0}
