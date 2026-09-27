"""Authenticate stored source provenance against immutable Git commit blobs."""

import hashlib
import re
import subprocess
from pathlib import Path

from .provenance import verify_source_run

_FULL_OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


def _git(repository: Path, *args: str) -> bytes:
    try:
        return subprocess.run(["git", "--no-replace-objects", "-C", str(repository), *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError("Unable to verify Git source") from error


def verify_git_source(bundle: Path) -> dict:
    """Verify every tracked Python blob against a stored source-only run.

    This proves source identity, not successful parsing or absence of defects.
    """
    verified = verify_source_run(bundle)
    run = verified["run"]
    repository_name = run["repository"]
    if not isinstance(repository_name, str) or not repository_name or not Path(repository_name).is_absolute():
        raise ValueError("Repository must be an absolute Git path")
    repository = Path(repository_name)
    if not repository.is_dir():
        raise ValueError("Repository must be an existing Git directory")
    commit = run["commit"]
    if not isinstance(commit, str) or not _FULL_OID.fullmatch(commit):
        raise ValueError("Invalid commit OID")
    resolved = _git(repository, "rev-parse", "--verify", "--end-of-options",
                    f"{commit}^{{commit}}").decode("ascii").strip()
    if resolved != commit:
        raise ValueError("Run commit does not resolve to its full commit OID")

    actual = {}
    for entry in _git(repository, "ls-tree", "-rz", "--full-tree", commit).split(b"\0"):
        if not entry:
            continue
        try:
            metadata, raw_path = entry.split(b"\t", 1)
            mode, kind, oid = metadata.split(b" ")
            path = raw_path.decode("utf-8", "surrogateescape")
            oid_text = oid.decode("ascii")
        except (ValueError, UnicodeDecodeError) as error:
            raise ValueError("Invalid Git tree entry") from error
        if not raw_path.endswith(b".py"):
            continue
        if mode not in (b"100644", b"100755") or kind != b"blob":
            continue
        content = _git(repository, "cat-file", "blob", oid_text)
        actual[path] = (oid_text, hashlib.sha256(content).hexdigest())

    expected = {item["path"]: (item["blob_oid"], item["source_sha256"])
                for item in verified["evidence"]}
    if actual != expected:
        raise ValueError("Stored source inventory differs from Git commit")
    return {**verified, "inventory_count": len(actual)}
