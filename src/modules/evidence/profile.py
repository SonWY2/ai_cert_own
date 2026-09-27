"""Offline normalization of caller-trusted cProfile marshal artifacts.

Only call this API for artifacts produced by a trusted operator in a trusted
environment. Python's marshal format is not safe for untrusted data. This
module never executes target code or establishes runtime approval.
"""

import hashlib
import io
import math
import marshal
import re
from pathlib import Path

from .provenance import verify_source_run

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_MAX_ARTIFACT_BYTES = 32 * 1024 * 1024
_MAX_ROWS = 100_000
_MAX_TOP = 100


def normalize_trusted_pstats(
    artifact: Path,
    source_bundle: Path,
    snapshot_sha: str,
    command_argv: list[str],
    manifest_hash: str,
    node_id: str,
    *,
    trusted_artifact: bool = False,
    top_n: int = 20,
) -> dict:
    """Summarize a *trusted* preexisting pstats file; do not infer runtime approval.

    ``trusted_artifact=True`` asserts that the file and its path are trusted.
    Snapshot and manifest links are caller declarations, not execution proof.
    """
    if not trusted_artifact:
        raise ValueError("marshal requires trusted_artifact=True and a trusted artifact path")
    if not isinstance(snapshot_sha, str) or not snapshot_sha:
        raise ValueError("Invalid snapshot SHA")
    if not isinstance(manifest_hash, str) or not _SHA.fullmatch(manifest_hash):
        raise ValueError("Invalid manifest hash")
    if not isinstance(node_id, str) or not node_id:
        raise ValueError("Invalid node ID")
    if (not isinstance(command_argv, list) or not command_argv or
            any(not isinstance(arg, str) or not arg for arg in command_argv)):
        raise ValueError("Invalid command argv")
    if isinstance(top_n, bool) or not isinstance(top_n, int) or not 1 <= top_n <= _MAX_TOP:
        raise ValueError("Invalid top_n")

    source = verify_source_run(source_bundle)
    if source["run"]["commit"] != snapshot_sha:
        raise ValueError("Snapshot SHA does not match verified source bundle")
    path = Path(artifact)
    if not path.is_file() or not 0 < path.stat().st_size <= _MAX_ARTIFACT_BYTES:
        raise ValueError("Invalid pstats artifact size")
    raw = path.read_bytes()
    if not 0 < len(raw) <= _MAX_ARTIFACT_BYTES:
        raise ValueError("Invalid pstats artifact size")
    artifact_sha256 = hashlib.sha256(raw).hexdigest()
    try:
        stream = io.BytesIO(raw)
        stats = marshal.load(stream)
        if stream.read(1) or not isinstance(stats, dict) or not 0 < len(stats) <= _MAX_ROWS:
            raise ValueError("Invalid pstats row count or trailing bytes")
    except (EOFError, ValueError, TypeError, OSError) as error:
        raise ValueError("Invalid pstats artifact") from error

    sources = {record["path"] for record in source["evidence"]}
    rows = []
    for key, values in stats.items():
        if (not isinstance(key, tuple) or len(key) != 3 or
                not isinstance(key[0], str) or not isinstance(key[1], int) or
                isinstance(key[1], bool) or key[1] < 0 or
                not isinstance(key[2], str) or
                not isinstance(values, tuple) or len(values) != 5):
            raise ValueError("Invalid pstats row")
        primitive_calls, total_calls, self_seconds, cumulative_seconds, callers = values
        if (any(isinstance(v, bool) or not isinstance(v, int) or v < 0
                for v in (primitive_calls, total_calls)) or
                primitive_calls > total_calls or
                any(isinstance(v, bool) or not isinstance(v, (int, float)) or
                    not math.isfinite(v) or v < 0 for v in (self_seconds, cumulative_seconds)) or
                self_seconds > cumulative_seconds or not isinstance(callers, dict)):
            raise ValueError("Invalid pstats row")
        filename, line, function = key
        # Only exact snapshot-relative paths are linked. Absolute/ambiguous
        # profiler paths remain unknown rather than guessing basename matches.
        mapped = filename if filename in sources else None
        rows.append({"file": mapped, "file_mapping": "resolved" if mapped else "unknown",
                     "profiler_file": filename, "line": line, "function": function,
                     "calls": total_calls, "primitive_calls": primitive_calls,
                     "cumulative_seconds": float(cumulative_seconds),
                     "self_seconds": float(self_seconds)})
    rows.sort(key=lambda row: (-row["cumulative_seconds"], -row["self_seconds"],
                               row["profiler_file"], row["line"], row["function"]))
    return {"kind": "runtime_profile_summary", "source_run_id": source["run"]["id"],
            "snapshot_sha": snapshot_sha, "manifest_hash": manifest_hash,
            "node_id": node_id, "command_argv": list(command_argv),
            "artifact_sha256": artifact_sha256, "total_rows": len(rows),
            "hotspots": rows[:top_n], "provenance": "caller_declared_unattested",
            "limitations": ["Trusted marshal input only; untrusted artifacts must not be decoded.",
                            "Command, snapshot, manifest and node linkage are caller-declared, not independently attested.",
                            "This summary does not confirm findings, workload reproducibility, or runtime approval.",
                            "Only exact source-relative profiler filenames map to the verified source bundle."]}
