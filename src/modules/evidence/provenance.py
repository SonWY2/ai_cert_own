"""Immutable, source-only provenance for accepted static scan results."""

import hashlib
import json
import re
from pathlib import Path

SCHEMA_VERSION = "evidence-contract-v1"
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


def _canonical(record: dict) -> bytes:
    return json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _hash(record: dict) -> str:
    return hashlib.sha256(_canonical({key: value for key, value in record.items()
                                      if key != "content_hash"})).hexdigest()


def _seal(record: dict) -> dict:
    record["content_hash"] = _hash(record)
    return record


def _digest(value: object, name: str, pattern: re.Pattern = _HEX) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f"Invalid {name}")
    return value


def _records(repository: str, scan_result: dict) -> tuple[dict, list[dict]]:
    if not isinstance(repository, str) or not repository:
        raise ValueError("Repository must be a nonempty string")
    if not isinstance(scan_result, dict):
        raise ValueError("Scan result must be an object")
    commit = _digest(scan_result.get("commit"), "commit", _OID)
    parser = scan_result.get("python_parser")
    files = scan_result.get("files")
    if not isinstance(parser, str) or not parser or not isinstance(files, list) or not files:
        raise ValueError("Accepted scan requires a parser and nonempty files list")
    paths = set()
    sources = []
    for file in files:
        if not isinstance(file, dict):
            raise ValueError("Scan file must be an object")
        path = file.get("path")
        if (not isinstance(path, str) or not path or path.startswith("/") or
                any(part in ("", ".", "..") for part in path.split("/")) or path in paths):
            raise ValueError("Invalid or duplicate scan path")
        paths.add(path)
        source = {"path": path,
                  "source_sha256": _digest(file.get("source_sha256"), "source SHA"),
                  "blob_oid": _digest(file.get("blob_oid"), "blob OID", _OID)}
        if "parse_error" in file:
            if not isinstance(file["parse_error"], str):
                raise ValueError("Invalid parse error")
            source["parse_error"] = file["parse_error"]
        else:
            for key in ("symbols", "symbol_table_names", "imports", "flags"):
                if key not in file:
                    raise ValueError(f"Missing scan field: {key}")
        sources.append(source)
    sources.sort(key=lambda item: item["path"])
    snapshot = {"repository": repository, "commit": commit, "python_parser": parser,
                "sources": sources}
    run_id = hashlib.sha256(_canonical(snapshot)).hexdigest()
    run = _seal({"id": run_id, "schema_version": SCHEMA_VERSION, "repository": repository,
                 "commit": commit, "python_parser": parser, "stage": "source_scanned",
                 "source_count": len(sources)})
    evidence = []
    for source in sources:
        evidence_id = hashlib.sha256(_canonical({"run_id": run_id, **source})).hexdigest()
        evidence.append(_seal({"id": evidence_id, "schema_version": SCHEMA_VERSION,
                               "kind": "source", "run_id": run_id, "commit": commit,
                               **source}))
    return run, evidence


def _bytes(record: dict) -> bytes:
    return _canonical(record) + b"\n"


def write_source_run(output_root: Path, repository: str, scan_result: dict) -> Path:
    """Write a deterministic source-only bundle under output_root/runs/<run id>."""
    run, evidence = _records(repository, scan_result)
    bundle = Path(output_root) / "runs" / run["id"]
    payloads = {"run.json": _bytes(run),
                "evidence.jsonl": b"".join(_bytes(record) for record in evidence)}
    bundle.mkdir(parents=True, exist_ok=True)
    for name, data in payloads.items():
        path = bundle / name
        if path.exists() and path.read_bytes() != data:
            raise FileExistsError(f"Existing provenance differs: {path}")
    for name, data in payloads.items():
        path = bundle / name
        try:
            with path.open("xb") as stream:
                stream.write(data)
        except FileExistsError:
            if path.read_bytes() != data:
                raise FileExistsError(f"Existing provenance differs: {path}") from None
    return bundle


def verify_source_run(bundle: Path) -> dict:
    """Verify stored source provenance, returning run and evidence records on success."""
    bundle = Path(bundle)
    run_data = (bundle / "run.json").read_bytes()
    evidence_data = (bundle / "evidence.jsonl").read_bytes()
    try:
        run = json.loads(run_data)
        evidence = [json.loads(line) for line in evidence_data.splitlines()]
        if not isinstance(run, dict) or not evidence or not all(isinstance(e, dict) for e in evidence):
            raise ValueError("Invalid provenance records")
        if run_data != _bytes(run) or evidence_data != b"".join(_bytes(e) for e in evidence):
            raise ValueError("Noncanonical provenance encoding")
        for record in [run, *evidence]:
            if record.get("schema_version") != SCHEMA_VERSION or record.get("content_hash") != _hash(record):
                raise ValueError("Provenance hash or schema mismatch")
        if run.get("stage") != "source_scanned" or run.get("source_count") != len(evidence):
            raise ValueError("Source run metadata mismatch")
        if bundle.name != run.get("id"):
            raise ValueError("Bundle name does not match run ID")
        sources = []
        for item in evidence:
            if item.get("kind") != "source" or item.get("run_id") != run["id"] or item.get("commit") != run["commit"]:
                raise ValueError("Source evidence linkage mismatch")
            sources.append({key: item[key] for key in ("path", "source_sha256", "blob_oid")})
            if "parse_error" in item:
                sources[-1]["parse_error"] = item["parse_error"]
        reconstructed = {"commit": run["commit"], "python_parser": run["python_parser"],
                         "files": [{**item, **({} if "parse_error" in item else
                                   {"symbols": [], "symbol_table_names": [], "imports": [], "flags": {}})}
                                   for item in sources]}
        expected_run, expected_evidence = _records(run["repository"], reconstructed)
        if run != expected_run or evidence != expected_evidence:
            raise ValueError("Source provenance IDs or records mismatch")
    except (KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError("Invalid source provenance") from error
    return {"run": run, "evidence": evidence}
