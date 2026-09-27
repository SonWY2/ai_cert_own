"""Prove candidate line spans exist in authenticated, immutable Git source blobs.

A location proof establishes physical line existence only; it does not validate a
symbol, a claimed defect, or any outcome of running the source.
"""

import hashlib
import re

from modules.evidence.authenticity import _git


def validate_locations(verified_git_source, candidate_list):
    """Return one bounded location proof per candidate in input order.

    The caller must pass the result of verify_git_source, not an unverified bundle.
    Each proof hashes the original bytes of its selected inclusive line span,
    including its original line terminators when present.
    """
    if not isinstance(verified_git_source, dict) or not isinstance(candidate_list, (list, tuple)):
        raise ValueError("Verified source and candidates are required")
    try:
        repository = verified_git_source["run"]["repository"]
        evidence = verified_git_source["evidence"]
        sources = {record["path"]: record for record in evidence}
    except (KeyError, TypeError) as error:
        raise ValueError("Invalid verified source") from error
    if not isinstance(repository, str) or not isinstance(evidence, list) or len(sources) != len(evidence):
        raise ValueError("Invalid verified source")
    blobs = {}
    proofs = []
    for candidate in candidate_list:
        if not isinstance(candidate, dict) or not isinstance(candidate.get("location"), dict):
            raise ValueError("Candidate requires a location")
        location = candidate["location"]
        path = location.get("path")
        if not isinstance(path, str) or path not in sources:
            raise ValueError("Location path is outside verified evidence")
        source = sources[path]
        evidence_ids = candidate.get("evidence_ids")
        if (not isinstance(evidence_ids, list) or not evidence_ids or
                any(not isinstance(item, str) or item != source["id"] for item in evidence_ids)):
            raise ValueError("Location evidence ID does not belong to its verified path")
        line = location.get("line")
        end_line = location.get("end_line", line)
        if (type(line) is not int or type(end_line) is not int or
                line < 1 or end_line < line):
            raise ValueError("Invalid physical line span")
        if path not in blobs:
            content = _git(repository, "cat-file", "blob", source["blob_oid"])
            if hashlib.sha256(content).hexdigest() != source["source_sha256"]:
                raise ValueError("Git blob differs from verified source evidence")
            blobs[path] = re.findall(rb"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+$", content)
        lines = blobs[path]
        if end_line > len(lines):
            raise ValueError("Physical line span exceeds Git blob")
        proofs.append({"path": path, "line": line, "end_line": end_line,
                       "evidence_ids": sorted(set(evidence_ids)),
                       "source_slice_sha256": hashlib.sha256(b"".join(lines[line - 1:end_line])).hexdigest()})
    return proofs
