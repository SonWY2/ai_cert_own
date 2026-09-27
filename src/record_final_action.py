"""Record an owner decision after authenticating the immutable final report."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from modules.evidence.final_bundle import verify_final_bundle
from modules.findings.actions import append_action, read_actions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_bundle", type=Path)
    parser.add_argument("final_bundle", type=Path)
    parser.add_argument("action_directory", type=Path, help="Existing owner-only directory outside repository")
    parser.add_argument("finding_id")
    parser.add_argument("action", choices=("verify", "fix", "accept_risk", "dismiss"))
    parser.add_argument("--runtime-trace-dir", type=Path,
                        help="Required when final report references an execution trace")
    args = parser.parse_args()
    try:
        final = verify_final_bundle(args.final_bundle, args.source_bundle,
                                    runtime_trace_dir=args.runtime_trace_dir)
        source_ids = {row["id"]: row["source_evidence_id"] for row in final["evidence"]}
        admitted = [{**row, "evidence_ids": [source_ids[item] for item in row["evidence_ids"]]}
                    for row in final["findings"]]
        if args.finding_id not in {row["id"] for row in admitted}:
            raise ValueError("Finding does not belong to the verified final report")
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise ValueError("An interactive terminal is required for owner confirmation")
        print(f"Confirm finding ID ({args.finding_id}): ", end="", flush=True)
        finding_confirmation = input().strip()
        print(f"Confirm action ({args.action}): ", end="", flush=True)
        action_confirmation = input().strip()
        if finding_confirmation != args.finding_id or action_confirmation != args.action:
            raise ValueError("Owner confirmation does not match the requested action")
        record = append_action(args.source_bundle, admitted, args.finding_id, args.action,
                               args.action_directory, explicit_owner_confirmation=True)
        latest = read_actions(args.source_bundle, admitted, args.action_directory)
    except (EOFError, OSError, ValueError, TypeError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(2, f"action rejected: {error}\n")
    print(json.dumps({"action_id": record["id"], "finding_id": args.finding_id,
                      "latest_action": latest[args.finding_id],
                      "evidence_status": final["report"]["scan_status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
