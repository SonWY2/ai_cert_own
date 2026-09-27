"""Summarize a preexisting trusted local cProfile artifact; no runtime attestation."""

import argparse
import json
import subprocess
from pathlib import Path

from modules.evidence.authenticity import verify_git_source
from modules.evidence.profile import normalize_trusted_pstats
from modules.run_policy import manifest_hash
from modules.static_scan.orchestrator import graph
from modules.static_scan.retrieval import retrieve


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_bundle", type=Path)
    parser.add_argument("run_manifest", type=Path)
    parser.add_argument("node_id")
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--trusted-local-artifact", action="store_true",
                        help="Assert the pstats marshal file and path came from a trusted local operator")
    parser.add_argument("--hotspot-index", type=int,
                        help="Locate one mapped hotspot in authenticated Git source (zero-based)")
    args = parser.parse_args()
    try:
        if not args.trusted_local_artifact:
            raise ValueError("marshal input requires explicit --trusted-local-artifact")
        manifest = json.loads(args.run_manifest.read_text(encoding="utf-8"))
        digest = manifest_hash(manifest)
        nodes = [node for node in manifest["nodes"] if node["id"] == args.node_id]
        if len(nodes) != 1 or nodes[0]["tool"] != "cprofile":
            raise ValueError("node must declare the cprofile tool in the manifest")
        summary = normalize_trusted_pstats(
            args.artifact, args.source_bundle, manifest["snapshot_sha"],
            nodes[0]["argv"], digest, args.node_id, trusted_artifact=True)
        if args.hotspot_index is not None:
            if not 0 <= args.hotspot_index < len(summary["hotspots"]):
                raise ValueError("hotspot index is outside the displayed summary")
            hotspot = summary["hotspots"][args.hotspot_index]
            if hotspot["file_mapping"] != "resolved":
                raise ValueError("hotspot filename is not mapped to source")
            verified = verify_git_source(args.source_bundle)
            run = verified["run"]
            if run["id"] != summary["source_run_id"] or run["commit"] != summary["snapshot_sha"]:
                raise ValueError("hotspot source differs from authenticated Git")
            evidence = next(record for record in verified["evidence"] if record["path"] == hotspot["file"])
            scanned, database = graph(Path(run["repository"]), run["commit"])
            try:
                located = retrieve(database, frame=(hotspot["file"], hotspot["line"]))
            finally:
                database.close()
            node = next((node for node in located["nodes"]
                         if node["id"] == located["frame"]["node_id"]), None)
            if (scanned["commit"] != run["commit"] or
                    located["frame"]["source_sha256"] != evidence["source_sha256"] or
                    node is None or node["kind"] != "function" or
                    node["line"] != hotspot["line"] or
                    node["name"].rsplit(".", 1)[-1] != hotspot["function"]):
                raise ValueError("hotspot does not identify a complete matching Git function")
            summary["hotspot_context"] = located
    except (OSError, ValueError, TypeError, KeyError, StopIteration, subprocess.CalledProcessError) as error:
        parser.exit(2, f"profile rejected: {error}\n")
    print(json.dumps(summary, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
