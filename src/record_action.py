"""Record a confirmed owner action on a source-only provisional finding."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from modules.evidence.authenticity import verify_git_source
from modules.findings import admit
from modules.findings.actions import append_action
from modules.findings.locations import validate_locations
from modules.findings.snapshots import load_previous
from modules.git_modes.review_scope import plan_for_review, select_candidates
from modules.static_scan.orchestrator import git


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_bundle", type=Path)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("action_directory", type=Path)
    parser.add_argument("finding_id")
    parser.add_argument("action", choices=("verify", "fix", "accept_risk", "dismiss"))
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--previous-bundle", type=Path)
    parser.add_argument("--main-ref")
    parser.add_argument("--candidate-ref")
    parser.add_argument("--scope", choices=("impact", "full"))
    args = parser.parse_args()
    try:
        verified = verify_git_source(args.source_bundle)
        candidates = json.loads(args.candidates.read_text(encoding="utf-8"))
        if bool(args.previous) != bool(args.previous_bundle):
            raise ValueError("--previous and --previous-bundle must be supplied together")
        prior = load_previous(args.previous, args.previous_bundle, verified["run"]["repository"]) if args.previous else None
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
        observed = selection["observed_candidates"] if selection else candidates
        validate_locations(verified, observed)
        findings = admit(args.source_bundle, observed, prior["findings"] if prior else [])
        if args.finding_id not in {row["id"] for row in findings}:
            raise ValueError("Finding does not belong to this review scope")
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise ValueError("An interactive terminal is required for owner confirmation")
        print(f"Confirm finding ID ({args.finding_id}): ", end="", flush=True)
        finding_confirmation = input().strip()
        print(f"Confirm action ({args.action}): ", end="", flush=True)
        action_confirmation = input().strip()
        if finding_confirmation != args.finding_id or action_confirmation != args.action:
            raise ValueError("Owner confirmation does not match the requested action")
        record = append_action(args.source_bundle, findings, args.finding_id, args.action,
                               args.action_directory, explicit_owner_confirmation=True)
    except (EOFError, OSError, ValueError, TypeError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(2, f"action rejected: {error}\n")
    print(json.dumps(record, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
