"""Consume one manual approval then run declared, network-isolated Docker nodes.

A container exit code is an execution trace, not independent defect confirmation.
"""

import argparse
import json
import subprocess
from pathlib import Path

from modules.evidence.authenticity import verify_git_source
from modules.run_policy import consume_approval, verify_approval
from modules.runtime_exec.docker import (
    execute_nodes, validate_runtime_host, validate_runtime_plan, validate_source_workloads,
    verify_execution,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true",
                        help="verify a recorded trace and artifact bytes offline; never consume approval")
    parser.add_argument("source_bundle", type=Path)
    parser.add_argument("run_manifest", type=Path)
    parser.add_argument("paths", nargs="+", type=Path,
                        help="execution: RECEIPT EVIDENCE_ROOT; --verify: EVIDENCE_ROOT")
    args = parser.parse_args()
    if len(args.paths) != (1 if args.verify else 2):
        parser.error("--verify needs EVIDENCE_ROOT; execution needs RECEIPT EVIDENCE_ROOT")
    try:
        manifest = json.loads(args.run_manifest.read_text(encoding="utf-8"))
        if args.verify:
            result = verify_execution(args.source_bundle, manifest, args.paths[0])
        else:
            verified = verify_git_source(args.source_bundle)
            run = verified["run"]
            validate_runtime_plan(manifest)
            if manifest["snapshot_sha"] != run["commit"]:
                raise ValueError("RunManifest differs from authenticated source commit")
            validate_source_workloads(verified, manifest)
            repository = Path(run["repository"]).resolve()
            source = args.source_bundle.resolve()
            receipt, evidence_root = args.paths
            if (receipt.resolve().is_relative_to(repository)
                    or receipt.resolve().is_relative_to(source)):
                raise ValueError("Approval receipt must be outside target repository and source bundle")
            if (evidence_root.resolve().is_relative_to(repository)
                    or evidence_root.resolve().is_relative_to(source)):
                raise ValueError("Execution evidence must be outside target repository and source bundle")
            verify_approval(manifest, run["commit"], receipt)
            validate_runtime_host()
            digest = consume_approval(manifest, run["commit"], receipt)
            result = execute_nodes(verified, manifest, digest, evidence_root)
    except (OSError, ValueError, TypeError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(2, f"execution rejected: {error}\n")
    print(json.dumps(result, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
