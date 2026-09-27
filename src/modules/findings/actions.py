"""Owner decisions stored outside the immutable source-stage provenance bundle."""

import fcntl
import hashlib
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

from modules.evidence.provenance import SCHEMA_VERSION, verify_source_run

ACTIONS = frozenset({"verify", "fix", "accept_risk", "dismiss"})
_FIELDS = frozenset({"id", "schema_version", "content_hash", "run_id", "finding_id", "action", "timestamp"})


def _canonical(record):
    return json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _hash(record):
    return hashlib.sha256(_canonical({key: value for key, value in record.items()
                                      if key != "content_hash"})).hexdigest()


def _context(source_bundle, admitted_findings, destination):
    bundle = Path(source_bundle).resolve(strict=True)
    verified = verify_source_run(bundle)
    directory = Path(destination).resolve(strict=True)
    if directory == bundle or directory in bundle.parents or bundle in directory.parents:
        raise ValueError("Owner actions must be outside the source bundle")
    repository = Path(verified["run"]["repository"])
    if repository.is_absolute() and directory.is_relative_to(repository.resolve()):
        raise ValueError("Owner actions must be outside the source repository")
    stat = directory.stat()
    if not directory.is_dir() or stat.st_uid != os.getuid() or stat.st_mode & 0o077:
        raise ValueError("Action directory must be owner-controlled (mode 0700)")
    if not isinstance(admitted_findings, (list, tuple)):
        raise ValueError("Admitted findings must be a sequence")
    evidence = {record["id"]: record["path"] for record in verified["evidence"]}
    findings = {}
    for row in admitted_findings:
        if not isinstance(row, dict) or row.get("repository") != verified["run"]["repository"] or row.get("state") != "deferred" or row.get("basis") != "source_only":
            raise ValueError("Finding must be source-only, deferred, and in this repository")
        location = row.get("location")
        ids = row.get("evidence_ids")
        finding_id = row.get("id")
        if (not isinstance(finding_id, str) or not finding_id.startswith("F") or
                finding_id in findings or not isinstance(location, dict) or
                not isinstance(location.get("path"), str) or
                not isinstance(ids, list) or not ids or
                any(not isinstance(item, str) or evidence.get(item) != location["path"] for item in ids)):
            raise ValueError("Finding is not linked to this source run")
        findings[finding_id] = row
    return verified["run"]["id"], findings, directory / (verified["run"]["id"] + ".actions.jsonl")


def _read(stream, run_id, findings):
    raw = stream.read()
    if raw and not raw.endswith(b"\n"):
        raise ValueError("Truncated action history")
    latest = {}
    history = []
    for line in raw.splitlines(keepends=True):
        try:
            record = json.loads(line)
            if (not isinstance(record, dict) or set(record) != _FIELDS or
                    line != _canonical(record) + b"\n" or
                    record["schema_version"] != SCHEMA_VERSION or
                    record["run_id"] != run_id or
                    not isinstance(record["finding_id"], str) or
                    not record["finding_id"].startswith("F") or
                    record["action"] not in ACTIONS or
                    record["content_hash"] != _hash(record) or
                    record["id"] != hashlib.sha256(_canonical({
                        key: value for key, value in record.items()
                        if key not in ("id", "content_hash")})).hexdigest() or
                    not isinstance(record["timestamp"], str)):
                raise ValueError("Invalid action history")
            datetime.fromisoformat(record["timestamp"])
        except (TypeError, KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid action history") from exc
        history.append(record)
        if record["finding_id"] in findings:
            latest[record["finding_id"]] = record["action"]
    return latest, history


def _open(path, create=False):
    flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW if create else os.O_RDONLY | os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    stream = os.fdopen(descriptor, "r+b" if create else "rb")
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid() or metadata.st_mode & 0o077 or metadata.st_nlink != 1:
        stream.close()
        raise ValueError("Action log must be owner-only regular file")
    return stream


def append_action(source_bundle, admitted_findings, finding_id, action, destination,
                  explicit_owner_confirmation):
    """Append a confirmed owner decision; never change evidence or finding status."""
    if explicit_owner_confirmation is not True:
        raise ValueError("Explicit owner confirmation is required")
    if action not in ACTIONS:
        raise ValueError("Invalid user action")
    run_id, findings, path = _context(source_bundle, admitted_findings, destination)
    if finding_id not in findings:
        raise ValueError("Unknown finding ID")
    with _open(path, create=True) as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        _read(stream, run_id, findings)
        record = {"schema_version": SCHEMA_VERSION, "run_id": run_id,
                  "finding_id": finding_id, "action": action,
                  "timestamp": datetime.now(timezone.utc).isoformat()}
        record["id"] = _hash(record)
        record["content_hash"] = _hash(record)
        stream.seek(0, os.SEEK_END)
        stream.write(_canonical(record) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    return record


def read_actions(source_bundle, admitted_findings, destination):
    """Return latest explicit actions keyed by finding ID; absent IDs have no action."""
    run_id, findings, path = _context(source_bundle, admitted_findings, destination)
    if not os.path.lexists(path):
        return {}
    with _open(path) as stream:
        fcntl.flock(stream, fcntl.LOCK_SH)
        return _read(stream, run_id, findings)[0]


def read_action_history(source_bundle, admitted_findings, destination):
    """Return validated owner actions for this exact source run and finding set."""
    run_id, findings, path = _context(source_bundle, admitted_findings, destination)
    if not os.path.lexists(path):
        return []
    with _open(path) as stream:
        fcntl.flock(stream, fcntl.LOCK_SH)
        _, history = _read(stream, run_id, findings)
    return [record for record in history if record["finding_id"] in findings]
