"""Isolate invalid model rows without losing independent source-only hypotheses."""

from modules.evidence.provenance import verify_source_run
from modules.findings.admission import _identity, admit
from modules.findings.locations import validate_locations


def _reject_candidate(candidate, unverified, reason):
    entry = candidate["_audit"]
    entry.update(status="unverified", reason=reason, finding_id=None)
    if unverified is not None:
        unverified.append({"perspective": candidate["perspective"], "reason": reason,
                           "candidate": entry["candidate"],
                           "response_sha256": candidate["_response_sha256"],
                           "candidate_index": entry["index"],
                           "candidate_sha256": entry["candidate_sha256"]})


def screen_candidates(candidates, verified, source_bundle, context, unverified, path=None):
    """Validate each enriched row against schema, sent context and immutable lines.

    ``verified`` must come from the caller's Git authentication before transmission.
    Source bundle integrity errors remain fatal, rather than becoming row errors.
    """
    source = verify_source_run(source_bundle)
    if source["run"] != verified["run"] or source["evidence"] != verified["evidence"]:
        raise ValueError("Source bundle differs from authenticated source")
    sources = {item["path"]: item["id"] for item in verified["evidence"]}
    accepted = []
    for candidate in candidates:
        raw = candidate["_audit"]["candidate"]
        if not isinstance(raw, dict) or not isinstance(raw.get("location"), dict):
            _reject_candidate(candidate, unverified, "candidate_schema_invalid")
            continue
        location = raw["location"]
        location_path = location.get("path")
        if not isinstance(location_path, str):
            _reject_candidate(candidate, unverified, "candidate_schema_invalid")
            continue
        if (location_path not in sources or
                raw.get("evidence_ids") != [sources[location_path]]):
            _reject_candidate(candidate, unverified, "candidate_source_invalid")
            continue
        try:
            finding = admit(source_bundle, [candidate])[0]
        except (ValueError, TypeError, KeyError):
            _reject_candidate(candidate, unverified, "candidate_schema_invalid")
            continue
        if ((path is not None and location_path != path) or
                not any(node["path"] == location_path and
                        node["line"] <= location["line"] and
                        location.get("end_line", location["line"]) <= node["end_line"]
                        for node in context["nodes"])):
            _reject_candidate(candidate, unverified, "candidate_location_outside_context")
            continue
        try:
            validate_locations(verified, [candidate])
        except (ValueError, TypeError, KeyError):
            _reject_candidate(candidate, unverified, "candidate_git_line_invalid")
            continue
        candidate["_audit"].update(status="accepted", reason=None, finding_id=finding["id"])
        accepted.append(candidate)
    return accepted


def isolate_conflicts(source_bundle, candidates, unverified):
    """Quarantine every member of an ambiguous exact admission identity group."""
    groups = {}
    for candidate in candidates:
        # Admission normalizes text before deriving identity and merge semantics.
        finding = admit(source_bundle, [candidate])[0]
        identity = _identity(finding["repository"], finding)
        groups.setdefault(identity, []).append((candidate, finding))
    conflicting = set()
    for identity, group in groups.items():
        first = group[0][1]
        if any(any(finding[key] != first[key]
                   for key in ("trigger", "taxonomy", "next_action")) or
               finding["location"]["path"] != first["location"]["path"]
               for _, finding in group[1:]):
            for candidate, _ in group:
                _reject_candidate(candidate, unverified, "candidate_identity_conflict")
                conflicting.add(id(candidate))
    return [candidate for candidate in candidates if id(candidate) not in conflicting]
