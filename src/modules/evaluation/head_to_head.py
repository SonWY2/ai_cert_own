"""Offline comparison of evaluator-sealed, multi-finding model observations.

Seals bind records to the evaluator's key, but do not authenticate an API invoice,
clock, model invocation, oracle run, or hidden-label custody. Keep their raw logs.
"""

import random
from collections import Counter, defaultdict

from .paired import (_calibration, _hash, _required, _sha, _text, _time,
                     _uint, _unseal)

ARMS = ("S_strong_single", "F_runtime_feedback")
STATUSES = ("completed", "missing", "timeout", "tool_failure", "judge_failure")
TRUTH = ("executable_behavior_oracle", "known_regression_test", "hidden_mutation_manifest")


def _summary(rows, arm):
    tp = sum(len(row[arm]["matched"]) for row in rows)
    fp = sum(row[arm]["false_positives"] for row in rows)
    gold = sum(len(row["findings"]) for row in rows)
    cost = sum(row[arm]["cost_micro_usd"] for row in rows)
    return {"tp": tp, "fp": fp, "fn": gold - tp,
            "recall": tp / gold if gold else None,
            "precision": tp / (tp + fp) if tp + fp else None,
            "reported_api_cost_micro_usd": cost,
            "reported_cost_per_tp_micro_usd": cost / tp if tp else None,
            "calls": sum(row[arm]["calls"] for row in rows),
            "tokens": sum(row[arm]["tokens"] for row in rows),
            "status_counts": dict(sorted(Counter(row[arm]["status"] for row in rows).items()))}


def _interval(rows, seed, iterations):
    families = defaultdict(list)
    for row in rows:
        families[row["family_id"]].append(row)
    groups = list(families.values())
    rng = random.Random(seed)
    effects = []
    for _ in range(iterations):
        sampled = [item for _ in groups for item in groups[rng.randrange(len(groups))]]
        gold = sum(len(row["findings"]) for row in sampled)
        effect = sum(len(row[ARMS[1]]["matched"]) - len(row[ARMS[0]]["matched"])
                     for row in sampled)
        effects.append(100 * effect / gold if gold else 0.0)
    effects.sort()

    def percentile(p):
        index = p * (len(effects) - 1)
        low = int(index)
        return effects[low] + (effects[min(low + 1, len(effects) - 1)] - effects[low]) * (index - low)

    return [percentile(.025), percentile(.975)]


def evaluate(document, trusted_key):
    """Aggregate precommitted findings and independently matched predictions.

    This reads evidence claims, not actual model/provider/oracle systems. Results from
    test fixtures and missing external receipts cannot establish project performance.
    """
    if not isinstance(trusted_key, bytes) or len(trusted_key) < 32:
        raise ValueError("Independent evaluator key (>=32 bytes) required")
    _required(document, ("protocol", "freeze", "gold", "calibration", "results", "judgments"), "input")
    protocol = _unseal(document["protocol"], trusted_key,
                       ("version", "models", "judge", "budget", "strength_rationale",
                        "bootstrap_seed", "bootstrap_iterations"), "protocol")
    if protocol["version"] != "evaluation-protocol-v2":
        raise ValueError("Wrong head-to-head protocol")
    models = _required(protocol["models"], ARMS, "models")
    for arm, config in models.items():
        _required(config, ("version", "family", "prompt_sha256", "pricing_sha256", "sampling"), f"{arm} model")
        _text(config["version"], "model version")
        _text(config["family"], "model family")
        _sha(config["prompt_sha256"], "model prompt")
        _sha(config["pricing_sha256"], "model pricing")
        if not isinstance(config["sampling"], dict) or not config["sampling"]:
            raise ValueError("Model sampling settings required")
    if models[ARMS[0]]["version"] == models[ARMS[1]]["version"]:
        raise ValueError("Strong and small models must differ")
    _text(protocol["strength_rationale"], "model strength rationale")
    judge = _required(protocol["judge"],
                      ("model_version", "model_family", "prompt_sha256", "temperature"), "judge")
    _text(judge["model_version"], "judge version")
    _text(judge["model_family"], "judge family")
    _sha(judge["prompt_sha256"], "judge prompt")
    if (type(judge["temperature"]) not in (int, float) or judge["temperature"] != 0 or
            judge["model_family"] in {model["family"] for model in models.values()}):
        raise ValueError("Judge must differ from both model families and use temperature zero")
    budget = _required(protocol["budget"], ("token_limit", "wall_seconds_limit"), "budget")
    _uint(budget["token_limit"], "token limit", True)
    if type(budget["wall_seconds_limit"]) is not int or budget["wall_seconds_limit"] != 1200:
        raise ValueError("20-minute ceiling required")
    _uint(protocol["bootstrap_seed"], "bootstrap seed")
    _uint(protocol["bootstrap_iterations"], "bootstrap iterations", True)
    if protocol["bootstrap_iterations"] < 1000:
        raise ValueError("Too few bootstrap replicates")
    protocol_hash = _hash(protocol)
    freeze = _unseal(document["freeze"], trusted_key,
                     ("frozen_at", "development_cutoff", "arm_definitions_frozen_at",
                      "protocol_hash", "calibration_hash", "development_families",
                      "development_near_duplicates", "cases"), "freeze")
    frozen_at = _time(freeze["frozen_at"])
    cutoff = _time(freeze["development_cutoff"])
    if (freeze["protocol_hash"] != protocol_hash or cutoff >= frozen_at or
            _time(freeze["arm_definitions_frozen_at"]) > frozen_at):
        raise ValueError("Unfrozen protocol, arm or development cutoff")
    for field in ("development_families", "development_near_duplicates"):
        items = freeze[field]
        if not isinstance(items, list) or any(not isinstance(item, str) or not item for item in items) or len(set(items)) != len(items):
            raise ValueError("Invalid development family registry")
    calibration_hash = _calibration(document["calibration"], trusted_key, judge)
    if calibration_hash != freeze["calibration_hash"] or _time(document["calibration"]["calibrated_at"]) > cutoff:
        raise ValueError("Calibration must be frozen before development cutoff")
    cases = freeze["cases"]
    if not isinstance(cases, list) or len(cases) != 80:
        raise ValueError("Exactly 80 precommitted cases required")
    committed = {}
    for item in cases:
        _required(item, ("case_id", "gold_hash"), "frozen case")
        _text(item["case_id"], "case ID")
        _sha(item["gold_hash"], "gold hash")
        if item["case_id"] in committed:
            raise ValueError("Duplicate frozen case")
        committed[item["case_id"]] = item["gold_hash"]
    if not isinstance(document["gold"], list) or len(document["gold"]) != 80:
        raise ValueError("Exactly 80 independently sealed gold cases required")
    gold = {}
    lane_counts = Counter()
    family_split = {}
    duplicate_split = {}
    for signed in document["gold"]:
        item = _unseal(signed, trusted_key,
                       ("case_id", "family_id", "near_duplicate_group", "snapshot_sha",
                        "lane", "stratum", "source_type", "revision", "license",
                        "sealed_at", "released_at", "findings"), "gold")
        cid = _text(item["case_id"], "case ID")
        if cid not in committed or cid in gold or _hash(item) != committed[cid] or _time(item["sealed_at"]) > frozen_at:
            raise ValueError("Gold differs from precommitted freeze")
        _sha(item["snapshot_sha"], "source snapshot")
        for field in ("family_id", "near_duplicate_group"):
            _text(item[field], field)
        if item["lane"] not in ("hidden_synthetic_holdout", "temporal_public_holdout") or item["stratum"] not in ("scheduled_main", "release_candidate"):
            raise ValueError("Invalid case split")
        if item["lane"] == "temporal_public_holdout":
            if (item["source_type"] != "public_repository" or
                    not cutoff < _time(item["released_at"]) <= frozen_at):
                raise ValueError("Temporal case is not post-cutoff public source")
            _text(item["revision"], "public revision")
            _text(item["license"], "public license")
        elif (item["source_type"] != "project_owned_synthetic_fixture" or
              any(item[field] is not None for field in ("revision", "license", "released_at"))):
            raise ValueError("Hidden case must be an owned synthetic fixture")
        for field, registry, development in (("family_id", family_split, freeze["development_families"]),
                                              ("near_duplicate_group", duplicate_split, freeze["development_near_duplicates"])):
            name = item[field]
            split = (item["stratum"], item["lane"])
            if name in development or name in registry and registry[name] != split:
                raise ValueError("Family/near duplicate crosses development or final splits")
            registry[name] = split
        if not isinstance(item["findings"], list):
            raise ValueError("Gold findings must be a list, including empty negatives")
        findings = {}
        for finding in item["findings"]:
            _required(finding, ("finding_id", "risk_type", "severity", "cross_file",
                                "root_cause_symbol", "truth_source", "oracle_sha256"), "gold finding")
            fid = _text(finding["finding_id"], "finding ID")
            if fid in findings or finding["severity"] not in ("critical", "high", "medium", "low") or type(finding["cross_file"]) is not bool or finding["truth_source"] not in TRUTH:
                raise ValueError("Duplicate or invalid gold finding")
            _text(finding["risk_type"], "risk type")
            _text(finding["root_cause_symbol"], "root cause")
            _sha(finding["oracle_sha256"], "oracle evidence hash")
            findings[fid] = finding
        item["findings"] = findings
        gold[cid] = item
        lane_counts[item["stratum"], item["lane"]] += 1
    if set(gold) != set(committed) or any(lane_counts[stratum, lane] != 20 for stratum in ("scheduled_main", "release_candidate") for lane in ("hidden_synthetic_holdout", "temporal_public_holdout")):
        raise ValueError("Invalid final allocation")
    results = {}
    needed = {}
    receipts = set()
    if not isinstance(document["results"], list) or len(document["results"]) != 80 * len(ARMS):
        raise ValueError("Exactly two arm outputs per frozen case required")
    for signed in document["results"]:
        item = _unseal(signed, trusted_key,
                       ("case_id", "arm", "snapshot_sha", "protocol_hash", "status", "started_at",
                        "ended_at", "tokens_used", "tool_seconds_used", "calls", "predictions",
                        "unsafe_execution", "unjustified_high_dismissal"), "result")
        cid, arm = item["case_id"], item["arm"]
        if cid not in gold or arm not in ARMS or (cid, arm) in results:
            raise ValueError("Unknown or duplicate case-arm result")
        if item["snapshot_sha"] != gold[cid]["snapshot_sha"] or item["protocol_hash"] != protocol_hash:
            raise ValueError("Changed snapshot or protocol")
        started, ended = _time(item["started_at"]), _time(item["ended_at"])
        if started <= frozen_at or ended < started:
            raise ValueError("Output predates frozen holdout or reverses time")
        if item["status"] not in STATUSES or type(item["unsafe_execution"]) is not bool or type(item["unjustified_high_dismissal"]) is not bool:
            raise ValueError("Invalid result status or safety flag")
        if item["unsafe_execution"] or arm == ARMS[1] and item["unjustified_high_dismissal"]:
            raise ValueError("Unsafe execution or proposed Critical/High dismissal")
        _uint(item["tokens_used"], "tokens used")
        _uint(item["tool_seconds_used"], "tool seconds used")
        if not isinstance(item["calls"], list) or not isinstance(item["predictions"], list):
            raise ValueError("Calls and predictions must be lists")
        if arm == ARMS[0] and len(item["calls"]) > 1 or item["status"] == "completed" and not item["calls"]:
            raise ValueError("Strong baseline is one model call; completed system needs calls")
        if item["status"] != "completed" and item["predictions"]:
            raise ValueError("Failed output cannot emit findings")
        total_tokens = cost = 0
        for call in item["calls"]:
            _required(call, ("model_version", "input_tokens", "cache_input_tokens", "output_tokens",
                             "billed_micro_usd", "receipt_sha256"), "model call")
            if call["model_version"] != models[arm]["version"]:
                raise ValueError("Wrong model on arm call")
            for name in ("input_tokens", "cache_input_tokens", "output_tokens", "billed_micro_usd"):
                _uint(call[name], name)
            if call["cache_input_tokens"] > call["input_tokens"]:
                raise ValueError("Cached tokens exceed input tokens")
            _sha(call["receipt_sha256"], "billing receipt hash")
            if call["receipt_sha256"] in receipts:
                raise ValueError("Reused model billing receipt")
            receipts.add(call["receipt_sha256"])
            total_tokens += call["input_tokens"] + call["output_tokens"]
            cost += call["billed_micro_usd"]
        if total_tokens != item["tokens_used"] or total_tokens > budget["token_limit"]:
            raise ValueError("Total operational tokens mismatch or exceed budget")
        predictions = set()
        for prediction in item["predictions"]:
            _required(prediction, ("risk_type", "severity", "root_cause_symbol", "hypothesis",
                                   "next_action", "evidence_snapshot_sha"), "prediction")
            for name in ("risk_type", "root_cause_symbol", "hypothesis", "next_action"):
                _text(prediction[name], name)
            if prediction["severity"] not in ("critical", "high", "medium", "low") or prediction["evidence_snapshot_sha"] != gold[cid]["snapshot_sha"]:
                raise ValueError("Invalid prediction severity or evidence snapshot")
            digest = _hash(prediction)
            if digest in predictions:
                raise ValueError("Duplicate prediction in one output")
            predictions.add(digest)
            key = (cid, digest)
            needed[key] = max(needed.get(key, ended), ended)
        item["prediction_hashes"] = predictions
        item["cost_micro_usd"] = cost
        item["within_time"] = (ended - started).total_seconds() <= budget["wall_seconds_limit"]
        results[cid, arm] = item
    if len(results) != 80 * len(ARMS):
        raise ValueError("Missing paired result")
    judgments = {}
    if not isinstance(document["judgments"], list):
        raise ValueError("Judgments must be a list")
    for signed in document["judgments"]:
        item = _unseal(signed, trusted_key,
                       ("case_id", "snapshot_sha", "prediction_hash", "gold_finding_id",
                        "oracle_sha256", "oracle_supported", "judged_valid", "reason_code",
                        "judged_at", "calibration_hash", "model_version", "model_family",
                        "prompt_sha256", "temperature", "blinded", "randomized_order",
                        "unsafe_execution", "unjustified_high_dismissal"), "judgment")
        key = (item["case_id"], item["prediction_hash"])
        if key not in needed or key in judgments or item["snapshot_sha"] != gold[key[0]]["snapshot_sha"]:
            raise ValueError("Orphan, duplicate, or wrong-snapshot judgment")
        if (_time(item["judged_at"]) < needed[key] or item["calibration_hash"] != calibration_hash or
                any(item[name] != judge[name] for name in judge) or
                item["blinded"] is not True or item["randomized_order"] is not True):
            raise ValueError("Uncalibrated, unblinded, or premature judgment")
        for name in ("oracle_supported", "judged_valid", "unsafe_execution", "unjustified_high_dismissal"):
            if type(item[name]) is not bool:
                raise ValueError("Judgment safety and validity flags must be boolean")
        if item["unsafe_execution"] or (item["unjustified_high_dismissal"] and
                                        key[1] in results[key[0], ARMS[1]]["prediction_hashes"]):
            raise ValueError("Unsafe execution or proposed Critical/High dismissal")
        fid = item["gold_finding_id"]
        if fid is None:
            if item["oracle_sha256"] is not None or item["oracle_supported"]:
                raise ValueError("Unmatched prediction cannot claim oracle support")
        elif fid not in gold[key[0]]["findings"]:
            raise ValueError("Judgment cites unknown gold finding")
        elif item["oracle_sha256"] != gold[key[0]]["findings"][fid]["oracle_sha256"]:
            raise ValueError("Oracle evidence hash mismatch")
        _text(item["reason_code"], "judge reason")
        judgments[key] = item
    if set(judgments) != set(needed):
        raise ValueError("Missing independent judgment for completed prediction")
    rows = []
    exclusive = {"strong_only": [], "system_only": [], "missed_by_both": []}
    high_total = high_tp = 0
    for cid in sorted(gold):
        case = gold[cid]
        row = {"family_id": case["family_id"], "lane": case["lane"],
               "stratum": case["stratum"], "findings": case["findings"]}
        for arm in ARMS:
            result = results[cid, arm]
            matched = set()
            fp = 0
            if result["status"] == "completed" and result["within_time"]:
                for digest in result["prediction_hashes"]:
                    verdict = judgments[cid, digest]
                    fid = verdict["gold_finding_id"]
                    if fid is not None and verdict["oracle_supported"] and verdict["judged_valid"] and fid not in matched:
                        matched.add(fid)
                    else:
                        fp += 1
            row[arm] = {"matched": matched, "false_positives": fp,
                        "cost_micro_usd": result["cost_micro_usd"], "calls": len(result["calls"]),
                        "tokens": result["tokens_used"], "status": result["status"]}
        for fid, finding in case["findings"].items():
            strong = fid in row[ARMS[0]]["matched"]
            system = fid in row[ARMS[1]]["matched"]
            if finding["severity"] in ("critical", "high"):
                high_total += 1
                high_tp += system
            if strong and system:
                continue
            label = "strong_only" if strong else "system_only" if system else "missed_by_both"
            exclusive[label].append({"case_id": cid, "finding_id": fid,
                                     "risk_type": finding["risk_type"],
                                     "severity": finding["severity"],
                                     "cross_file": finding["cross_file"]})
        rows.append(row)
    overall = {arm: _summary(rows, arm) for arm in ARMS}
    if overall[ARMS[0]]["recall"] is None:
        raise ValueError("No sealed defects to compare")
    interval = _interval(rows, protocol["bootstrap_seed"], protocol["bootstrap_iterations"])
    difference = 100 * (overall[ARMS[1]]["recall"] - overall[ARMS[0]]["recall"])
    return {"cases": 80, "gold_findings": sum(len(row["findings"]) for row in rows),
            "overall": overall, "per_lane": {lane: {arm: _summary([row for row in rows if row["lane"] == lane], arm) for arm in ARMS}
                                            for lane in ("hidden_synthetic_holdout", "temporal_public_holdout")},
            "per_stratum": {stratum: {arm: _summary([row for row in rows if row["stratum"] == stratum], arm) for arm in ARMS}
                            for stratum in ("scheduled_main", "release_candidate")},
            "exclusive_gold_findings": exclusive, "system_critical_high_recall": high_tp / high_total if high_total else None,
            "recall_difference_percentage_points": difference,
            "family_bootstrap_95_ci_percentage_points": interval,
            "bootstrap_seed": protocol["bootstrap_seed"],
            "bootstrap_iterations": protocol["bootstrap_iterations"],
            "distinct_families": len(family_split),
            "meets_head_to_head_gate": interval[0] > 0 and high_total > 0 and high_tp / high_total >= .90 and
            overall[ARMS[1]]["recall"] >= .85 and overall[ARMS[1]]["precision"] is not None and
            overall[ARMS[1]]["precision"] >= .75}
