"""Review a frozen symbol or bounded Python source scope after one manual approval.

Hypotheses remain provisional; no target code is executed or finding confirmed.
"""

import argparse
import os
import json
import subprocess
import time
from pathlib import Path

from modules.diagnosis.model import (AnalysisBudget, BOUNDARY_PERSPECTIVES,
                                     GENERIC_PERSPECTIVES, PERSPECTIVES, ResponseArtifacts,
                                     analyze, prompt_hash, review_audit, validate_model_plan)
from modules.diagnosis.plan import prepare_analysis
from modules.diagnosis.screening import isolate_conflicts, screen_candidates
from modules.evidence.authenticity import verify_git_source
from modules.evidence.final_bundle import verify_final_bundle, write_final_bundle
from modules.findings import admit, priority_rows
from modules.findings.locations import validate_locations
from modules.run_policy import SCHEMA_VERSION, consume_approval, manifest_hash, verify_approval
from modules.runtime_exec.docker import (execute_nodes, summarize_execution, verify_execution,
                                         validate_runtime_host, validate_runtime_plan, validate_source_workloads)


def _deferred(reason, mode="five"):
    return [{"perspective": name, "status": "deferred", "reason": reason, "tokens": 0,
             "candidates": []}
            for name in (BOUNDARY_PERSPECTIVES if mode == "boundary" else
                         GENERIC_PERSPECTIVES if mode == "generic" else PERSPECTIVES)]


def _batch_review(contexts, paths, verified, source_bundle, manifest, plan, deadline,
                  unverified, runtime_context=None, response_artifacts=None, mode="five"):
    budget = AnalysisBudget(manifest, deadline=deadline)
    all_candidates = []
    audit = []
    analyzed = []
    source_bytes = 0
    for path in paths:
        scope_id = f"module:{path}"
        selected = contexts[scope_id]
        if budget.halted or budget.remaining < 1 or time.monotonic() >= budget.deadline:
            rows = _deferred("budget_exhausted", mode)
        elif selected is None:
            rows = _deferred("source_slice_unavailable", mode)
        else:
            candidates, rows = analyze(selected, verified["evidence"], manifest, budget=budget,
                                       runtime_context=runtime_context, unverified=unverified,
                                       response_artifacts=response_artifacts, mode=mode)
            if any(row["status"] != "deferred" for row in rows):
                source_bytes += selected["source_bytes"]
            all_candidates.extend(screen_candidates(candidates, verified, source_bundle,
                                                    selected, unverified, path))
        if selected is not None and "review_units" in selected:
            for row in rows:
                if "review" not in row:
                    row["review"] = review_audit(selected, row)
        audit.append({"scope_id": scope_id, "perspectives": rows})
        if all(row["status"] == "completed" for row in rows):
            analyzed.append(path)
    base_sha = plan["base_sha"] if plan else None
    scope = "candidate_impact" if plan and plan["scope"] == "impact" else "full_tracked_python_git_commit"
    coverage = {"selected_paths": paths, "analyzed_paths": analyzed,
                "omitted_unknown_paths": sorted(
                    set((plan or {}).get("omitted_unknown_paths", [])) | (set(paths) - set(analyzed))),
                "source_bytes": source_bytes,
                "tokens_used": sum(row["tokens"] for item in audit for row in item["perspectives"]),
                "diagnostic_completeness": "unknown", "base_sha": base_sha, "scope": scope}
    return all_candidates, audit, coverage


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_bundle", type=Path, nargs="?")
    parser.add_argument("run_manifest", type=Path, nargs="?")
    parser.add_argument("receipt", type=Path, nargs="?")
    parser.add_argument("--symbol", help="Exact graph symbol or node ID from frozen source")
    parser.add_argument("--scope", choices=("full", "impact"), help="All tracked Python or candidate impact scope")
    parser.add_argument("--main-ref", help="Immutable candidate comparison reference (requires --candidate-ref)")
    parser.add_argument("--candidate-ref", help="Candidate revision, checked against authenticated source")
    parser.add_argument("--prompt-hash", action="store_true", help="Display frozen model prompt hash without sending data")
    parser.add_argument("--single-baseline", action="store_true",
                        help="One-model-call development baseline on --symbol or --scope full (no final or runtime output)")
    parser.add_argument("--plain-baseline", action="store_true",
                        help="One generic review of the selected function's raw source file (no graph or runtime)")
    parser.add_argument("--boundary-review", action="store_true",
                        help="Opt-in development review: retain five reviewers and add assumptions/boundary review")
    parser.add_argument("--generic-review", action="store_true",
                        help="Opt-in sixth general review with the same first five independent calls")
    parser.add_argument("--review-units", choices=("raw", "outline", "cards"), default="raw",
                        help="Approved source context: unchanged, AST outline, or bounded local syntax cards")
    parser.add_argument("--final-output", type=Path, help="Seal a source-only deferred report outside the repository")
    parser.add_argument("--runtime-output", type=Path, help="Run the approved Docker DAG and store its unadjudicated traces")
    parser.add_argument("--response-output", type=Path,
                        help="New owner-only directory outside the repository for approved provider replies")
    parser.add_argument("--prepare-manifest", type=Path,
                        help="Write a new v3 manifest bound to this exact scope without approval or transmission")
    args = parser.parse_args()
    if args.boundary_review and (args.single_baseline or args.plain_baseline):
        parser.error("--boundary-review forbids --single-baseline and --plain-baseline")
    if args.generic_review and (args.boundary_review or args.single_baseline or args.plain_baseline):
        parser.error("--generic-review cannot be combined with other review modes")
    mode = ("plain" if args.plain_baseline else "single" if args.single_baseline else
            "boundary" if args.boundary_review else "generic" if args.generic_review else "five")
    if mode in ("single", "plain") and args.review_units != "raw":
        parser.error("Single baselines do not receive graph review units")
    prompt_sha256 = prompt_hash(mode)
    if args.prompt_hash:
        print(prompt_sha256)
        return 0
    response_artifacts = None
    try:
        if not args.source_bundle or not args.run_manifest or not (args.receipt or args.prepare_manifest):
            raise ValueError("source bundle, manifest and receipt (or --prepare-manifest) are required")
        if args.prepare_manifest and (args.receipt or args.runtime_output or args.final_output or args.response_output):
            raise ValueError("Manifest preparation cannot approve, execute or produce diagnosis output")
        if not args.prepare_manifest and not args.response_output:
            raise ValueError("--response-output is required to preserve normalized model replies")
        if (args.symbol is None) == (args.scope is None):
            raise ValueError("Select exactly one of --symbol or --scope")
        if args.single_baseline and (args.scope == "impact" or args.final_output or args.runtime_output):
            raise ValueError("Single-call baseline requires --symbol or --scope full and forbids final/runtime output")
        if args.plain_baseline and (not args.symbol or args.single_baseline or
                                    args.final_output or args.runtime_output):
            raise ValueError("Plain baseline requires --symbol and forbids other baselines and final/runtime output")
        if (args.main_ref is None) != (args.candidate_ref is None):
            raise ValueError("--main-ref and --candidate-ref must be supplied together")
        if args.symbol and args.main_ref:
            raise ValueError("Candidate references require --scope")
        if args.scope == "impact" and not args.main_ref:
            raise ValueError("--scope impact requires candidate references")
        verified = verify_git_source(args.source_bundle)
        run = verified["run"]
        manifest = json.loads(args.run_manifest.read_text(encoding="utf-8"))
        if manifest.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("Use a new v3 manifest; previous approvals cannot authorize this diagnosis")
        if manifest["snapshot_sha"] != run["commit"]:
            raise ValueError("Approved snapshot differs from authenticated Git source")
        repository = Path(run["repository"]).resolve()
        source_bundle = args.source_bundle.resolve()
        analysis, contexts, plan = prepare_analysis(
            verified, mode=mode, symbol=args.symbol, scope=args.scope,
            main_ref=args.main_ref, candidate_ref=args.candidate_ref,
            review=args.review_units)
        if args.prepare_manifest:
            manifest = {**manifest, "analysis": analysis,
                        "model": {**manifest["model"], "prompt_sha256": prompt_sha256}}
            digest = manifest_hash(manifest)
            validate_model_plan(manifest, mode=mode)
            destination = args.prepare_manifest
            if (destination.resolve().is_relative_to(repository)
                    or destination.resolve().is_relative_to(source_bundle)):
                raise ValueError("Prepared manifest must be outside source and repository")
            fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2) + "\n")
            print(json.dumps({"manifest": str(destination), "manifest_sha256": digest,
                              "model_calls": 0, "target_executions": 0}))
            return 0
        manifest_hash(manifest)
        validate_model_plan(manifest, mode=mode)
        if manifest["analysis"] != analysis:
            raise ValueError("Approved analysis mode, scope or source context differs")
        if (args.receipt.resolve().is_relative_to(repository)
                or args.receipt.resolve().is_relative_to(source_bundle)):
            raise ValueError("Approval receipt must be outside the repository and source bundle")
        selected = next(iter(contexts.values())) if args.symbol or args.single_baseline else None
        selected_paths = ([key.removeprefix("module:") for key in contexts]
                          if not args.symbol and not args.single_baseline else
                          sorted({node["path"] for node in selected["nodes"]}) if selected else [])
        if args.runtime_output:
            validate_runtime_plan(manifest)
            validate_source_workloads(verified, manifest)
            if not {"log", "evidence"}.issubset(manifest["model"]["transmitted_data"]):
                raise ValueError("Runtime log and evidence transmission must be explicitly declared")
            if (args.runtime_output.resolve().is_relative_to(repository)
                    or args.runtime_output.resolve().is_relative_to(source_bundle)):
                raise ValueError("Runtime output must be outside the repository and source bundle")
            verify_approval(manifest, run["commit"], args.receipt)
            validate_runtime_host()
        verify_approval(manifest, run["commit"], args.receipt)
        response_artifacts = ResponseArtifacts(args.response_output, repository, source_bundle)
        digest = consume_approval(manifest, run["commit"], args.receipt)
        run_deadline = time.monotonic() + manifest["limits"]["wall_seconds"]
        runtime_trace = None
        runtime_context = None
        if args.runtime_output:
            execute_nodes(verified, manifest, digest, args.runtime_output, run_deadline=run_deadline)
            runtime_trace = verify_execution(args.source_bundle, manifest, args.runtime_output)
            runtime_context = summarize_execution(runtime_trace, args.runtime_output)
        unverified = []
        if args.symbol or args.single_baseline:
            candidates, audit = analyze(selected, verified["evidence"], manifest,
                                        budget=AnalysisBudget(manifest, deadline=run_deadline),
                                        mode=mode,
                                        runtime_context=runtime_context, unverified=unverified,
                                        response_artifacts=response_artifacts)
            accepted = screen_candidates(candidates, verified, args.source_bundle, selected, unverified)
            if args.symbol:
                coverage = {"scope": "selected_symbol_source_file" if args.plain_baseline else "selected_symbol_only",
                            "symbol": args.symbol,
                            "base_sha": None, "context_node_ids": [node["id"] for node in selected["nodes"]],
                            "source_bytes": selected["source_bytes"], "truncated": selected["truncated"],
                            "diagnostic_completeness": "unknown"}
            else:
                complete = audit[0]["status"] == "completed"
                coverage = {"scope": "full_tracked_python_git_commit",
                            "selected_paths": selected_paths,
                            "analyzed_paths": selected_paths if complete else [],
                            "omitted_unknown_paths": [] if complete else selected_paths,
                            "base_sha": plan["base_sha"] if plan else None,
                            "source_bytes": selected["source_bytes"],
                            "tokens_used": audit[0]["tokens"],
                            "diagnostic_completeness": "unknown"}
        else:
            accepted, audit, coverage = _batch_review(
                contexts, selected_paths, verified, args.source_bundle, manifest, plan, run_deadline,
                unverified, runtime_context, response_artifacts, mode=mode)
        accepted = isolate_conflicts(args.source_bundle, accepted, unverified)
        proofs = validate_locations(verified, accepted)
        findings = admit(args.source_bundle, accepted)
        result = {"stage": ("pilot_plain_baseline_provisional" if args.plain_baseline else
                            "pilot_baseline_provisional" if args.single_baseline else
                            "pilot_boundary_review_provisional" if args.boundary_review else
                            "pilot_generic_review_provisional" if args.generic_review else
                            "provisional_hypotheses"),
                  "scope": coverage["scope"],
                  "source_run_id": run["id"], "snapshot_sha": run["commit"],
                  "perspectives": audit, "findings": findings, "location_proofs": proofs,
                  "model_version": manifest["model"]["name_version"],
                  "priority_rows": priority_rows(findings), "unverified_candidates": unverified,
                  "runtime_attested": False}
        if response_artifacts is not None:
            result["response_artifacts"] = response_artifacts.references
        if args.symbol:
            result["symbol"] = args.symbol
        else:
            result["base_sha"] = coverage["base_sha"]
        result["diagnosis_coverage"] = coverage
        if args.final_output:
            bundle = write_final_bundle(args.source_bundle, findings, args.final_output,
                                        manifest=manifest, model_audit=audit,
                                        diagnosis_coverage=coverage,
                                        runtime_trace_dir=args.runtime_output if runtime_trace else None)
            result["final_source_only_bundle"] = str(bundle)
            verify_final_bundle(bundle, args.source_bundle,
                                runtime_trace_dir=args.runtime_output if runtime_trace else None)
        if runtime_trace is not None:
            result["runtime_trace"] = runtime_trace
            result["runtime_trace_not_adjudicated_in_source_only_report"] = True
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, subprocess.CalledProcessError) as error:
        parser.exit(2, f"approved diagnosis rejected: {error}\n")
    finally:
        if response_artifacts is not None:
            response_artifacts.close()
    print(json.dumps(result, sort_keys=True, ensure_ascii=True))
    rows = (audit if args.symbol or args.single_baseline else
            [row for scope in audit for row in scope["perspectives"]])
    return 3 if (any(row["status"] != "completed" for row in rows) or unverified or
                 runtime_trace is not None and any(node["status"] in ("failed", "deferred")
                                                   for node in runtime_trace["nodes"])) else 0


if __name__ == "__main__":
    raise SystemExit(main())
