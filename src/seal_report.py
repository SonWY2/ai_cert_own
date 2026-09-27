"""Seal a provisional source-only review into five authenticated record files."""

import argparse
import json
import subprocess
from pathlib import Path

from modules.evidence.authenticity import verify_git_source
from modules.evidence.final_bundle import verify_final_bundle, write_final_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_bundle", type=Path)
    parser.add_argument("provisional_review", type=Path)
    parser.add_argument("output_root", type=Path)
    parser.add_argument("--run-manifest", type=Path)
    parser.add_argument("--actions", type=Path, help="Snapshot owner-confirmed actions without changing prior bundles")
    parser.add_argument("--runtime-trace-dir", type=Path,
                        help="Include a separately verified, explicitly unattested execution trace")
    args = parser.parse_args()
    try:
        verified = verify_git_source(args.source_bundle)
        review = json.loads(args.provisional_review.read_text(encoding="utf-8"))
        if (not isinstance(review, dict) or review.get("stage") != "provisional_hypotheses" or
                review.get("source_run_id") != verified["run"]["id"] or
                not isinstance(review.get("findings"), list)):
            raise ValueError("Provisional review does not belong to authenticated source")
        if review.get("runtime_attested", False):
            raise ValueError("Runtime claim cannot be sealed from a provisional review")
        manifest = json.loads(args.run_manifest.read_text(encoding="utf-8")) if args.run_manifest else None
        audit = review.get("perspectives")
        if audit is not None and manifest is None:
            raise ValueError("Model audit requires its exact frozen RunManifest")
        coverage = review.get("diagnosis_coverage")
        if coverage is not None and (not isinstance(coverage, dict) or
                                     review.get("scope") != coverage.get("scope") or
                                     review.get("base_sha") != coverage.get("base_sha")):
            raise ValueError("Review scope differs from its recorded diagnosis coverage")
        if review.get("scope") == "selected_symbol_only" and (
                coverage is None or review.get("symbol") != coverage.get("symbol")):
            raise ValueError("Selected symbol differs from its recorded diagnosis coverage")
        if args.runtime_trace_dir is not None and manifest is None:
            raise ValueError("Runtime trace requires its exact frozen RunManifest")
        saved = write_final_bundle(args.source_bundle, review["findings"], args.output_root,
                                   manifest=manifest, model_audit=audit,
                                   action_directory=args.actions, diagnosis_coverage=coverage,
                                   runtime_trace_dir=args.runtime_trace_dir)
        confirmed = verify_final_bundle(saved, args.source_bundle,
                                        runtime_trace_dir=args.runtime_trace_dir)
    except (OSError, ValueError, TypeError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(2, f"final report rejected: {error}\n")
    print(json.dumps({"bundle": str(saved), "run_id": confirmed["run"]["id"],
                      "status": confirmed["report"]["scan_status"],
                      "analysis_status": confirmed["report"]["analysis_status"],
                      "candidate_counts": confirmed["report"]["candidate_counts"],
                      "findings": len(confirmed["findings"]),
                      "confirmed": confirmed["report"]["confirmed_count"],
                      "actions": len(confirmed["actions"])},
                     sort_keys=True, ensure_ascii=True))
    return 3 if confirmed["report"]["analysis_status"] == "incomplete" else 0


if __name__ == "__main__":
    raise SystemExit(main())
