"""Show immutable main or candidate source coverage before diagnosis."""

import argparse
import json
import subprocess
from pathlib import Path

from modules.git_modes import plan_candidate, plan_main


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    modes = parser.add_subparsers(dest="mode", required=True)
    scheduled = modes.add_parser("main", help="Full tracked-Python scope at main")
    scheduled.add_argument("main_ref")
    scheduled.add_argument("--previous-accepted-sha")
    candidate = modes.add_parser("candidate", help="Merge-base candidate source scope")
    candidate.add_argument("main_ref")
    candidate.add_argument("candidate_ref")
    candidate.add_argument("--scope", choices=("impact", "full"), required=True)
    args = parser.parse_args()
    try:
        if args.mode == "main":
            result = plan_main(args.repository, args.main_ref, args.previous_accepted_sha)
        else:
            result = plan_candidate(args.repository, args.main_ref, args.candidate_ref, args.scope)
    except (subprocess.CalledProcessError, ValueError) as error:
        parser.exit(2, f"scan plan rejected: {error}\n")
    print(json.dumps(result, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
