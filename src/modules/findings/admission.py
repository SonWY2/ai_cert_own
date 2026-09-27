"""Admit caller hypotheses against a verified source-stage evidence bundle.

The source record proves only that a path was present in the frozen scan. Neither
that record nor a caller's claim establishes a defect or confirms an outcome.
"""

import hashlib
import json
from pathlib import Path

from modules.evidence.provenance import verify_source_run

TAXONOMIES = frozenset({"structure", "correctness", "performance", "concurrency", "tests"})
SEVERITIES = ("Critical", "High", "Medium", "Low")


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be nonempty text")
    return value.strip()


def _identity(repository, candidate):
    return (repository, candidate["root_symbol"], candidate["mechanism"],
            candidate["condition"], candidate["impact"])


def _id(identity):
    payload = json.dumps(identity, ensure_ascii=False, separators=(",", ":")).encode()
    return "F" + hashlib.sha256(payload).hexdigest()[:24].upper()


def _validate_candidate(candidate, sources):
    if not isinstance(candidate, dict):
        raise ValueError("Candidate must be an object")
    required = ("root_symbol", "mechanism", "condition", "impact", "trigger",
                "taxonomy", "severity", "location", "evidence_ids", "next_action")
    if any(key not in candidate for key in required):
        raise ValueError("Candidate is missing required fields")
    result = {key: _text(candidate[key], key) for key in
              ("root_symbol", "mechanism", "condition", "impact", "trigger")}
    if candidate["taxonomy"] not in TAXONOMIES or candidate["severity"] not in SEVERITIES:
        raise ValueError("Invalid taxonomy or severity")
    result.update(taxonomy=candidate["taxonomy"], severity=candidate["severity"])
    location = candidate["location"]
    if not isinstance(location, dict) or not isinstance(location.get("line"), int) or isinstance(location.get("line"), bool) or location["line"] < 1:
        raise ValueError("Location requires a positive line")
    path = _text(location.get("path"), "location.path")
    if path not in sources:
        raise ValueError("Location is outside source records")
    if "end_line" in location and (not isinstance(location["end_line"], int) or isinstance(location["end_line"], bool) or location["end_line"] < location["line"]):
        raise ValueError("Invalid location end_line")
    result["location"] = {"path": path, "line": location["line"]}
    if "end_line" in location:
        result["location"]["end_line"] = location["end_line"]
    evidence_ids = candidate["evidence_ids"]
    if not isinstance(evidence_ids, list) or not evidence_ids or any(not isinstance(item, str) or item not in sources[path] for item in evidence_ids):
        raise ValueError("Evidence must reference source record(s) for the location path")
    result["evidence_ids"] = sorted(set(evidence_ids))
    action = candidate["next_action"]
    if not isinstance(action, dict) or set(action) != {"action", "oracle", "time_minutes"}:
        raise ValueError("Next action requires action, falsifiable oracle, and estimated minutes")
    if type(action["time_minutes"]) is not int or action["time_minutes"] <= 0:
        raise ValueError("Next action requires positive estimated minutes")
    result["next_action"] = {key: _text(action[key], "next_action." + key) for key in ("action", "oracle")}
    result["next_action"]["time_minutes"] = action["time_minutes"]
    if "perspective" in candidate:
        result["perspective"] = _text(candidate["perspective"], "perspective")
    return result


def admit(bundle, candidates, previous=()):
    """Return source-only deferred hypotheses; never execute code or confirm claims.

    bundle is a provenance directory accepted by verify_source_run; candidates are
    caller-authored dicts. previous is a sequence of earlier admitted records used
    exclusively to reuse opaque IDs for exact identities. Invalid input fails closed.
    """
    verified = verify_source_run(Path(bundle))
    repository = verified["run"]["repository"]
    sources = {}
    for record in verified["evidence"]:
        sources.setdefault(record["path"], set()).add(record["id"])
    if not isinstance(candidates, (list, tuple)) or not isinstance(previous, (list, tuple)):
        raise ValueError("Candidates and previous must be sequences")
    earlier = {}
    used = {}
    for item in previous:
        if not isinstance(item, dict) or item.get("repository") != repository:
            raise ValueError("Previous finding repository mismatch")
        identity = (repository, *(_text(item.get(key), key) for key in
                                  ("root_symbol", "mechanism", "condition", "impact")))
        old_id = item.get("id")
        if not isinstance(old_id, str) or not old_id.startswith("F") or len(old_id) < 2:
            raise ValueError("Invalid previous finding ID")
        if identity in earlier and earlier[identity] != old_id or old_id in used and used[old_id] != identity:
            raise ValueError("Ambiguous previous finding identity or ID")
        earlier[identity] = old_id
        used[old_id] = identity
    merged = {}
    for candidate in candidates:
        value = _validate_candidate(candidate, sources)
        identity = _identity(repository, value)
        if identity not in merged:
            finding_id = earlier.get(identity, _id(identity))
            if finding_id in used and used[finding_id] != identity:
                raise ValueError("Finding ID collision")
            used[finding_id] = identity
            perspective = value.pop("perspective", None)
            merged[identity] = {"id": finding_id, "repository": repository,
                                "state": "deferred", "basis": "source_only", **value,
                                "perspectives": [perspective] if perspective else []}
        else:
            row = merged[identity]
            if any(value[key] != row[key] for key in ("trigger", "taxonomy", "next_action")) or value["location"]["path"] != row["location"]["path"]:
                raise ValueError("Ambiguous evidence path, trigger, taxonomy, or verification action for one risk")
            if (value["location"]["line"], value["location"].get("end_line", 0)) < (row["location"]["line"], row["location"].get("end_line", 0)):
                row["location"] = value["location"]
            row["evidence_ids"] = sorted(set(row["evidence_ids"]) | set(value["evidence_ids"]))
            if "perspective" in value:
                row["perspectives"] = sorted(set(row["perspectives"]) | {value["perspective"]})
            if SEVERITIES.index(value["severity"]) < SEVERITIES.index(row["severity"]):
                row["severity"] = value["severity"]
    return sorted(merged.values(), key=lambda item: item["id"])


def compare(base, target, complete):
    """Compare admitted snapshots; absent entries resolve only with complete coverage.

    complete is the caller's explicit coverage declaration; it is not inferred from
    missing candidates. Severity increase is worsened, decrease is unchanged.
    """
    if not isinstance(complete, bool):
        raise ValueError("complete must be boolean")
    def indexed(rows):
        if not isinstance(rows, (list, tuple)):
            raise ValueError("Snapshot must be a sequence")
        result = {}
        for row in rows:
            if not isinstance(row, dict) or row.get("id") in result or row.get("severity") not in SEVERITIES or row.get("state") != "deferred":
                raise ValueError("Invalid or duplicate finding")
            result[row["id"]] = row
        return result
    before, after = indexed(base), indexed(target)
    statuses = []
    for finding_id in sorted(before.keys() | after.keys()):
        if finding_id not in before:
            status = "new" if complete else "unknown"
        elif finding_id not in after:
            status = "resolved" if complete else "unknown"
        elif any(before[finding_id].get(key) != after[finding_id].get(key)
                 for key in ("repository", "root_symbol", "mechanism", "condition", "impact")):
            status = "unknown"
        elif SEVERITIES.index(after[finding_id]["severity"]) < SEVERITIES.index(before[finding_id]["severity"]):
            status = "worsened"
        else:
            status = "unchanged"
        statuses.append({"id": finding_id, "status": status})
    return statuses


def priority_rows(findings, changes=None, actions=None):
    """Order the user-facing provisional risk rows without inferring user decisions."""
    changes = {} if changes is None else changes
    actions = {} if actions is None else actions
    if not isinstance(changes, dict) or not isinstance(actions, dict):
        raise ValueError("changes and actions must be mappings")
    change_order = ("worsened", "new", "unknown", "unchanged", "resolved")
    evidence_order = ("confirmed", "deferred", "rejected")
    allowed_actions = {"verify", "fix", "accept_risk", "dismiss"}
    rows = []
    ids = set()
    for finding in findings:
        if not isinstance(finding, dict) or finding.get("severity") not in SEVERITIES or not isinstance(finding.get("id"), str) or finding["id"] in ids:
            raise ValueError("Invalid or duplicate finding")
        finding_id = finding["id"]
        ids.add(finding_id)
        change = changes.get(finding_id, "unknown")
        state = finding.get("state")
        if change not in change_order or state not in evidence_order:
            raise ValueError("Invalid change or evidence status")
        next_action = finding.get("next_action")
        if not isinstance(next_action, dict) or type(next_action.get("time_minutes")) is not int or next_action["time_minutes"] <= 0:
            raise ValueError("Invalid next action estimate")
        action = actions.get(finding_id)
        if action is not None and action not in allowed_actions:
            raise ValueError("Invalid user action")
        if change == "resolved" or state == "rejected":
            continue
        rows.append({"id": finding_id, "title": finding["root_symbol"],
                     "severity": finding["severity"], "taxonomy": finding["taxonomy"],
                     "location": finding["location"], "impact": finding["impact"],
                     "condition": finding["condition"], "change_status": change,
                     "evidence_status": state, "evidence_ids": finding["evidence_ids"],
                     "next_action": next_action, "user_action": action})
    if (set(actions) | set(changes)) - ids:
        raise ValueError("Status or action refers to unknown finding")
    return sorted(rows, key=lambda row: (
        SEVERITIES.index(row["severity"]), change_order.index(row["change_status"]),
        evidence_order.index(row["evidence_status"]), row["next_action"]["time_minutes"], row["id"]))
