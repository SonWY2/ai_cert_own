"""Validate bounded RunManifest declarations and hash their canonical contents."""

import hashlib
import json
import os
import re
from urllib.parse import urlsplit

SCHEMA_VERSION = "run-manifest-v3"
LOCAL_OAUTH_ENDPOINT = "http://127.0.0.1:10531/v1/responses"
ALLOWED_TOOLS = frozenset({"python", "pytest", "unittest", "coverage", "cprofile"})
_SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")


class PolicyError(ValueError):
    """Manifest violates the declared boundary."""


def _fields(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise PolicyError(f"{label} requires exactly {', '.join(keys)}")


def _sha(value, label):
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise PolicyError(f"{label} must be a full lowercase Git commit SHA")


def _positive(value, label):
    if type(value) is not int or value <= 0:
        raise PolicyError(f"{label} must be a positive integer")


def _strings(value, label, *, nonempty=True):
    if not isinstance(value, list) or (nonempty and not value):
        raise PolicyError(f"{label} must be a {'nonempty ' if nonempty else ''}list")
    if any(not isinstance(item, str) or not item or "\x00" in item for item in value):
        raise PolicyError(f"{label} contains an invalid string")


def _absolute(path, label):
    if not isinstance(path, str) or not path.startswith("/") or "\x00" in path:
        raise PolicyError(f"{label} must be an absolute path")
    if path != os.path.normpath(path) or any(part == ".." for part in path.split("/")):
        raise PolicyError(f"{label} must be normalized")


def _inside(path, root):
    return path == root or path.startswith(root.rstrip("/") + "/")


def _validate_analysis(analysis, *, model_enabled):
    if not model_enabled:
        if analysis is not None:
            raise PolicyError("analysis must be null without a model endpoint")
        return
    _fields(analysis, ("mode", "roles", "scope", "symbol", "base_sha",
                       "context_policy", "contexts"), "analysis")
    mode = analysis["mode"]
    if mode not in ("five", "boundary", "generic", "single", "plain"):
        raise PolicyError("unsupported analysis mode")
    roles = ["structure", "correctness", "performance", "concurrency", "tests"]
    expected_roles = roles + ["assumptions"] if mode == "boundary" else (
        roles + ["generic"] if mode == "generic" else
        ["all"] if mode in ("single", "plain") else roles)
    if analysis["roles"] != expected_roles:
        raise PolicyError("analysis roles must exactly match the ordered mode roles")
    scope = analysis["scope"]
    if scope not in ("symbol", "full", "impact"):
        raise PolicyError("unsupported analysis scope")
    symbol = analysis["symbol"]
    if scope == "symbol":
        if not isinstance(symbol, str) or not symbol.strip() or "\x00" in symbol:
            raise PolicyError("symbol scope requires a nonempty symbol")
    elif symbol is not None:
        raise PolicyError("analysis symbol must be null outside symbol scope")
    base_sha = analysis["base_sha"]
    if base_sha is not None and (
            not isinstance(base_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", base_sha)):
        raise PolicyError("analysis base_sha must be a full lowercase 40-hex commit SHA")
    if scope == "symbol" and base_sha is not None:
        raise PolicyError("symbol scope cannot declare a comparison base")
    if scope == "impact" and base_sha is None:
        raise PolicyError("impact scope requires base_sha")
    if mode == "plain" and scope != "symbol" or mode == "single" and scope == "impact":
        raise PolicyError("baseline mode does not support the selected scope")
    if analysis["context_policy"] not in (
            "git-ast-context-v1", "git-ast-outline-v1", "git-ast-cards-v1"):
        raise PolicyError("unsupported analysis context policy")
    if mode in ("single", "plain") and analysis["context_policy"] != "git-ast-context-v1":
        raise PolicyError("single baselines do not receive graph review units")
    contexts = analysis["contexts"]
    if not isinstance(contexts, list):
        raise PolicyError("analysis contexts must be an ordered list")
    batch = scope != "symbol" and mode in ("five", "boundary", "generic")
    expected_scope = "symbol:" + symbol if scope == "symbol" else "full"
    seen = set()
    for context in contexts:
        _fields(context, ("scope_id", "sha256"), "analysis context")
        scope_id = context["scope_id"]
        if not isinstance(scope_id, str) or not scope_id or "\x00" in scope_id:
            raise PolicyError("invalid analysis context scope_id")
        if scope_id in seen:
            raise PolicyError("duplicate analysis context scope_id")
        seen.add(scope_id)
        if batch:
            path = scope_id.removeprefix("module:")
            if (not scope_id.startswith("module:") or not path or path.startswith("/")
                    or any(part in ("", ".", "..") for part in path.split("/"))):
                raise PolicyError("batch context requires a normalized module path")
        elif scope_id != expected_scope:
            raise PolicyError("analysis context differs from selected scope")
        digest = context["sha256"]
        if digest is None and batch:
            continue
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise PolicyError("analysis context requires a SHA-256 digest")
    if not batch and len(contexts) != 1:
        raise PolicyError("selected symbol or full baseline requires exactly one context")


def validate_manifest(manifest):
    """Reject undeclared fields, unsafe capabilities and incomplete resource bounds.

    The declaration cannot prove command side effects or implement sandboxing.
    """
    _fields(manifest, ("schema_version", "snapshot_sha", "image_digest", "nodes", "tools",
                       "limits", "network", "writable_paths", "model", "analysis"), "manifest")
    if manifest["schema_version"] != SCHEMA_VERSION:
        raise PolicyError("unsupported manifest version")
    _sha(manifest["snapshot_sha"], "snapshot_sha")
    image = manifest["image_digest"]
    if not isinstance(image, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise PolicyError("image_digest must be a pinned sha256 digest")
    _strings(manifest["tools"], "tools", nonempty=False)
    if any(type(tool) is not str for tool in manifest["tools"]):
        raise PolicyError("tools must be strings")
    if len(set(manifest["tools"])) != len(manifest["tools"]) or not set(manifest["tools"]) <= ALLOWED_TOOLS:
        raise PolicyError("duplicate or prohibited tool")
    _fields(manifest["limits"], ("wall_seconds", "cpu_seconds", "memory_bytes",
                                  "tokens", "tool_seconds", "per_node"), "limits")
    limits = manifest["limits"]
    for key in ("wall_seconds", "cpu_seconds", "memory_bytes", "tokens", "tool_seconds"):
        _positive(limits[key], key)
    if type(limits["per_node"]) is not dict or (manifest["nodes"] and not limits["per_node"]):
        raise PolicyError("per_node must declare each node's bounds")
    for node_id, bounds in limits["per_node"].items():
        if not isinstance(node_id, str) or not _ID.fullmatch(node_id):
            raise PolicyError("invalid per_node identifier")
        _fields(bounds, ("wall_seconds", "cpu_seconds", "memory_bytes", "tokens", "tool_seconds"), "node limits")
        for key, amount in bounds.items():
            _positive(amount, f"{node_id}.{key}")
            if amount > limits[key]:
                raise PolicyError(f"{node_id}.{key} exceeds total limit")
    _fields(manifest["network"], ("dependency", "model", "workload"), "network")
    if any(type(value) is not bool for value in manifest["network"].values()):
        raise PolicyError("network permissions must be booleans")
    _strings(manifest["writable_paths"], "writable_paths")
    writable = manifest["writable_paths"]
    for path in writable:
        _absolute(path, "writable path")
        if not any(_inside(path, root) and path != root for root in ("/tmp", "/work")):
            raise PolicyError("writable paths must be isolated under /tmp or /work, not source")
    if len(set(writable)) != len(writable):
        raise PolicyError("duplicate writable path")
    _fields(manifest["model"], ("endpoint", "name_version", "prompt_sha256", "transmitted_data"), "model")
    model = manifest["model"]
    if model["endpoint"] is None:
        if (model["name_version"] is not None or model["prompt_sha256"] is not None
                or model["transmitted_data"] != [] or manifest["network"]["model"]):
            raise PolicyError("model network and data require a declared endpoint and version")
    else:
        endpoint = model["endpoint"]
        if not isinstance(endpoint, str):
            raise PolicyError("model endpoint must be HTTPS or the pinned loopback OAuth endpoint")
        try:
            parsed = urlsplit(endpoint)
            parsed.port
        except ValueError as error:
            raise PolicyError("invalid model endpoint") from error
        https_endpoint = (parsed.scheme == "https" and parsed.hostname
                          and not (parsed.username or parsed.password or parsed.query or parsed.fragment))
        if (not https_endpoint and endpoint != LOCAL_OAUTH_ENDPOINT) or not manifest["network"]["model"]:
            raise PolicyError("model endpoint requires declared network permission and HTTPS or pinned loopback")
        if not isinstance(model["name_version"], str) or not model["name_version"].strip():
            raise PolicyError("model name and version must be declared")
        if not isinstance(model["prompt_sha256"], str) or not _SHA256.fullmatch(model["prompt_sha256"]):
            raise PolicyError("model prompt SHA-256 must be frozen")
        _strings(model["transmitted_data"], "transmitted_data")
        permitted = {"source", "config", "lockfile", "diff", "ast", "graph",
                     "context", "log", "profile", "evidence"}
        if len(set(model["transmitted_data"])) != len(model["transmitted_data"]) or not set(model["transmitted_data"]) <= permitted:
            raise PolicyError("model transmission must contain only declared project data")
    _validate_analysis(manifest["analysis"], model_enabled=model["endpoint"] is not None)
    nodes = manifest["nodes"]
    if not isinstance(nodes, list):
        raise PolicyError("nodes must be a list")
    if not nodes and (manifest["tools"] or limits["per_node"] or
                      manifest["model"]["endpoint"] is None):
        raise PolicyError("model-only manifest cannot declare executable tools or nodes")
    seen = set()
    for node in nodes:
        _fields(node, ("id", "argv", "cwd", "workload", "trigger", "tool"), "node")
        identifier = node["id"]
        if not isinstance(identifier, str) or not _ID.fullmatch(identifier) or identifier in seen:
            raise PolicyError("invalid or duplicate node id")
        seen.add(identifier)
        _strings(node["argv"], "argv")
        argv = node["argv"]
        if node["tool"] not in manifest["tools"]:
            raise PolicyError("node tool must be selected in the manifest")
        if node["tool"] == "cprofile":
            if argv[:3] != ["python", "-m", "cProfile"] or len(argv) < 4:
                raise PolicyError("cprofile requires an exact python -m cProfile command")
        elif argv[0] != node["tool"]:
            raise PolicyError("node executable must match its selected tool")
        if any("\n" in arg or "\r" in arg for arg in argv):
            raise PolicyError("multiline argv is out of scope")
        if any(arg in ("-c", "--command", "-m", "--module") for arg in argv[1:]) and node["tool"] == "python":
            raise PolicyError("python interpreter command/module dispatch is out of scope")
        if any(arg.startswith(("--pid", "--attach", "--privileged", "--volume", "--mount", "--network"))
               or arg in ("-p", "-v", "ptrace", "nsenter", "gdb") for arg in argv[1:]):
            raise PolicyError("host attach or capability-changing argument is out of scope")
        _absolute(node["cwd"], "cwd")
        if not _inside(node["cwd"], "/workspace"):
            raise PolicyError("cwd must be under read-only /workspace")
        if not isinstance(node["workload"], str) or not node["workload"].strip():
            raise PolicyError("workload must be explicit")
        if not isinstance(node["trigger"], str) or not node["trigger"].strip():
            raise PolicyError("trigger must be explicit")
    if seen != set(limits["per_node"]):
        raise PolicyError("each executable node needs exact per-node limits")
    return manifest


def manifest_hash(manifest):
    """Hash canonical UTF-8 JSON; key order and whitespace do not change the hash."""
    validate_manifest(manifest)
    try:
        raw = json.dumps(manifest, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise PolicyError("manifest must be canonical JSON data") from exc
    return hashlib.sha256(raw).hexdigest()

