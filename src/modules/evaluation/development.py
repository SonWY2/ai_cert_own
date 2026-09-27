"""Offline development evidence comparison, never a final-holdout score.

Local Git/final/normalized-response replay proves consistency of stored bytes only.
Neither external adjudication, provider usage, invoices, clocks nor model identity is
independently authenticated by this document. Missing records remain in the plan.
"""

import hashlib
import json
import math
import os
import random
import stat
from pathlib import Path

from modules.diagnosis.model import verify_responses
from modules.diagnosis.model import prompt_hash
from modules.diagnosis.plan import prepare_analysis
from modules.evidence.authenticity import verify_git_source
from modules.evidence.final_bundle import verify_final_bundle


BASE = ("structure", "correctness", "performance", "concurrency", "tests")
SIXTH_ROLES = {"B": BASE, "B_generic": (*BASE, "generic"),
               "B_assumptions": (*BASE, "assumptions")}
BASELINE_ROLES = {"small_single": ("all",), "small_five": BASE,
                  "strong_single": ("all",)}
STAGE_PAIRS = (("P0", "P1"), ("P1", "P2a"), ("P2a", "P2b"))
STATUSES = ("completed", "failed", "deferred")


def _fields(value, fields, label):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError(f"{label}: expected exactly {sorted(fields)}")
    return value


def _list(value, label):
    if not isinstance(value, list):
        raise ValueError(f"{label}: expected list")
    return value


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}: nonempty string required")
    return value


def _integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{label}: integer >= {minimum} required")
    return value


def _number(value, label):
    if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{label}: finite nonnegative number required")
    return value


def _sha(value, label):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label}: lowercase SHA-256 required")
    return value


def _distinct(values, label):
    if len(set(values)) != len(values):
        raise ValueError(f"{label}: duplicate identity")


def _read_response(reference):
    """Read owner-only bytes without following symlinks; verify their SHA before use."""
    path = Path(os.path.abspath(reference["path"]))
    descriptors = []
    try:
        directory = os.open(path.parts[0], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(directory)
        for part in path.parts[1:-1]:
            directory = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            descriptors.append(directory)
        descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        descriptors.append(descriptor)
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or
                stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > 4 * 1024 * 1024):
            raise ValueError("Response artifact must be an owner-only bounded file")
        with os.fdopen(os.dup(descriptor), "rb") as stream:
            raw = stream.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != reference["response_sha256"]:
            raise ValueError("Response artifact hash mismatch")
        return json.loads(raw, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("Response artifact unavailable") from error
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def _summary(rows, gold):
    raw = sum(row["raw"] for row in rows)
    accepted = sum(row["accepted"] for row in rows)
    causes = {item for row in rows for item in row["tp"] | row["fp"]}
    tp = {item for row in rows for item in row["tp"]}
    fp = {item for row in rows for item in row["fp"]}
    # A cause is scoped to its case and trial, never merged across independent trials.
    unknown = sum(row["unknown"] for row in rows)
    judged = len(tp) + len(fp)
    total = judged + unknown
    known = sum(len(gold[row["case_id"]]) for row in rows if gold[row["case_id"]] is not None)
    missing_gold = sum(gold[row["case_id"]] is None for row in rows)
    matched = sum(len(row["tp"]) for row in rows)
    known_misses = sum(len(set(gold[row["case_id"]]) - {cause for _, _, cause in row["tp"]})
                       for row in rows if gold[row["case_id"]] is not None)
    usd = [row["billed_usd"] for row in rows]
    return {"raw_claims": raw, "accepted_claims": accepted,
            "unverified_claims": raw - accepted,
            "unknown_claims": unknown, "unique_causes": len(causes),
            "tp": len(tp), "fp": len(fp), "u": unknown,
            "precision_conditional": _ratio(len(tp), judged),
            "precision_lower": _ratio(len(tp), total),
            "precision_upper": _ratio(len(tp) + unknown, total),
            "known_gold_causes": known, "known_gold_matched": matched,
            "known_gold_misses": known_misses,
            "known_gold_recall": _ratio(matched, known) if not missing_gold else None,
            "missing_gold_trials": missing_gold,
            "causal_position": {"matched": sum(row["causal_true"] for row in rows),
                                "mismatched": sum(row["causal_false"] for row in rows),
                                "unknown": sum(row["causal_unknown"] for row in rows),
                                "rate_among_adjudicated": _ratio(sum(row["causal_true"] for row in rows),
                                    sum(row["causal_true"] + row["causal_false"] for row in rows))},
            "calls": {name: sum(row["calls"][name] for row in rows)
                      for name in (*STATUSES, "missing")},
            "tokens": {name: sum(row["tokens"][name] for row in rows)
                       for name in ("input", "cache_creation", "cache_read", "output")},
            "reported_billed_usd_known_items": sum(row["observed_billed_usd"] for row in rows),
            "unpriced_calls": sum(row["unpriced_calls"] for row in rows),
            "unknown_token_calls": sum(row["unknown_token_calls"] for row in rows),
            "reported_billed_usd": sum(usd) if all(item is not None for item in usd) else None,
            "reported_usd_per_tp": (sum(usd) / len(tp) if len(tp) and all(item is not None for item in usd)
                                    else None),
            "incomplete_trials": sum(row["incomplete"] for row in rows),
            "overbudget_trials": sum(row["overbudget"] for row in rows)}


def _validated_plan(plan):
    plan = _fields(plan, ("version", "experiment", "arms", "profiles", "seed",
                          "budget", "cases", "order", "static_baseline") if "static_baseline" in plan else
                   ("version", "experiment", "arms", "profiles", "seed",
                    "budget", "cases", "order"), "plan")
    if plan["version"] != "development-comparison-v1":
        raise ValueError("Unsupported development comparison plan")
    experiment = plan["experiment"]
    if experiment == "sixth_role":
        roles = SIXTH_ROLES
    elif experiment == "baseline":
        roles = BASELINE_ROLES
    elif experiment == "stage":
        if not isinstance(plan["arms"], dict) or tuple(plan["arms"]) not in STAGE_PAIRS:
            raise ValueError("Stage arms must be one adjacent preregistered pair")
        roles = {arm: BASE for arm in plan["arms"]}
    else:
        raise ValueError("Unsupported experiment")
    if plan["arms"] != {arm: list(value) for arm, value in roles.items()}:
        raise ValueError("Plan must freeze exact arm roles and call order")
    arms = tuple(roles)
    profiles = _fields(plan["profiles"], arms, "arm profiles")
    expected_modes = ({"B": "five", "B_generic": "generic", "B_assumptions": "boundary"}
                      if experiment == "sixth_role" else
                      {"small_single": "single", "small_five": "five", "strong_single": "single"}
                      if experiment == "baseline" else {arm: "five" for arm in arms})
    expected_policies = {"P0": "git-ast-context-v1", "P1": "git-ast-context-v1",
                         "P2a": "git-ast-outline-v1", "P2b": "git-ast-cards-v1"}
    for arm, profile in profiles.items():
        _fields(profile, ("mode", "model_version", "prompt_sha256", "context_policy"), "arm profile")
        if profile["mode"] != expected_modes[arm]:
            raise ValueError("Arm profile mode differs from frozen role layout")
        _text(profile["model_version"], "model version")
        _sha(profile["prompt_sha256"], "prompt SHA")
        if profile["context_policy"] not in ("git-ast-context-v1", "git-ast-outline-v1",
                                              "git-ast-cards-v1"):
            raise ValueError("Unknown frozen context policy")
        if arm in expected_policies and profile["context_policy"] != expected_policies[arm]:
            raise ValueError("Stage context policy differs from planned treatment")
        if profile["mode"] == "single" and profile["context_policy"] != "git-ast-context-v1":
            raise ValueError("Single baseline must retain raw context")
        if arm != "P0" and profile["prompt_sha256"] != prompt_hash(profile["mode"]):
            raise ValueError("Arm prompt differs from current ordered role instructions")
        if experiment == "baseline" and profile["context_policy"] != "git-ast-context-v1":
            raise ValueError("Baseline arms must share the original raw graph context")
    if experiment == "sixth_role" and len({profile["model_version"] for profile in profiles.values()}) != 1:
        raise ValueError("Sixth-role arms must use one frozen model version")
    if experiment == "sixth_role" and len({profile["context_policy"] for profile in profiles.values()}) != 1:
        raise ValueError("Sixth-role arms must use one frozen context policy")
    if experiment == "baseline" and profiles["small_single"]["model_version"] != profiles["small_five"]["model_version"]:
        raise ValueError("Small model baseline arms differ in model version")
    if experiment == "baseline" and profiles["strong_single"]["model_version"] == profiles["small_single"]["model_version"]:
        raise ValueError("Strong and small baselines must have different models")
    _integer(plan["seed"], "order seed")
    budget = _fields(plan["budget"], ("tokens_per_trial", "wall_seconds_per_trial"), "budget")
    _integer(budget["tokens_per_trial"], "token budget", 1)
    _number(budget["wall_seconds_per_trial"], "wall budget")
    if not budget["wall_seconds_per_trial"]:
        raise ValueError("Positive wall budget required")
    if "static_baseline" in plan:
        static = _fields(plan["static_baseline"], ("enabled", "max_probes", "kinds"), "static baseline plan")
        if (type(static["enabled"]) is not bool or static["max_probes"] != 8 or
                type(static["max_probes"]) is not int or
                static["kinds"] != ["zero_denominator", "empty_index"]):
            raise ValueError("N_static is limited to eight probes in the two supported kinds")
    cases = {}
    gold = {}
    keys = []
    contexts_by_case = {}
    for case in _list(plan["cases"], "cases"):
        _fields(case, ("id", "snapshot_sha", "source_bundle", "scope", "trials", "gold", "strong_candidate_causes"), "case")
        cid = _text(case["id"], "case ID")
        if cid in cases:
            raise ValueError("Duplicate case")
        cases[cid] = case
        _text(case["source_bundle"], "source bundle")
        _text(case["snapshot_sha"], "snapshot OID")
        scope = _fields(case["scope"], ("path", "symbol"), "scope")
        _text(scope["path"], "scope path")
        if scope["symbol"] is None:
            raise ValueError("Development-comparison-v1 requires an exact selected symbol")
        _text(scope["symbol"], "scope symbol")
        source = verify_git_source(Path(case["source_bundle"]))
        if source["run"]["commit"] != case["snapshot_sha"] or scope["path"] not in {item["path"] for item in source["evidence"]}:
            raise ValueError("Scope or snapshot differs from authenticated Git source")
        _, contexts, _ = prepare_analysis(source, mode="five", symbol=scope["symbol"])
        context = contexts.get("symbol:" + scope["symbol"])
        if (context is None or
                not any(node["path"] == scope["path"] and node["distance"] == 0
                        for node in context["nodes"])):
            raise ValueError("Selected symbol/path differs from verified Git graph")
        contexts_by_case[cid] = context
        trials = _list(case["trials"], "trials")
        if len(trials) != 3:
            raise ValueError("Exactly three distinct planned trials per arm required")
        for trial in trials:
            _text(trial, "trial ID")
        _distinct(trials, "trials")
        for trial in trials:
            for arm in arms:
                keys.append((cid, trial, arm))
        if case["gold"] is None:
            gold[cid] = None
        else:
            known = {}
            for item in _list(case["gold"], "gold"):
                _fields(item, ("cause_id", "independent_ref"), "gold cause")
                cause = _text(item["cause_id"], "gold cause ID")
                _text(item["independent_ref"], "gold external evidence reference")
                if cause in known:
                    raise ValueError("Duplicate gold cause")
                known[cause] = item
            gold[cid] = known
        if case["strong_candidate_causes"] is not None:
            raise ValueError("Strong candidate causes are observed after baseline runs, not preregistered")
    if not cases:
        raise ValueError("At least one frozen case required")
    shuffled = list(keys)
    random.Random(plan["seed"]).shuffle(shuffled)
    order = _list(plan["order"], "order")
    if order != [list(key) for key in shuffled]:
        raise ValueError("Order differs from frozen seed shuffle")
    return cases, gold, keys, roles, experiment, arms, budget, contexts_by_case


def validate_plan(plan: dict) -> dict:
    """Check source and frozen design without observations or external claims."""
    cases, _, keys, roles, experiment, arms, _, _ = _validated_plan(plan)
    digest = hashlib.sha256(json.dumps(plan, sort_keys=True, ensure_ascii=False,
                                       separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    return {"plan_sha256": digest, "experiment": experiment, "case_count": len(cases),
            "planned_case_trials": len(keys) // len(arms),
            "planned_actual_calls": 3 * len(cases) * sum(map(len, roles.values())),
            "provenance": "local_source_verified; preregistration_time_and_approval_not_authenticated"}


def evaluate(document: dict) -> dict:
    """Compare frozen trial evidence; reject inconsistent records.

    No target imports, model calls, oracle execution, generated truth, or cost estimates.
    USD is a *reported* value only, even when a local receipt digest is supplied.
    """
    _fields(document, ("plan", "executions", "judgments", "static_baseline")
            if "static_baseline" in document else ("plan", "executions", "judgments"), "document")
    plan = document["plan"]
    cases, gold, keys, roles, experiment, arms, budget, contexts_by_case = _validated_plan(plan)
    static_config = plan.get("static_baseline")
    if "static_baseline" in document and not (static_config and static_config["enabled"]):
        raise ValueError("N_static observations require a predeclared enabled static baseline")
    if static_config and static_config["enabled"]:
        baseline = {}
        for item in _list(document.get("static_baseline", []), "N_static"):
            _fields(item, ("case_id", "snapshot_sha", "sha256", "rows"), "static artifact")
            cid = item["case_id"]
            if cid not in cases or cid in baseline or item["snapshot_sha"] != cases[cid]["snapshot_sha"]:
                raise ValueError("N_static references an unknown, repeated or changed case snapshot")
            observed = _list(item["rows"], "static hypotheses")
            if len(observed) > static_config["max_probes"]:
                raise ValueError("N_static exceeds frozen probe limit")
            for probe in observed:
                _fields(probe, ("kind", "status", "path", "entry_symbol", "entry_line",
                                "parameter", "input_value", "call_line", "sink_symbol",
                                "sink_line"), "static hypothesis")
                if (probe["kind"] not in static_config["kinds"] or
                        probe["status"] != "static_hypothesis" or
                        probe["path"] != cases[cid]["scope"]["path"]):
                    raise ValueError("Static hypothesis differs from selected source or narrow producer contract")
                for field in ("entry_symbol", "parameter", "sink_symbol"):
                    _text(probe[field], "static " + field)
                for field in ("entry_line", "sink_line"):
                    _integer(probe[field], "static " + field, 1)
                if probe["call_line"] is not None:
                    _integer(probe["call_line"], "static call line", 1)
                if (probe["kind"] == "zero_denominator" and probe["input_value"] != 0 or
                        probe["kind"] == "empty_index" and probe["input_value"] != []):
                    raise ValueError("Unsupported static probe input")
            raw = json.dumps({"case_id": cid, "snapshot_sha": item["snapshot_sha"],
                              "rows": observed}, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
            if hashlib.sha256(raw).hexdigest() != item["sha256"]:
                raise ValueError("Static artifact content digest differs from source-linked rows")
            context = contexts_by_case[cid]
            expected = [probe for probe in context["static_counterexamples"]
                        if probe["path"] == cases[cid]["scope"]["path"]]
            if observed != expected:
                raise ValueError("N_static differs from deterministic counterexamples on authenticated Git")
            baseline[cid] = item
        static_report = {"status": "git_static_replay_verified" if len(baseline) == len(cases) else "incomplete",
                         "scope": "two_kinds_zero_denominator_empty_index_max_eight_per_case",
                         "cases": {cid: ({"sha256": baseline[cid]["sha256"], "rows": baseline[cid]["rows"],
                                           "hypotheses": len(baseline[cid]["rows"])}
                                          if cid in baseline else None) for cid in cases},
                         "not_gold_or_confirmed_findings": True}
    else:
        static_report = None
    recorded = {}
    observed_order = []
    final_run_ids = set()
    claims = {}
    usage_by_call = {}
    for record in _list(document["executions"], "executions"):
        _fields(record, ("case_id", "trial_id", "arm", "final_bundle", "wall_seconds", "calls"), "execution")
        key = (record["case_id"], record["trial_id"], record["arm"])
        if key not in keys or key in recorded:
            raise ValueError("Unplanned or duplicate execution")
        recorded[key] = record
        observed_order.append(key)
        cid, trial, arm = key
        _number(record["wall_seconds"], "reported trial wall seconds")
        if arm == "P0":
            raise ValueError("Historical P0 requires an archived offline verifier; live v3 cannot replay it")
        if record["final_bundle"] is None and arm not in ("small_single", "strong_single"):
            raise ValueError("Planned multi-call run requires its verified final bundle")
        if record["final_bundle"] is not None:
            _text(record["final_bundle"], "final bundle")
            final = verify_final_bundle(Path(record["final_bundle"]), Path(cases[cid]["source_bundle"]))
            final_id = final["run"]["id"]
            if final_id in final_run_ids:
                raise ValueError("One final bundle cannot stand for two independent trial records")
            final_run_ids.add(final_id)
            manifest = final["run"].get("manifest")
            analysis = manifest.get("analysis") if isinstance(manifest, dict) else None
            scope = cases[cid]["scope"]
            if (final["run"]["target_sha"] != cases[cid]["snapshot_sha"] or
                    not isinstance(analysis, dict) or analysis.get("symbol") != scope["symbol"] or
                    analysis.get("mode") != plan["profiles"][arm]["mode"] or
                    analysis.get("context_policy") != plan["profiles"][arm]["context_policy"] or
                    manifest["model"]["name_version"] != plan["profiles"][arm]["model_version"] or
                    manifest["model"]["prompt_sha256"] != plan["profiles"][arm]["prompt_sha256"] or
                    manifest["limits"]["tokens"] != budget["tokens_per_trial"] or
                    manifest["limits"]["wall_seconds"] != budget["wall_seconds_per_trial"] or
                    len(final["run"].get("model_audit") or []) != len(roles[arm])):
                raise ValueError("Final bundle differs from planned scope, mode, or calls")
        calls = _list(record["calls"], "calls")
        if len(calls) != len(roles[arm]):
            raise ValueError("All planned calls, including failures/deferred, are required")
        for position, call in enumerate(calls):
            _fields(call, ("audit", "response", "billed_usd", "receipt_sha256"), "call")
            audit = call["audit"]
            if not isinstance(audit, dict) or audit.get("perspective") != roles[arm][position] or audit.get("status") not in STATUSES:
                raise ValueError("Call role/order/status differs from plan")
            if record["final_bundle"] is not None and audit != final["run"]["model_audit"][position]:
                raise ValueError("Call differs from verified final bundle audit")
            if audit["status"] == "deferred":
                if (call["response"] is not None or audit.get("tokens") != 0 or
                        audit.get("candidates") != [] or audit.get("reason") is None):
                    raise ValueError("Deferred call cannot contain responses or claims")
            elif audit["status"] == "failed":
                if audit.get("candidates") != [] or not audit.get("reason"):
                    raise ValueError("Failed call cannot contain scored claims")
            elif audit.get("reason") is not None:
                raise ValueError("Completed call must not have a failure reason")
            if audit["status"] != "deferred":
                _sha(audit.get("request_sha256"), "request digest")
            if audit.get("response_sha256") is None:
                if call["response"] is not None or audit["status"] == "completed":
                    raise ValueError("Completed or referenced call lacks response digest")
                usage = None
            else:
                _sha(audit["response_sha256"], "response digest")
                if call["response"] is None:
                    raise ValueError("Response bytes required for response-bearing call")
                verify_responses([call["response"]], [audit])
                response = _read_response(call["response"])
                usage = response.get("usage") if isinstance(response, dict) else None
                if audit["status"] == "completed" and not isinstance(audit.get("candidates"), list):
                    raise ValueError("Completed call lacks candidate audit")
            if call["billed_usd"] is not None:
                _number(call["billed_usd"], "reported billed USD")
                if audit["status"] == "deferred" and call["billed_usd"] != 0:
                    raise ValueError("Deferred call cannot have billed USD")
                if audit["status"] != "deferred" and call["receipt_sha256"] is None:
                    raise ValueError("Reported USD requires a stored invoice receipt digest")
            if call["receipt_sha256"] is not None:
                _sha(call["receipt_sha256"], "receipt digest")
            if audit["status"] == "completed":
                for entry in audit["candidates"]:
                    if (not isinstance(entry, dict) or entry.get("status") not in ("accepted", "unverified") or
                            entry.get("reason") is None and entry["status"] != "accepted" or
                            entry.get("reason") is not None and entry["status"] == "accepted" or
                            type(entry.get("index")) is not int or
                            entry["index"] < 0 or entry["index"] >= len(audit["candidates"])):
                        raise ValueError("Candidate lacks final admission status")
                    claim_key = (*key, position, entry["index"])
                    if claim_key in claims:
                        raise ValueError("Duplicate raw candidate index")
                    claims[claim_key] = entry
            usage_by_call[(*key, position)] = usage
    if observed_order != [tuple(triple) for triple in plan["order"]
                          if tuple(triple) in recorded]:
        raise ValueError("Reported execution order differs from frozen run order")
    judgments = {}
    cause_verdicts = {}
    for item in _list(document["judgments"], "judgments"):
        _fields(item, ("case_id", "trial_id", "arm", "call_index", "candidate_index", "candidate_sha256", "verdict", "cause_id", "independent_ref", "causal_position"), "judgment")
        key = (item["case_id"], item["trial_id"], item["arm"], item["call_index"], item["candidate_index"])
        if key not in claims or key in judgments or claims[key]["candidate_sha256"] != item["candidate_sha256"]:
            raise ValueError("Judgment lacks exact original response candidate")
        if claims[key]["status"] != "accepted":
            raise ValueError("Unverified raw candidate cannot be scored")
        if item["verdict"] not in ("TP", "FP", "U"):
            raise ValueError("Unknown verdict")
        if item["verdict"] == "U":
            if item["cause_id"] is not None or item["independent_ref"] is not None or item["causal_position"] is not None:
                raise ValueError("Unknown judgment cannot assert cause or location")
        else:
            _text(item["cause_id"], "independently adjudicated cause ID")
            _text(item["independent_ref"], "external judgment evidence reference")
            if item["causal_position"] is not None and type(item["causal_position"]) is not bool:
                raise ValueError("Causal location judgment must be boolean or unknown")
            if item["verdict"] == "TP" and gold[item["case_id"]] is not None and item["cause_id"] not in gold[item["case_id"]]:
                raise ValueError("TP cause not in preregistered known gold")
            if item["verdict"] == "FP" and gold[item["case_id"]] is not None and item["cause_id"] in gold[item["case_id"]]:
                raise ValueError("Known gold cause cannot be scored false positive")
            cause_key = (item["case_id"], item["trial_id"], item["cause_id"])
            previous = cause_verdicts.setdefault(cause_key, item["verdict"])
            if previous != item["verdict"]:
                raise ValueError("Conflicting independent verdicts for one cause")
        judgments[key] = item
    rows = []
    for key in keys:
        cid, trial, arm = key
        record = recorded.get(key)
        role_count = len(roles[arm])
        row = {"case_id": cid, "trial_id": trial, "arm": arm, "raw": 0, "accepted": 0,
               "unknown": 0, "tp": set(), "fp": set(), "causal_true": 0,
               "causal_false": 0, "causal_unknown": 0,
               "calls": dict.fromkeys((*STATUSES, "missing"), 0),
               "tokens": dict.fromkeys(("input", "cache_creation", "cache_read", "output"), 0),
               "billed_usd": 0.0, "observed_billed_usd": 0.0, "unpriced_calls": 0,
               "unknown_token_calls": 0, "incomplete": record is None, "overbudget": False}
        if record is None:
            row["calls"]["missing"] = role_count
            row["billed_usd"] = None
        else:
            row["overbudget"] = record["wall_seconds"] > budget["wall_seconds_per_trial"]
            for position, call in enumerate(record["calls"]):
                audit = call["audit"]
                row["calls"][audit["status"]] += 1
                if audit["status"] != "completed":
                    row["incomplete"] = True
                usage = usage_by_call[(*key, position)]
                if not isinstance(usage, dict) or any(
                        type(usage.get(name, 0)) is not int or usage.get(name, 0) < 0
                        for name in ("input_tokens", "cache_creation_input_tokens",
                                     "cache_read_input_tokens", "output_tokens")):
                    if audit["status"] == "completed":
                        raise ValueError("Completed response has invalid usage")
                    row["unknown_token_calls"] += audit["status"] == "failed"
                    usage = None
                if usage is not None:
                    for field, source in (("input", "input_tokens"), ("cache_creation", "cache_creation_input_tokens"),
                                          ("cache_read", "cache_read_input_tokens"), ("output", "output_tokens")):
                        row["tokens"][field] += usage.get(source, 0)
                if call["billed_usd"] is None:
                    if audit["status"] != "deferred":
                        row["unpriced_calls"] += 1
                        row["billed_usd"] = None
                else:
                    row["observed_billed_usd"] += call["billed_usd"]
                    if row["billed_usd"] is not None:
                        row["billed_usd"] += call["billed_usd"]
                for entry in audit["candidates"]:
                    row["raw"] += 1
                    if entry["status"] != "accepted":
                        row["incomplete"] = True
                        continue
                    row["accepted"] += 1
                    judgment = judgments.get((*key, position, entry["index"]))
                    if judgment is None or judgment["verdict"] == "U" or judgment["verdict"] == "TP" and gold[cid] is None:
                        row["unknown"] += 1
                        row["causal_unknown"] += 1
                        continue
                    cause = (cid, trial, judgment["cause_id"])
                    target = row["tp"] if judgment["verdict"] == "TP" else row["fp"]
                    other = row["fp"] if judgment["verdict"] == "TP" else row["tp"]
                    if cause in other:
                        raise ValueError("Conflicting independent cause verdicts")
                    target.add(cause)
                    location = judgment["causal_position"]
                    row["causal_true" if location is True else "causal_false" if location is False else "causal_unknown"] += 1
            row["overbudget"] |= sum(row["tokens"].values()) > budget["tokens_per_trial"]
        rows.append(row)
    # Provider usage can change a later output cap even when instructions and source match.
    # Keep every run and cost; report payload drift instead of dropping a paired result.
    first_five_payload_drift = []
    if experiment == "sixth_role":
        for cid, case in cases.items():
            for trial in case["trials"]:
                arm_runs = [recorded.get((cid, trial, arm)) for arm in arms]
                if all(arm_runs):
                    for index in range(5):
                        hashes = {item["calls"][index]["audit"].get("request_sha256") for item in arm_runs}
                        if len(hashes) != 1:
                            first_five_payload_drift.append(
                                {"case_id": cid, "trial_id": trial, "call_index": index})
    actual = {arm: _summary([row for row in rows if row["arm"] == arm], gold) for arm in arms}
    by_key = {(row["case_id"], row["trial_id"], row["arm"]): row for row in rows}
    derived = {}
    for name, extra in ((("B", None), ("B_plus_generic", "B_generic"),
                         ("B_plus_assumptions", "B_assumptions")) if experiment == "sixth_role" else ()):
        recombined = []
        for cid, case in cases.items():
            for trial in case["trials"]:
                base = by_key[cid, trial, "B"]
                add = by_key[cid, trial, extra] if extra else None
                row = {**base, "tp": set(base["tp"]), "fp": set(base["fp"]),
                       "tokens": dict.fromkeys(base["tokens"], 0),
                       "calls": dict.fromkeys(base["calls"], 0), "billed_usd": None,
                       "observed_billed_usd": 0.0, "unpriced_calls": 0}
                if add is not None:
                    # Only the actual extra call is borrowed, never its changing first five.
                    full = recorded.get((cid, trial, extra))
                    if full is None:
                        row["incomplete"] = True
                        row["calls"]["missing"] = 1
                    else:
                        role = len(roles[extra]) - 1
                        call = full["calls"][role]
                        row["calls"][call["audit"]["status"]] = 1
                        row["incomplete"] |= call["audit"]["status"] != "completed"
                        usage = usage_by_call[(cid, trial, extra, role)]
                        if usage is None and call["audit"]["status"] == "failed":
                            row["unknown_token_calls"] += 1
                        if call["billed_usd"] is None and call["audit"]["status"] != "deferred":
                            row["unpriced_calls"] += 1
                        if usage is not None:
                            for field, source in (("input", "input_tokens"), ("cache_creation", "cache_creation_input_tokens"),
                                                  ("cache_read", "cache_read_input_tokens"), ("output", "output_tokens")):
                                row["tokens"][field] += usage.get(source, 0)
                        row["overbudget"] |= add["overbudget"]
                        for entry in call["audit"]["candidates"]:
                            row["raw"] += 1
                            if entry["status"] != "accepted":
                                row["incomplete"] = True
                                continue
                            row["accepted"] += 1
                            judgment = judgments.get((cid, trial, extra, role, entry["index"]))
                            if judgment is None or judgment["verdict"] == "U" or judgment["verdict"] == "TP" and gold[cid] is None:
                                row["unknown"] += 1
                                row["causal_unknown"] += 1
                                continue
                            cause = (cid, trial, judgment["cause_id"])
                            target = row["tp"] if judgment["verdict"] == "TP" else row["fp"]
                            other = row["fp"] if judgment["verdict"] == "TP" else row["tp"]
                            if cause in other:
                                raise ValueError("Contradictory derived same-cause judgments")
                            target.add(cause)
                            location = judgment["causal_position"]
                            row["causal_true" if location is True else "causal_false" if location is False else "causal_unknown"] += 1
                recombined.append(row)
        derived[name] = _summary(recombined, gold)
        derived[name]["offline_only_no_additional_calls_or_billing"] = True
    paired = []
    for cid, case in cases.items():
        for trial in case["trials"]:
            grouped = {arm: by_key[cid, trial, arm] for arm in arms}
            strong = ({cause for _, _, cause in grouped["strong_single"]["tp"] | grouped["strong_single"]["fp"]}
                      if experiment == "baseline" else None)
            gold_outcomes = ({cause: {arm: (cid, trial, cause) in row["tp"]
                                      for arm, row in grouped.items()}
                             for cause in sorted(gold[cid])} if gold[cid] is not None else None)
            paired.append({"case_id": cid, "trial_id": trial,
                           "paired_known_gold_causes": gold_outcomes,
                           "actual_trials": {arm: _summary([row], gold) for arm, row in grouped.items()},
                           "reported_wall_seconds": {
                               arm: (recorded[cid, trial, arm]["wall_seconds"] if (cid, trial, arm) in recorded else None)
                               for arm in arms},
                           "known_gold_misses": {arm: (sorted(set(gold[cid]) - {cause for _, _, cause in row["tp"]})
                                                       if gold[cid] is not None else None)
                                                 for arm, row in grouped.items()},
                           "strong_candidate_overlap_not_recall": {
                               arm: ({"shared": len({cause for _, _, cause in row["tp"] | row["fp"]} & strong),
                                      "strong_candidates": len(strong),
                                      "strong_unknown_claims": grouped["strong_single"]["unknown"],
                                      "scope": "adjudicated_cause_ids_only",
                                      "ratio": _ratio(len({cause for _, _, cause in row["tp"] | row["fp"]} & strong), len(strong))}
                                     if strong is not None else None)
                               for arm, row in grouped.items()}})
    case_repeats = {}
    for cid, case in cases.items():
        case_repeats[cid] = {}
        for arm in arms:
            arm_rows = [by_key[cid, trial, arm] for trial in case["trials"]]
            cause_sets = [{cause for _, _, cause in row["tp"]} for row in arm_rows]
            case_repeats[cid][arm] = {
                "planned_repeats": 3,
                "unique_tp_per_trial": [len(items) for items in cause_sets],
                "mean_unique_tp_per_trial": sum(map(len, cause_sets)) / 3,
                "consistent_tp_cause_set": (None if any(row["incomplete"] for row in arm_rows)
                                             else all(items == cause_sets[0] for items in cause_sets)),
                "all_trials_complete": not any(row["incomplete"] for row in arm_rows)}
    incomplete = any(row["incomplete"] for row in rows)
    overbudget = any(row["overbudget"] for row in rows)
    return {"version": "development-comparison-report-v1", "experiment": experiment,
            "plan_sha256": hashlib.sha256(json.dumps(
                plan, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                allow_nan=False).encode("utf-8")).hexdigest(),
            "plan_seed": plan["seed"], "planned_case_trials": len(keys) // len(arms),
            "planned_actual_calls": len(plan["cases"]) * 3 * sum(map(len, roles.values())),
            "actual": actual, "derived_fixed_B": derived, "N_static": static_report,
            "paired": paired, "case_repeats": case_repeats,
            "promotion_blocked": True,
            "blocking_reasons": (["historical_P0_archive_not_integrated"] if "P0" in arms else []) +
                                (["missing_or_failed_trial"] if incomplete else []) +
                                (["static_baseline_incomplete"] if static_report is not None and
                                  static_report["status"] == "incomplete" else []) +
                                (["overbudget_comparison_bundle"] if overbudget else []) +
                                (["first_five_payload_drift"] if first_five_payload_drift else []) +
                                ["development_only_no_independent_promotion_evidence"],
            "first_five_payload_drift": first_five_payload_drift,
            "provenance": {"git_source": "local_immutable_commit_verified",
                           "final_bundle": "verified_for_present_multi_call_runs; baseline_single_unsealed",
                           "response": "local_normalized_bytes_verified_when_present",
                           "external_judgments": "caller_declared_not_authenticated",
                           "provider_invoice_and_execution": "not_authenticated",
                           "pre_registration_and_approval_time": "not_authenticated",
                           "extra_role_candidate_hints": "not_verifiable_from_request_digest_only"}}
