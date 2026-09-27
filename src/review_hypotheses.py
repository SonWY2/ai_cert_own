"""Validate caller hypotheses against source provenance and rank them as deferred."""

import argparse
import json
import subprocess
from pathlib import Path

from modules.evidence.authenticity import verify_git_source
from modules.findings import admit, compare, priority_rows
from modules.findings.locations import validate_locations
from modules.findings.snapshots import load_previous, save_snapshot
from modules.findings.actions import read_actions
from modules.git_modes.review_scope import plan_for_review, select_candidates
from modules.static_scan.orchestrator import git


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_bundle", type=Path)
    parser.add_argument("candidates", type=Path, help="JSON array of externally supplied hypotheses")
    parser.add_argument("--previous", type=Path, help="Previously sealed provisional snapshot")
    parser.add_argument("--previous-bundle", type=Path, help="Git-authenticated source bundle for --previous")
    parser.add_argument("--save-snapshot", type=Path, help="New immutable provisional snapshot in a private directory")
    parser.add_argument("--actions", type=Path, help="Owner action directory for this exact source run")
    parser.add_argument("--main-ref", help="Plan a full main scan or compare a candidate against main")
    parser.add_argument("--candidate-ref", help="Candidate Git revision for impact/full selection")
    parser.add_argument("--scope", choices=("impact", "full"), help="Candidate observation scope")
    args = parser.parse_args()
    try:
        verified = verify_git_source(args.source_bundle)
        candidates = json.loads(args.candidates.read_text(encoding="utf-8"))
        if bool(args.previous) != bool(args.previous_bundle):
            raise ValueError("--previous and --previous-bundle must be supplied together")
        prior = load_previous(args.previous, args.previous_bundle, verified["run"]["repository"]) if args.previous else None
        previous = prior["findings"] if prior else []
        plan = plan_for_review(verified, args.main_ref, args.candidate_ref, args.scope,
                               previous_sha=prior["commit"] if prior else None)
        if prior and plan and plan["base_sha"] != prior["commit"]:
            raise ValueError("Previous snapshot commit is not the planned base SHA")
        if prior:
            try:
                git(verified["run"]["repository"], "merge-base", "--is-ancestor",
                    prior["commit"], verified["run"]["commit"])
            except subprocess.CalledProcessError as error:
                if error.returncode == 1:
                    raise ValueError("Previous snapshot commit is not an ancestor of the target") from error
                raise
        if plan and plan.get("skipped"):
            raise ValueError("Already reviewed this immutable main SHA")
        selection = select_candidates(verified, plan, candidates) if plan else None
        candidates = selection["observed_candidates"] if selection else candidates
        location_proofs = validate_locations(verified, candidates)
        findings = admit(args.source_bundle, candidates, previous)
        changes = {row["id"]: row["status"] for row in compare(previous, findings, complete=False)} if previous else {}
        actions = read_actions(args.source_bundle, findings, args.actions) if args.actions else {}
        rows = priority_rows(findings, changes=changes, actions=actions)
        output = {"stage": "provisional_hypotheses", "source_run_id": verified["run"]["id"],
                  "source_files": verified["inventory_count"], "findings": findings,
                  "priority_rows": rows, "location_proofs": location_proofs}
        if plan:
            output["scope"] = {"mode": plan["mode"], "selected": plan["scope"],
                               "omitted_unknown_paths": selection["omitted_unknown_paths"],
                               "coverage": selection["coverage"]}
        if args.save_snapshot:
            save_snapshot(output, verified, args.save_snapshot, source_bundle=args.source_bundle)
            output["snapshot_path"] = str(args.save_snapshot)
    except (OSError, ValueError, TypeError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(2, f"hypotheses rejected: {error}\n")
    print(json.dumps(output, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
