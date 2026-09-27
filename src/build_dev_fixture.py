"""Generate a project-owned DEVELOPMENT case, excluded from sealed final scores."""

import argparse
import json
import subprocess
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "development"
PROJECT = FIXTURE.parents[1]
MUTATIONS = {
    "correctness": ("service.py", "return items[offset:offset + count]", "return items[offset:offset + count + 1]"),
    "performance": ("service.py", "operations += 1", "operations += len(items)"),
    "concurrency": ("service.py", "await asyncio.sleep(0)\n    events.append", "__import__('time').sleep(0.01)\n    events.append"),
    "cancellation": ("service.py", "    await asyncio.sleep(60)\n", "    try:\n        await asyncio.sleep(60)\n    except asyncio.CancelledError:\n        return\n"),
    "api_contract": ("service.py", "HTTPException(status_code=404", "HTTPException(status_code=200"),
    "cross_file": ("helper.py", "return value.strip()", "return value"),
}


def build(destination: Path, mutation: str) -> dict:
    destination = destination.resolve()
    if destination == PROJECT or destination.is_relative_to(PROJECT):
        raise ValueError("Development cases must be outside this repository")
    destination.mkdir(mode=0o700)
    for filename in ("service.py", "helper.py", "oracle.py", "requirements.txt"):
        contents = (FIXTURE / filename).read_text(encoding="utf-8")
        if mutation != "clean" and filename == MUTATIONS[mutation][0]:
            _, before, after = MUTATIONS[mutation]
            if contents.count(before) != 1:
                raise ValueError("Fixture mutation anchor is not unique")
            contents = contents.replace(before, after, 1)
        (destination / filename).write_text(contents, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(destination)], check=True)
    subprocess.run(["git", "-C", str(destination), "add",
                    "service.py", "helper.py", "oracle.py", "requirements.txt"], check=True)
    subprocess.run(["git", "-C", str(destination), "-c", "user.name=Fixture",
                    "-c", "user.email=fixture@example.invalid", "commit", "-qm", mutation], check=True)
    sha = subprocess.run(["git", "-C", str(destination), "rev-parse", "HEAD"],
                         check=True, capture_output=True, text=True).stdout.strip()
    return {"lane": "development_only", "mutation": mutation, "snapshot_sha": sha,
            "repository": str(destination), "oracle_argv": ["python3", "-m", "unittest", "oracle", "-q"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--mutation", choices=("clean", *MUTATIONS), required=True)
    args = parser.parse_args()
    try:
        record = build(args.destination, args.mutation)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(2, f"development fixture rejected: {error}\n")
    print(json.dumps(record, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
