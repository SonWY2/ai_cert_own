#!/usr/bin/env python3
"""Stage a public text file through GitHub Issue comments and materialize it in Actions."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

MANIFEST_MARKER = "issue-file-manifest-v1"
CHUNK_MARKER = "issue-file-chunk-v1"
ALLOWED_PREFIX = ".wayfinder/ai-a-plus-code-health/research/"
MANIFEST_PATTERN = re.compile(
    rf"<!-- {MANIFEST_MARKER}\n(?P<metadata>.*?)\n-->", re.DOTALL
)
CHUNK_PATTERN = re.compile(rf"<!-- {CHUNK_MARKER}\n(?P<metadata>.*?)\n-->", re.DOTALL)
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def issue_body(marker: str, metadata: dict[str, Any], payload: str = "") -> str:
    return f"<!-- {marker}\n{json.dumps(metadata, sort_keys=True, separators=(',', ':'))}\n-->\n{payload}"


def require_sha256(value: object, field: str) -> str:
    if not isinstance(value, str) or not SHA256_PATTERN.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return value


def require_allowed_path(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("manifest path must be a string")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("manifest path must stay inside the repository")
    normalized = path.as_posix()
    if not normalized.startswith(ALLOWED_PREFIX) or not normalized.endswith(".md"):
        raise ValueError(f"manifest path must match {ALLOWED_PREFIX}*.md")
    return normalized


def gh_api_json(repo: str, method: str, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".json", delete=False) as handle:
        payload_path = Path(handle.name)
        handle.write(json_bytes(payload))
    try:
        command = [
            "gh",
            "api",
            "--hostname",
            "github.com",
            "--method",
            method,
            f"repos/{repo}/{endpoint}",
            "--input",
            str(payload_path),
        ]
        result = subprocess.run(command, check=False, text=True, capture_output=True)
    finally:
        payload_path.unlink(missing_ok=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "gh api failed")
    return json.loads(result.stdout)


def stage(arguments: argparse.Namespace) -> None:
    source = Path(arguments.path).resolve()
    root = Path.cwd().resolve()
    try:
        relative_path = source.relative_to(root).as_posix()
    except ValueError as error:
        raise ValueError("path must be inside the current repository") from error
    require_allowed_path(relative_path)
    content = source.read_bytes()
    if not content:
        raise ValueError("empty files are not staged through Issue comments")
    if arguments.chunk_bytes <= 0:
        raise ValueError("chunk bytes must be positive")

    chunks = [content[offset : offset + arguments.chunk_bytes] for offset in range(0, len(content), arguments.chunk_bytes)]
    manifest = {
        "version": 1,
        "path": relative_path,
        "size": len(content),
        "sha256": sha256(content),
        "chunks": len(chunks),
    }
    issue_payload = {
        "title": arguments.title or f"stage: {relative_path}",
        "body": issue_body(MANIFEST_MARKER, manifest),
    }
    comment_payloads = []
    for index, chunk in enumerate(chunks):
        metadata = {"index": index, "sha256": sha256(chunk)}
        encoded = base64.b64encode(chunk).decode("ascii")
        comment_payloads.append({"body": issue_body(CHUNK_MARKER, metadata, encoded)})

    envelopes = [issue_payload, *comment_payloads]
    request_sizes = [len(json_bytes(payload)) for payload in envelopes]
    over_budget = [size for size in request_sizes if size > arguments.request_budget]
    if over_budget:
        raise ValueError(
            f"request budget exceeded: largest={max(over_budget)}, budget={arguments.request_budget}; reduce --chunk-bytes"
        )

    summary = {
        "path": relative_path,
        "source_bytes": len(content),
        "source_sha256": manifest["sha256"],
        "chunks": len(chunks),
        "largest_request_bytes": max(request_sizes),
        "request_budget": arguments.request_budget,
    }
    if arguments.dry_run:
        print(json.dumps(summary, sort_keys=True))
        return

    issue = gh_api_json(arguments.repo, "POST", "issues", issue_payload)
    issue_number = issue["number"]
    for payload in comment_payloads:
        gh_api_json(arguments.repo, "POST", f"issues/{issue_number}/comments", payload)
    summary["issue_number"] = issue_number
    summary["issue_url"] = issue["html_url"]
    print(json.dumps(summary, sort_keys=True))


def github_request(url: str, token: str, method: str = "GET", payload: dict[str, Any] | None = None) -> tuple[Any, str]:
    data = json_bytes(payload) if payload is not None else None
    request = Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "issue-file-materializer",
            "X-GitHub-Api-Version": "2026-03-10",
        },
    )
    try:
        with urlopen(request) as response:
            body = response.read()
            return (json.loads(body) if body else None), response.headers.get("Link", "")
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {method} {url} failed: HTTP {error.code}: {detail}") from error


def next_link(link_header: str) -> str | None:
    match = re.search(r'<([^>]+)>; rel="next"', link_header)
    return match.group(1) if match else None


def marker_metadata(pattern: re.Pattern[str], body: object, kind: str) -> tuple[dict[str, Any], str] | None:
    if not isinstance(body, str):
        raise ValueError(f"{kind} body is missing")
    match = pattern.search(body)
    if not match:
        return None
    try:
        metadata = json.loads(match.group("metadata"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{kind} metadata is invalid JSON") from error
    if not isinstance(metadata, dict):
        raise ValueError(f"{kind} metadata must be an object")
    return metadata, body[match.end() :].strip()


def materialize(arguments: argparse.Namespace) -> None:
    repository = arguments.repo
    owner = repository.split("/", 1)[0]
    if "/" not in repository or not arguments.issue.isdigit() or int(arguments.issue) <= 0:
        raise ValueError("repository must be owner/repo and issue must be a positive integer")
    api_root = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    base_url = f"{api_root}/repos/{repository}/issues/{arguments.issue}"
    issue, _ = github_request(base_url, arguments.token)
    if issue.get("user", {}).get("login") != owner:
        raise ValueError("only the repository owner may supply the staging manifest")
    parsed_manifest = marker_metadata(MANIFEST_PATTERN, issue.get("body"), "manifest")
    if parsed_manifest is None:
        raise ValueError("staging manifest marker is missing")
    manifest, trailing = parsed_manifest
    if trailing:
        raise ValueError("manifest issue body must not contain unstructured trailing content")
    if manifest.get("version") != 1:
        raise ValueError("unsupported manifest version")
    target_path = require_allowed_path(manifest.get("path"))
    if not isinstance(manifest.get("size"), int) or manifest["size"] <= 0:
        raise ValueError("manifest size must be a positive integer")
    expected_sha = require_sha256(manifest.get("sha256"), "manifest sha256")
    expected_chunks = manifest.get("chunks")
    if not isinstance(expected_chunks, int) or expected_chunks <= 0 or expected_chunks > 100:
        raise ValueError("manifest chunks must be between 1 and 100")

    comments: list[dict[str, Any]] = []
    comments_url = f"{base_url}/comments?per_page=100"
    while comments_url:
        page, link = github_request(comments_url, arguments.token)
        if not isinstance(page, list):
            raise ValueError("issue comments response is invalid")
        comments.extend(page)
        comments_url = next_link(link)

    chunks: dict[int, bytes] = {}
    for comment in comments:
        parsed_chunk = marker_metadata(CHUNK_PATTERN, comment.get("body"), "chunk")
        if parsed_chunk is None:
            continue
        if comment.get("user", {}).get("login") != owner:
            raise ValueError("only the repository owner may supply staged chunks")
        metadata, encoded = parsed_chunk
        index = metadata.get("index")
        if not isinstance(index, int) or index < 0 or index >= expected_chunks:
            raise ValueError("chunk index is outside the manifest range")
        if index in chunks:
            raise ValueError(f"duplicate chunk index {index}")
        expected_chunk_sha = require_sha256(metadata.get("sha256"), "chunk sha256")
        try:
            chunk = base64.b64decode(encoded, validate=True)
        except ValueError as error:
            raise ValueError(f"chunk {index} is not valid Base64") from error
        if sha256(chunk) != expected_chunk_sha:
            raise ValueError(f"chunk {index} SHA-256 mismatch")
        chunks[index] = chunk

    if set(chunks) != set(range(expected_chunks)):
        raise ValueError("staged chunks are incomplete")
    content = b"".join(chunks[index] for index in range(expected_chunks))
    if len(content) != manifest["size"] or sha256(content) != expected_sha:
        raise ValueError("reassembled file does not match the manifest")

    workspace = Path(arguments.workspace).resolve()
    destination = (workspace / target_path).resolve()
    try:
        destination.relative_to(workspace)
    except ValueError as error:
        raise ValueError("target path escaped the workspace") from error
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(destination)
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with Path(output_path).open("a", encoding="utf-8") as output:
            output.write(f"path={target_path}\n")
    print(json.dumps({"path": target_path, "size": len(content), "sha256": expected_sha}, sort_keys=True))


def close_issue(arguments: argparse.Namespace) -> None:
    if not arguments.issue.isdigit() or int(arguments.issue) <= 0:
        raise ValueError("issue must be a positive integer")
    api_root = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    base_url = f"{api_root}/repos/{arguments.repo}/issues/{arguments.issue}"
    github_request(base_url, arguments.token, "PATCH", {"state": "closed"})
    github_request(f"{base_url}/lock", arguments.token, "PUT")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)

    stage_parser = commands.add_parser("stage", help="create an Issue and staged chunk comments")
    stage_parser.add_argument("--repo", required=True)
    stage_parser.add_argument("--path", required=True)
    stage_parser.add_argument("--title")
    stage_parser.add_argument("--chunk-bytes", type=int, default=24_000)
    stage_parser.add_argument("--request-budget", type=int, default=35_000)
    stage_parser.add_argument("--dry-run", action="store_true")
    stage_parser.set_defaults(handler=stage)

    materialize_parser = commands.add_parser("materialize", help="reassemble an Issue into the workspace")
    materialize_parser.add_argument("--repo", required=True)
    materialize_parser.add_argument("--issue", required=True)
    materialize_parser.add_argument("--token", required=True)
    materialize_parser.add_argument("--workspace", required=True)
    materialize_parser.set_defaults(handler=materialize)

    close_parser = commands.add_parser("close", help="close and lock a completed staging Issue")
    close_parser.add_argument("--repo", required=True)
    close_parser.add_argument("--issue", required=True)
    close_parser.add_argument("--token", required=True)
    close_parser.set_defaults(handler=close_issue)
    return root


def main() -> int:
    try:
        arguments = parser().parse_args()
        arguments.handler(arguments)
    except (ValueError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
