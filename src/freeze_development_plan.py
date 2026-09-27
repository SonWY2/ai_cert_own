"""Record a local development comparison plan before collecting model responses.

A local file hash is not an independent timestamp or consent to transmit source.
Each planned diagnosis still requires its own exact owner-approved RunManifest.
"""

import argparse
import json
import os
import random
import stat
from pathlib import Path

from modules.evaluation.development import validate_plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft", type=Path, help="Plan JSON without the randomized order")
    parser.add_argument("output", type=Path, help="New file under an existing private directory")
    args = parser.parse_args()
    try:
        draft = json.loads(args.draft.read_text(encoding="utf-8"))
        if not isinstance(draft, dict) or "order" in draft:
            raise ValueError("Draft must be an object without results or run order")
        arms = draft["arms"]
        order = [[case["id"], trial, arm] for case in draft["cases"]
                 for trial in case["trials"] for arm in arms]
        random.Random(draft["seed"]).shuffle(order)
        plan = {**draft, "order": order}
        validated = validate_plan(plan)
        destination = args.output.absolute()
        parent = destination.parent
        info = parent.lstat()
        repository = Path(__file__).resolve().parents[1]
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or
                info.st_mode & 0o077 or destination.is_relative_to(repository) or
                destination.exists() or destination.is_symlink()):
            raise ValueError("Output must be a new file in an owner-only directory outside this repository")
        payload = json.dumps(plan, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        print(json.dumps({"plan": str(destination), **validated,
                          "model_calls": 0, "target_executions": 0}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"development plan rejected: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
