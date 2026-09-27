"""Display an exact v2 RunManifest and record manual approval; execute nothing."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from modules.run_policy import PolicyError, issue_approval, manifest_hash
from modules.static_scan.orchestrator import git


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("receipt", type=Path, help="New receipt outside the repository")
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        digest = manifest_hash(manifest)
        sha = manifest["snapshot_sha"]
        git(args.repository, "cat-file", "-e", f"{sha}^{{commit}}")
        if git(args.repository, "rev-parse", "--is-bare-repository").strip() != b"true":
            source_root = Path(git(args.repository, "rev-parse", "--show-toplevel").decode().strip())
            if args.receipt.resolve().is_relative_to(source_root.resolve()):
                raise PolicyError("approval receipt must be outside the source repository")
        if not sys.stdin.isatty():
            raise PolicyError("approval requires an interactive terminal")
        print(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True))
        analysis = manifest["analysis"]
        if analysis is not None:
            print(f"Analysis: {analysis['mode']} / {analysis['scope']}; "
                  f"roles: {', '.join(analysis['roles'])}; "
                  f"frozen contexts: {len(analysis['contexts'])}")
            print("Only the declared mode, scope and exact context digests are approved.")
        if manifest["nodes"]:
            print("주의: 현재 Docker에서는 CPU·메모리·PID 요청값이 강제되지 않을 수 있음. "
                  "실행 시 경고와 결과를 확인하세요.")
        print(f"Manifest SHA-256: {digest}")
        typed = input("승인하려면 위 SHA-256을 그대로 입력: ").strip()
        issue_approval(manifest, sha, args.receipt, typed)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(2, f"approval rejected: {error}\n")
    print(f"Approval recorded: {args.receipt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
