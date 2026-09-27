"""Seal and re-verify a complete, source-only five-record-type scan bundle.

A Git blob inventory establishes source identity, never defect truth. No caller
supplied runtime record, profile summary, or model output can confirm a finding.
"""

import hashlib
import io
import json
import math
import re
from pathlib import Path

from modules.diagnosis.model import (BOUNDARY_PERSPECTIVES, GENERIC_PERSPECTIVES,
                                     PERSPECTIVES, prompt_hash, review_audit)
from modules.diagnosis.plan import prepare_analysis
from modules.diagnosis.screening import screen_candidates
from modules.evidence.authenticity import verify_git_source
from modules.findings.actions import _read as validate_owner_log, read_action_history
from modules.findings.admission import (_id, _identity, _validate_candidate, admit,
                                        priority_rows)
from modules.findings.locations import validate_locations
from modules.git_modes import plan_candidate
from modules.run_policy import manifest_hash
from modules.runtime_exec.docker import verify_execution


SCHEMA_VERSION = "evidence-contract-v2"
_FILES = frozenset({"run.json", "evidence.jsonl", "findings.jsonl", "report.json", "actions.jsonl"})
_CANDIDATE_KEYS = frozenset({"root_symbol", "mechanism", "condition", "impact", "trigger",
                             "taxonomy", "severity", "location", "evidence_ids", "next_action"})
_SCOPE = "full_tracked_python_git_commit"
_STATUS = "source_only_deferred"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_REASON = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,79}\Z")


def _audit(rows, manifest, admitted, source_bundle, verified, context=None, *,
           path=None, deferred_reasons=frozenset({"budget_exhausted"})):
    if rows is None:
        if manifest is not None and manifest["model"]["endpoint"] is not None:
            raise ValueError("Model review requires its candidate audit")
        return None, None
    if (manifest is None or manifest["model"]["endpoint"] is None or
            manifest["analysis"]["mode"] not in ("five", "boundary", "generic") or
            not manifest["network"]["model"]):
        raise ValueError("Model audit requires the pinned approved-analysis manifest")
    mode = manifest["analysis"]["mode"]
    expected = (BOUNDARY_PERSPECTIVES if mode == "boundary" else
                GENERIC_PERSPECTIVES if mode == "generic" else PERSPECTIVES)
    if manifest["model"]["prompt_sha256"] != prompt_hash(mode):
        raise ValueError("Model prompt differs from approved reviewer mode")
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError(f"Model audit requires exactly {len(expected)} approved perspective rows")
    by_perspective = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid model audit row")
        perspective = row.get("perspective")
        status = row.get("status")
        if (not isinstance(perspective, str) or perspective not in expected or
                perspective in by_perspective or status not in ("completed", "failed", "deferred")):
            raise ValueError("Invalid model perspective or status")
        fields = {"perspective", "status", "reason", "tokens", "candidates"}
        if status != "deferred":
            fields |= {"request_sha256", "wall_seconds"}
        if status == "completed" or "response_sha256" in row:
            fields.add("response_sha256")
        if context is not None and "review_units" in context:
            fields.add("review")
            if row.get("review") != review_audit(context, row):
                raise ValueError("Review unit audit differs from approved context or response indices")
        if set(row) != fields or type(row["tokens"]) is not int or row["tokens"] < 0:
            raise ValueError("Invalid model audit fields or token count")
        if (status == "completed" and (row["reason"] is not None or row["tokens"] < 1)
                or status != "completed" and (
                    not isinstance(row["reason"], str) or not _REASON.fullmatch(row["reason"]))):
            raise ValueError("Invalid model audit result")
        if status == "deferred":
            if row["tokens"] != 0 or row["reason"] not in deferred_reasons:
                raise ValueError("Deferred perspective must declare a supported reason")
        else:
            if (not isinstance(row["request_sha256"], str) or
                    not _SHA256.fullmatch(row["request_sha256"]) or
                    type(row["wall_seconds"]) is not float or
                    not math.isfinite(row["wall_seconds"]) or row["wall_seconds"] < 0):
                raise ValueError("Invalid model request hash or elapsed time")
            if "response_sha256" in row and (
                    not isinstance(row["response_sha256"], str) or
                    not _SHA256.fullmatch(row["response_sha256"])):
                raise ValueError("Invalid model response hash")
            if status == "failed" and row["tokens"] and "response_sha256" not in row:
                raise ValueError("Consumed model tokens require a response hash")
        by_perspective[perspective] = row
    if [row["perspective"] for row in rows] != list(expected):
        raise ValueError("Model audit perspectives must retain approved call order")
    if sum(row["tokens"] for row in rows) > manifest["limits"]["tokens"]:
        raise ValueError("Model audit exceeds manifest token budget")
    accepted = []
    for row in rows:
        candidates = row["candidates"]
        if not isinstance(candidates, list) or row["status"] != "completed" and candidates:
            raise ValueError("Only completed calls may contain candidate rows")
        for index, entry in enumerate(candidates):
            if (not isinstance(entry, dict) or set(entry) != {
                    "index", "candidate", "candidate_sha256", "status", "reason", "finding_id"} or
                    type(entry["index"]) is not int or entry["index"] != index or
                    not isinstance(entry["candidate_sha256"], str) or
                    not _SHA256.fullmatch(entry["candidate_sha256"]) or
                    entry["candidate_sha256"] != _digest(entry["candidate"])):
                raise ValueError("Invalid original candidate index, digest, or fields")
            if entry["status"] == "unverified":
                if (not isinstance(entry["reason"], str) or not _REASON.fullmatch(entry["reason"]) or
                        entry["reason"] == "pending_admission" or entry["finding_id"] is not None):
                    raise ValueError("Unverified candidate requires a final reason and no finding")
                continue
            if (entry["status"] != "accepted" or entry["reason"] is not None or
                    not isinstance(entry["candidate"], dict)):
                raise ValueError("Invalid candidate admission status")
            candidate = {**entry["candidate"], "perspective": row["perspective"],
                         "_audit": dict(entry), "_response_sha256": row["response_sha256"]}
            if context is None:
                raise ValueError("Accepted candidate has no approved context")
            accepted.append(candidate)
    screened = screen_candidates(accepted, verified, source_bundle, context, None, path=path)
    if len(screened) != len(accepted):
        raise ValueError("Accepted candidate fails source, context, or location validation")
    for candidate in screened:
        original = by_perspective[candidate["perspective"]]["candidates"][candidate["_audit"]["index"]]
        if candidate["_audit"] != original:
            raise ValueError("Accepted candidate differs from its finding identity")
    reconstructed = admit(source_bundle, screened)
    if reconstructed != admitted:
        raise ValueError("Findings differ from their accepted candidate provenance")
    ordered = [by_perspective[p] for p in expected]
    return ordered, _digest(ordered)


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _seal(record):
    return {**record, "content_hash": _digest(record)}


def _lines(rows):
    return b"".join(_canonical(row) + b"\n" for row in rows)


def _admitted(rows, verified):
    if not isinstance(rows, list):
        raise ValueError("Findings must be a list of admitted source-only records")
    source = verified["run"]
    by_path = {item["path"]: {item["id"]} for item in verified["evidence"]}
    seen = set()
    clean = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != _CANDIDATE_KEYS | {
                "id", "repository", "state", "basis", "perspectives"}:
            raise ValueError("Finding must be an admitted source-only record")
        if row["repository"] != source["repository"] or row["state"] != "deferred" or row["basis"] != "source_only":
            raise ValueError("Only deferred findings from this source are accepted")
        candidate = _validate_candidate({key: row[key] for key in _CANDIDATE_KEYS}, by_path)
        if not isinstance(row["perspectives"], list) or any(
                not isinstance(p, str) or not p.strip() for p in row["perspectives"]):
            raise ValueError("Invalid perspectives")
        perspectives = sorted(set(p.strip() for p in row["perspectives"]))
        identity = _identity(source["repository"], candidate)
        finding_id = _id(identity)
        if row["id"] != finding_id or finding_id in seen:
            raise ValueError("Invalid or duplicate stable finding ID")
        normalized = {"id": finding_id, "repository": source["repository"],
                      "state": "deferred", "basis": "source_only", **candidate,
                      "perspectives": perspectives}
        if row != normalized:
            raise ValueError("Finding differs from admitted source-only record")
        seen.add(finding_id)
        clean.append(normalized)
    clean.sort(key=lambda row: row["id"])
    proofs = validate_locations(verified, clean)
    return clean, {row["id"]: proof for row, proof in zip(clean, proofs)}


def _batch_audit(rows, manifest, admitted, verified, coverage, source_bundle, contexts):
    fields = {"selected_paths", "analyzed_paths", "omitted_unknown_paths",
              "source_bytes", "tokens_used", "diagnostic_completeness",
              "base_sha", "scope"}
    if not isinstance(coverage, dict) or set(coverage) != fields:
        raise ValueError("Batch diagnosis requires exact coverage fields")
    selected = coverage["selected_paths"]
    analyzed = coverage["analyzed_paths"]
    omitted = coverage["omitted_unknown_paths"]
    if any(not isinstance(paths, list) or
           any(not isinstance(path, str) for path in paths) or
           paths != sorted(set(paths))
           for paths in (selected, analyzed, omitted)):
        raise ValueError("Batch paths must be unique and sorted")
    inventory = {row["path"] for row in verified["evidence"]}
    if (set(selected) - inventory or set(analyzed) - set(selected) or
            coverage["diagnostic_completeness"] != "unknown" or
            type(coverage["source_bytes"]) is not int or coverage["source_bytes"] < 0 or
            type(coverage["tokens_used"]) is not int or coverage["tokens_used"] < 0):
        raise ValueError("Batch coverage claims paths or measurements not established")
    base = coverage["base_sha"]
    scope = coverage["scope"]
    if scope == "candidate_impact":
        if not isinstance(base, str):
            raise ValueError("Candidate impact requires frozen base commit")
        plan = plan_candidate(Path(verified["run"]["repository"]), base,
                              verified["run"]["commit"], scope="impact")
        if selected != plan["observed_target_paths"] or plan["base_sha"] != base:
            raise ValueError("Candidate scope differs from Git impact plan")
        planned_omissions = set(plan["omitted_unknown_paths"])
    elif scope == _SCOPE:
        if set(selected) != inventory:
            raise ValueError("Full batch must select every tracked Python source")
        if base is not None:
            plan = plan_candidate(Path(verified["run"]["repository"]), base,
                                  verified["run"]["commit"], scope="full")
            if plan["base_sha"] != base:
                raise ValueError("Candidate full scope differs from Git base")
        planned_omissions = set()
    else:
        raise ValueError("Unsupported batch scope")
    if (manifest is None or manifest["model"]["endpoint"] is None or
            manifest["analysis"]["mode"] not in ("five", "boundary", "generic") or
            manifest["model"]["prompt_sha256"] != prompt_hash(manifest["analysis"]["mode"]) or
            not manifest["network"]["model"] or
            not {"source", "context"} <= set(manifest["model"]["transmitted_data"])):
        raise ValueError("Batch audit requires a pinned declared source/context model")
    if (manifest["analysis"]["scope"] != ("impact" if scope == "candidate_impact" else "full") or
            manifest["analysis"]["base_sha"] != base or
            list(contexts) != [f"module:{path}" for path in selected]):
        raise ValueError("Batch coverage differs from approved analysis")
    if not isinstance(rows, list) or len(rows) != len(selected):
        raise ValueError("Batch must account for every selected module")
    by_path = {row["location"]["path"]: [] for row in admitted}
    for finding in admitted:
        by_path[finding["location"]["path"]].append(finding)
    normalized = []
    complete = []
    token_total = 0
    for path, entry in zip(selected, rows):
        if (not isinstance(entry, dict) or set(entry) != {"scope_id", "perspectives"} or
                entry["scope_id"] != f"module:{path}"):
            raise ValueError("Batch audit scope differs from selected source")
        reviewers, _ = _audit(
            entry["perspectives"], manifest, by_path.get(path, []), source_bundle, verified,
            contexts[entry["scope_id"]], path=path,
            deferred_reasons=frozenset({"budget_exhausted", "source_slice_unavailable"}))
        normalized.append({"scope_id": entry["scope_id"], "perspectives": reviewers})
        token_total += sum(row["tokens"] for row in reviewers)
        if all(row["status"] == "completed" for row in reviewers):
            complete.append(path)
    if (set(by_path) - set(selected) or complete != analyzed or
            set(omitted) != planned_omissions | (set(selected) - set(complete)) or
            token_total != coverage["tokens_used"] or token_total > manifest["limits"]["tokens"]):
        raise ValueError("Batch audit is incomplete or exceeds the approved budget")
    return normalized, _digest(normalized)

def _symbol_audit(rows, manifest, admitted, verified, coverage, source_bundle, contexts):
    fields = {"scope", "symbol", "base_sha", "context_node_ids", "source_bytes",
              "truncated", "diagnostic_completeness"}
    if (not isinstance(coverage, dict) or set(coverage) != fields or
            coverage["scope"] != "selected_symbol_only" or
            not isinstance(coverage["symbol"], str) or not coverage["symbol"] or
            coverage["base_sha"] is not None or
            type(coverage["source_bytes"]) is not int or coverage["source_bytes"] < 0 or
            type(coverage["truncated"]) is not bool or
            coverage["diagnostic_completeness"] != "unknown"):
        raise ValueError("Selected symbol coverage is invalid")
    context = contexts.get("symbol:" + coverage["symbol"])
    if context is None:
        raise ValueError("Selected symbol differs from approved analysis")
    if (not any(node["distance"] == 0 for node in context["nodes"]) or
            coverage["context_node_ids"] != [node["id"] for node in context["nodes"]] or
            coverage["source_bytes"] != context["source_bytes"] or
            coverage["truncated"] != context["truncated"] or
            any(not any(node["path"] == finding["location"]["path"] and
                        node["line"] <= finding["location"]["line"] and
                        finding["location"].get("end_line", finding["location"]["line"]) <= node["end_line"]
                        for node in context["nodes"])
                for finding in admitted)):
        raise ValueError("Selected symbol differs from frozen Git context")
    return _audit(rows, manifest, admitted, source_bundle, verified, context)



def _build(source_bundle, verified, findings, manifest, model_audit, source_actions=None,
           diagnosis_coverage=None, runtime_trace=None):
    source = verified["run"]
    if manifest is not None:
        if not isinstance(manifest, dict):
            raise ValueError("Manifest must be a RunManifest object")
        config_hash = manifest_hash(manifest)
        if manifest["snapshot_sha"] != source["commit"]:
            raise ValueError("Manifest snapshot differs from authenticated Git commit")
    else:
        config_hash = None
    admitted, proofs = _admitted(findings, verified)
    contexts = {}
    if manifest is not None and manifest["model"]["endpoint"] is not None:
        analysis = manifest["analysis"]
        if analysis["mode"] not in ("five", "boundary", "generic"):
            raise ValueError("Single baselines cannot produce a final bundle")
        if manifest["model"]["prompt_sha256"] != prompt_hash(analysis["mode"]):
            raise ValueError("Model prompt differs from approved reviewer mode")
        actual, contexts, _ = prepare_analysis(
            verified, mode=analysis["mode"], symbol=analysis["symbol"],
            scope=analysis["scope"] if analysis["symbol"] is None else None,
            main_ref=analysis["base_sha"],
            candidate_ref=source["commit"] if analysis["base_sha"] is not None else None,
            review={"git-ast-context-v1": "raw", "git-ast-outline-v1": "outline",
                    "git-ast-cards-v1": "cards"}[analysis["context_policy"]])
        if actual != analysis:
            raise ValueError("Model analysis differs from approved Git context")
    if diagnosis_coverage is None:
        if model_audit is not None and len(contexts) != 1:
            raise ValueError("Multiple model contexts require batch coverage")
        context = next(iter(contexts.values()), None)
        audit, model_io_hash = _audit(model_audit, manifest, admitted,
                                      source_bundle, verified, context)
    elif isinstance(diagnosis_coverage, dict) and diagnosis_coverage.get("scope") == "selected_symbol_only":
        audit, model_io_hash = _symbol_audit(model_audit, manifest, admitted,
                                              verified, diagnosis_coverage, source_bundle, contexts)
    else:
        audit, model_io_hash = _batch_audit(model_audit, manifest, admitted,
                                            verified, diagnosis_coverage, source_bundle, contexts)
    source_actions = [] if source_actions is None else source_actions
    if not isinstance(source_actions, list):
        raise ValueError("Owner actions must be a validated history list")
    _, history = validate_owner_log(io.BytesIO(_lines(source_actions)), source["id"],
                                    {row["id"]: row for row in admitted})
    if history != source_actions or any(row["finding_id"] not in {item["id"] for item in admitted}
                                        for row in history):
        raise ValueError("Owner action belongs to a different final finding set")
    action_hash = _digest(history) if history else None
    if runtime_trace is not None and (
            not isinstance(runtime_trace, dict) or manifest is None or
            runtime_trace.get("runtime_attested") is not False or
            runtime_trace.get("runtime_provenance") != "caller_declared_unattested" or
            runtime_trace.get("snapshot_sha") != source["commit"] or
            runtime_trace.get("source_run_id") != source["id"] or
            runtime_trace.get("manifest_sha256") != config_hash):
        raise ValueError("Runtime trace cannot establish independent execution provenance")
    audit_rows = [row for entry in audit or [] for row in
                  (entry["perspectives"] if "perspectives" in entry else [entry])]
    sources = {item["path"]: {item["id"]} for item in verified["evidence"]}
    admitted_ids = {row["id"] for row in admitted}
    for row in audit_rows:
        for candidate in row["candidates"]:
            if candidate["reason"] == "candidate_identity_conflict":
                value = _validate_candidate(
                    {**candidate["candidate"], "perspective": row["perspective"]}, sources)
                if _id(_identity(source["repository"], value)) in admitted_ids:
                    raise ValueError("Conflicting identity group cannot retain accepted findings")
    candidate_counts = {
        status: sum(candidate["status"] == status for row in audit_rows
                    for candidate in row["candidates"])
        for status in ("accepted", "unverified")}
    incomplete = (candidate_counts["unverified"] > 0 or
                  any(row["status"] != "completed" for row in audit_rows) or
                  runtime_trace is not None and any(
                      row["status"] in ("failed", "deferred") for row in runtime_trace["nodes"]))
    analysis_status = "incomplete" if incomplete else "completed" if audit is not None else "not_observed"
    trace_hash = _digest(runtime_trace) if runtime_trace is not None else None
    findings_hash = _digest(admitted)
    if diagnosis_coverage is not None:
        scope, base_sha = diagnosis_coverage["scope"], diagnosis_coverage["base_sha"]
    elif manifest is not None and manifest["analysis"] is not None:
        scope = {"symbol": "selected_symbol_only", "impact": "candidate_impact",
                 "full": _SCOPE}[manifest["analysis"]["scope"]]
        base_sha = manifest["analysis"]["base_sha"]
    else:
        scope, base_sha = _SCOPE, None
    mode = "full"
    if diagnosis_coverage is not None:
        mode = "pull_request_or_candidate_commit" if base_sha else "scheduled_main_branch"
    run_id = _digest({"schema_version": SCHEMA_VERSION,
                      "source_run_id": source["id"], "manifest_hash": config_hash,
                      "mode": mode, "scope": scope, "findings_hash": findings_hash,
                      "model_io_hash": model_io_hash, "action_hash": action_hash,
                      "diagnosis_coverage": diagnosis_coverage, "runtime_trace_hash": trace_hash})
    run = _seal({"id": run_id, "schema_version": SCHEMA_VERSION, "repository": source["repository"],
                 "base_sha": base_sha, "target_sha": source["commit"], "source_run_id": source["id"],
                 "source_run_hash": source["content_hash"], "mode": mode, "scope": scope,
                 "manifest": manifest, "manifest_hash": config_hash,
                 "findings_hash": findings_hash, "model_io_hash": model_io_hash,
                 "action_hash": action_hash,
                 "model_audit": audit, "diagnosis_coverage": diagnosis_coverage,
                 "runtime_trace": runtime_trace, "runtime_trace_hash": trace_hash,
                 "model_provenance": "caller_declared_unattested" if audit is not None else "not_observed",
                 "cache": [], "clean_replay_run_id": None,
                 "source_count": len(verified["evidence"]), "run_status": _STATUS})
    evidence = []
    evidence_ids = {}
    for original in verified["evidence"]:
        identifier = _digest({"run_id": run_id, "source_evidence_id": original["id"]})
        evidence_ids[original["id"]] = identifier
        evidence.append(_seal({"id": identifier, "schema_version": SCHEMA_VERSION,
                               "kind": "source", "producer": "authenticated_git_source",
                               "run_id": run_id, "source_run_id": source["id"],
                               "source_evidence_id": original["id"],
                               "source_record_hash": original["content_hash"],
                               "path": original["path"], "commit": source["commit"],
                               "blob_oid": original["blob_oid"],
                               "source_sha256": original["source_sha256"],
                               "payload_sha256": original["source_sha256"],
                               "observed_value": "git_blob_bytes_authenticated"}))
    output_findings = []
    for finding in admitted:
        path = finding["location"]["path"]
        origin = next(item for item in verified["evidence"] if item["path"] == path)
        output_findings.append(_seal({**finding, "schema_version": SCHEMA_VERSION,
                                      "run_id": run_id, "evidence_ids": [
                                          evidence_ids[item] for item in finding["evidence_ids"]],
                                      "source_sha256": origin["source_sha256"],
                                      "source_slice_sha256": proofs[finding["id"]]["source_slice_sha256"],
                                      "change_status": "unknown", "model_io_hash": model_io_hash}))
    latest = {row["finding_id"]: row["action"] for row in history}
    priority = priority_rows(output_findings, actions=latest)
    coverage = {"source_inventory": "complete_tracked_python_git_commit",
                "source_count": len(evidence), "diagnostic_completeness": "unknown",
                "runtime_execution": ("caller_declared_unattested" if runtime_trace is not None
                                      else "not_observed"), "oracle": "not_observed",
                "non_python_and_unresolved_dependencies": "outside_source_inventory"}
    if diagnosis_coverage is not None:
        coverage["diagnosis"] = diagnosis_coverage
    report = _seal({"id": _digest({"run_id": run_id, "kind": "report"}),
                    "schema_version": SCHEMA_VERSION, "run_id": run_id,
                    "ordered_finding_ids": [row["id"] for row in priority],
                    "priority_rows": priority, "coverage": coverage, "scan_status": _STATUS,
                    "analysis_status": analysis_status, "candidate_counts": candidate_counts,
                    "finding_status": "all_deferred_source_only",
                    "deferred_count": len(output_findings), "confirmed_count": 0,
                    "user_actions": "owner_declared_local" if history else "none_recorded"})
    output_actions = [_seal({"id": _digest({"run_id": run_id, "source_action_id": row["id"]}),
                             "schema_version": SCHEMA_VERSION, "run_id": run_id,
                             "source_run_id": source["id"], "source_action": row,
                             "finding_id": row["finding_id"], "action": row["action"],
                             "timestamp": row["timestamp"]}) for row in history]
    return {"run.json": _lines([run]), "evidence.jsonl": _lines(evidence),
            "findings.jsonl": _lines(output_findings), "report.json": _lines([report]),
            "actions.jsonl": _lines(output_actions)}


def write_final_bundle(source_bundle: Path, findings: list[dict], output_root: Path, *,
                       manifest: dict | None = None,
                       runtime_records: list[dict] | None = None,
                       model_audit: list[dict] | None = None,
                       action_directory: Path | None = None,
                       diagnosis_coverage: dict | None = None,
                       runtime_trace_dir: Path | None = None) -> Path:
    """Write five immutable record files; only authenticated source evidence is admissible.

    No runtime attestation/oracle schema exists yet. Even an empty explicit runtime
    submission is rejected rather than being reported as executed.
    """
    if runtime_records is not None:
        raise ValueError("Runtime records have no approved independent attestation and oracle schema")
    source_bundle = Path(source_bundle).resolve(strict=True)
    verified = verify_git_source(source_bundle)
    repository = Path(verified["run"]["repository"]).resolve(strict=True)
    output_root = Path(output_root).resolve()
    if (output_root == source_bundle or output_root.is_relative_to(source_bundle) or
            output_root == repository or output_root.is_relative_to(repository)):
        raise ValueError("Final output must not modify the source bundle or repository")
    actions = (read_action_history(source_bundle, findings, action_directory)
               if action_directory is not None else None)
    trace = (verify_execution(source_bundle, manifest, runtime_trace_dir)
             if runtime_trace_dir is not None else None)
    payloads = _build(source_bundle, verified, findings, manifest, model_audit, actions,
                      diagnosis_coverage, trace)
    run = json.loads(payloads["run.json"])
    runs = output_root / "runs"
    if runs.is_symlink():
        raise ValueError("Runs directory must not be a symlink")
    runs.mkdir(parents=True, exist_ok=True)
    if runs.is_symlink() or not runs.is_dir():
        raise ValueError("Runs directory must be a real directory")
    bundle = runs / run["id"]
    if bundle.exists() or bundle.is_symlink():
        _unchanged(bundle, payloads)
        return bundle
    try:
        bundle.mkdir(mode=0o700)
    except FileExistsError:
        _unchanged(bundle, payloads)
        return bundle
    for name, payload in payloads.items():
        with (bundle / name).open("xb") as stream:
            stream.write(payload)
    return bundle


def _unchanged(bundle, payloads):
    if not bundle.is_dir() or bundle.is_symlink() or {p.name for p in bundle.iterdir()} != _FILES:
        raise FileExistsError(f"Existing final bundle differs: {bundle}")
    for name, payload in payloads.items():
        file = bundle / name
        if file.is_symlink() or not file.is_file() or file.read_bytes() != payload:
            raise FileExistsError(f"Existing final bundle differs: {file}")


def _parse_one(data):
    try:
        record = json.loads(data)
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError("Invalid final record") from error
    if not isinstance(record, dict) or _lines([record]) != data:
        raise ValueError("Noncanonical final record")
    return record


def _parse_many(data):
    try:
        rows = [json.loads(line) for line in data.splitlines(keepends=True)]
        if not all(isinstance(row, dict) for row in rows) or _lines(rows) != data:
            raise ValueError("Noncanonical final records")
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError("Invalid final records") from error
    return rows


def verify_final_bundle(bundle: Path, source_bundle: Path, *,
                        runtime_trace_dir: Path | None = None) -> dict:
    """Authenticate Git bytes and reconstruct all five types and their replay chain."""
    bundle = Path(bundle)
    source_bundle = Path(source_bundle).resolve(strict=True)
    verified = verify_git_source(source_bundle)
    if not bundle.is_dir() or bundle.is_symlink() or {p.name for p in bundle.iterdir()} != _FILES:
        raise ValueError("Incomplete or unexpected final bundle files")
    payloads = {}
    for name in _FILES:
        path = bundle / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("Final record must be a regular file")
        payloads[name] = path.read_bytes()
    run = _parse_one(payloads["run.json"])
    evidence = _parse_many(payloads["evidence.jsonl"])
    findings = _parse_many(payloads["findings.jsonl"])
    report = _parse_one(payloads["report.json"])
    actions = _parse_many(payloads["actions.jsonl"])
    source_actions = []
    for row in actions:
        if not isinstance(row.get("source_action"), dict):
            raise ValueError("Final action lacks its original owner log entry")
        source_actions.append(row["source_action"])
    source_ids = {row["id"]: row for row in verified["evidence"]}
    evidence_to_source = {}
    for row in evidence:
        if not isinstance(row.get("id"), str) or row["id"] in evidence_to_source:
            raise ValueError("Duplicate or invalid evidence ID")
        evidence_to_source[row["id"]] = row.get("source_evidence_id")
    restored = []
    for row in findings:
        if not isinstance(row.get("evidence_ids"), list):
            raise ValueError("Finding has no evidence links")
        try:
            original_ids = [evidence_to_source[item] for item in row["evidence_ids"]]
        except (KeyError, TypeError) as error:
            raise ValueError("Finding cites absent evidence") from error
        if any(item not in source_ids for item in original_ids):
            raise ValueError("Finding cites foreign source evidence")
        restored.append({key: value for key, value in row.items() if key in _CANDIDATE_KEYS | {
            "id", "repository", "state", "basis", "perspectives"}} |
            {"evidence_ids": original_ids})
    try:
        trace = run.get("runtime_trace")
        if (trace is None) != (runtime_trace_dir is None):
            raise ValueError("Runtime artifacts required exactly when run cites a trace")
        if trace is not None and verify_execution(source_bundle, run["manifest"], runtime_trace_dir) != trace:
            raise ValueError("Runtime trace differs from its declared artifact bytes")
        expected = _build(source_bundle, verified, restored, run.get("manifest"), run.get("model_audit"),
                          source_actions, run.get("diagnosis_coverage"), trace)
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise ValueError("Invalid final bundle lineage or finding") from error
    if bundle.name != run.get("id") or payloads != expected:
        raise ValueError("Final bundle differs from authenticated source lineage")
    return {"run": run, "evidence": evidence, "findings": findings,
            "report": report, "actions": actions}
