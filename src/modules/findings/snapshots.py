"""Owner-held, immutable provisional reviews linked to authenticated Git source."""

import hashlib
import json
import os
import stat
from pathlib import Path

from modules.evidence.authenticity import verify_git_source
from modules.findings.locations import validate_locations
from modules.findings.admission import SEVERITIES, TAXONOMIES, _id, _identity

_STAGE = "provisional_hypotheses"
_FIELDS = frozenset({"id", "content_hash", "stage", "source_run_id", "commit", "repository", "findings", "scope", "priority_rows"})


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _owner_path(path, repository, bundle=None):
    path = Path(path)
    directory = path.parent.resolve(strict=True)
    repo = Path(repository).resolve(strict=True)
    if directory == repo or directory.is_relative_to(repo):
        raise ValueError("Snapshot must be outside the source repository")
    if bundle is not None:
        source = Path(bundle).resolve(strict=True)
        if directory == source or directory.is_relative_to(source):
            raise ValueError("Snapshot must be outside the source bundle")
    info = directory.stat()
    if not directory.is_dir() or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("Snapshot directory must be owner-controlled")
    return directory / path.name


def _findings(rows, verified):
    if not isinstance(rows, list):
        raise ValueError("Findings must be a list")
    run = verified["run"]
    evidence = {entry["id"]: entry["path"] for entry in verified["evidence"]}
    identities = set()
    ids = set()
    for row in rows:
        if not isinstance(row, dict) or row.get("repository") != run["repository"] or row.get("state") != "deferred" or row.get("basis") != "source_only":
            raise ValueError("Prior finding must be deferred source-only evidence")
        for field in ("root_symbol", "mechanism", "condition", "impact", "trigger"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError("Invalid finding identity or claim")
        identity = _identity(run["repository"], row)
        finding_id = row.get("id")
        if finding_id != _id(identity) or finding_id in ids or identity in identities:
            raise ValueError("Invalid or duplicate finding ID or identity")
        ids.add(finding_id)
        identities.add(identity)
        location = row.get("location")
        if not isinstance(location, dict) or not isinstance(location.get("path"), str) or type(location.get("line")) is not int or location["line"] < 1:
            raise ValueError("Invalid finding location")
        if "end_line" in location and (type(location["end_line"]) is not int or location["end_line"] < location["line"]):
            raise ValueError("Invalid finding end line")
        citations = row.get("evidence_ids")
        if not isinstance(citations, list) or not citations or len(citations) != len(set(citations)) or any(not isinstance(item, str) or evidence.get(item) != location["path"] for item in citations):
            raise ValueError("Finding references missing source evidence")
        if row.get("taxonomy") not in TAXONOMIES or row.get("severity") not in SEVERITIES:
            raise ValueError("Invalid finding taxonomy or severity")
        action = row.get("next_action")
        if not isinstance(action, dict) or set(action) != {"action", "oracle", "time_minutes"} or type(action["time_minutes"]) is not int or action["time_minutes"] <= 0 or any(not isinstance(action[key], str) or not action[key].strip() for key in ("action", "oracle")):
            raise ValueError("Invalid finding verification action")
    validate_locations(verified, rows)
    return ids


def _risk_rows(rows, findings):
    if not isinstance(rows, list):
        raise ValueError("Priority rows must be a list")
    by_id = {row["id"]: row for row in findings}
    used = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or row["id"] not in by_id or row["id"] in used:
            raise ValueError("Invalid or duplicate risk row")
        used.add(row["id"])
        finding = by_id[row["id"]]
        if row.get("evidence_status") != "deferred" or row.get("change_status") not in ("new", "worsened", "unknown", "unchanged"):
            raise ValueError("Risk row must remain deferred")
        if row.get("user_action") not in (None, "verify", "fix", "accept_risk", "dismiss"):
            raise ValueError("Invalid owner action")
        for key, source_key in (("title", "root_symbol"), ("severity", "severity"), ("taxonomy", "taxonomy"), ("location", "location"), ("impact", "impact"), ("condition", "condition"), ("evidence_ids", "evidence_ids"), ("next_action", "next_action")):
            if row.get(key) != finding[source_key]:
                raise ValueError("Risk row differs from cited finding")


def save_snapshot(review_output, verified_source, destination_path, source_bundle=None):
    """Write once in an existing owner-only directory; return the sealed record."""
    if not isinstance(verified_source, dict) or not isinstance(verified_source.get("run"), dict):
        raise ValueError("Verified source is required")
    run = verified_source["run"]
    if not isinstance(review_output, dict) or review_output.get("stage", _STAGE) != _STAGE:
        raise ValueError("Only provisional reviews can be saved")
    for key, value in (("source_run_id", run["id"]), ("repository", run["repository"]), ("commit", run["commit"])):
        if key in review_output and review_output[key] != value:
            raise ValueError("Review source mismatch")
    findings = review_output.get("findings")
    _findings(findings, verified_source)
    record = {"stage": _STAGE, "source_run_id": run["id"], "commit": run["commit"], "repository": run["repository"], "findings": findings}
    for key in ("scope", "priority_rows"):
        if key in review_output:
            record[key] = review_output[key]
    if "priority_rows" in record:
        _risk_rows(record["priority_rows"], findings)
    record["id"] = _digest(record)
    record["content_hash"] = _digest(record)
    path = _owner_path(destination_path, run["repository"], source_bundle)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(_canonical(record) + b"\n")
    return record


def load_previous(snapshot_path, previous_source_bundle, expected_repository):
    """Authenticate a prior Git source and return its sealed snapshot record."""
    verified = verify_git_source(Path(previous_source_bundle))
    run = verified["run"]
    if run["repository"] != expected_repository:
        raise ValueError("Prior repository mismatch")
    path = _owner_path(snapshot_path, expected_repository, previous_source_bundle)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_nlink != 1:
            raise ValueError("Snapshot must be an owner-only regular file")
        raw = source.read()
    try:
        record = json.loads(raw)
        if not isinstance(record, dict) or not _FIELDS.issuperset(record) or not {"id", "content_hash", "stage", "source_run_id", "commit", "repository", "findings"}.issubset(record):
            raise ValueError("Invalid snapshot schema")
        if raw != _canonical(record) + b"\n" or record["content_hash"] != _digest({key: value for key, value in record.items() if key != "content_hash"}) or record["id"] != _digest({key: value for key, value in record.items() if key not in ("id", "content_hash")}):
            raise ValueError("Noncanonical or altered snapshot")
        if record["stage"] != _STAGE or any(record[key] != run[source] for key, source in (("source_run_id", "id"), ("commit", "commit"), ("repository", "repository"))):
            raise ValueError("Snapshot does not match authenticated prior run")
        _findings(record["findings"], verified)
        if "priority_rows" in record:
            _risk_rows(record["priority_rows"], record["findings"])
    except (TypeError, KeyError, UnicodeDecodeError, json.JSONDecodeError, OverflowError) as error:
        raise ValueError("Invalid provisional snapshot") from error
    return record
