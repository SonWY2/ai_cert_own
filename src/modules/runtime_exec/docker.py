"""Run exactly declared workloads in an isolated container from frozen Git bytes.

The host workspace checkout or unknown Git object is never mounted into the
container; execution is limited to the declared manifest and frozen Git bytes.
"""

import hashlib
import json
import math
import os
import posixpath
import resource
import stat
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

from modules.evidence.authenticity import verify_git_source
from modules.run_policy import manifest_hash
from modules.static_scan.orchestrator import git

_LOG_LIMIT = 1024 * 1024
_SCHEMA = "approved-execution-v1"
_PROVENANCE = "caller_declared_unattested"
_LIMITATIONS = "A container trace is not an oracle or confirmed finding."


def _artifact_sha(path: Path, root: Path, *, nonempty: bool = False) -> str:
    """Hash a regular artifact without following symlinks in its relative path."""
    relative = path.relative_to(root)
    current = root
    for component in relative.parts[:-1]:
        current = current / component
        if not stat.S_ISDIR(current.lstat().st_mode):
            raise ValueError("Runtime artifact parent must be a real directory")
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or (nonempty and not info.st_size):
        raise ValueError("Runtime artifact must be a nonempty regular file" if nonempty
                         else "Runtime artifact must be a regular file")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _writable_output(manifest: dict, output: str, label: str) -> str:
    """Resolve a declared tool output to its one writable bind mount."""
    if (not output.startswith("/") or posixpath.normpath(output) != output
            or "\\" in output or "," in output or "\n" in output or "\r" in output):
        raise ValueError(f"{label} raw output path must be normalized")
    for index, writable in enumerate(manifest["writable_paths"]):
        if output.startswith(writable.rstrip("/") + "/"):
            return f"write-{index}/{output[len(writable) + 1:]}"
    raise ValueError(f"{label} raw output path must be declared writable")


def _profile_path(manifest: dict, node: dict) -> str:
    return _writable_output(manifest, node["argv"][4], "Profile")


def _coverage_path(manifest: dict, node: dict) -> str:
    return _writable_output(manifest, node["argv"][2].removeprefix("--data-file="), "Coverage")


def _source_script(argv: list[str], cwd: str) -> str:
    if len(argv) < 2 or argv[1].startswith("-"):
        raise ValueError("Python workload must name a frozen source script")
    script = posixpath.normpath(posixpath.join(cwd, argv[1]))
    if not script.startswith("/workspace/") or script == "/workspace/":
        raise ValueError("Python workload must stay in frozen Git source")
    return script


def _test_script(node: dict) -> str:
    """Accept one focused test file from Git, not discovery or option dispatch."""
    argv = node["argv"]
    tool = node["tool"]
    if tool == "pytest":
        selection = argv[1:]
    elif tool == "unittest":
        selection = argv[1:]
    else:
        if len(argv) < 4 or argv[1] != "run" or not argv[2].startswith("--data-file="):
            raise ValueError("Coverage needs run and a declared data-file")
        selection = argv[3:]
        if selection[:2] == ["-m", "pytest"]:
            selection = selection[2:]
            tool = "pytest"
    options = {"-q", "-v", "-vv", "-x", "--disable-warnings", "-s"}
    if tool == "pytest":
        options |= {"--asyncio-mode=auto", "--asyncio-mode=strict"}
    targets = [argument for argument in selection if argument not in options]
    if len(targets) != 1 or targets[0].startswith("-"):
        raise ValueError("Test workload needs one explicit frozen test path")
    target = targets[0]
    filename, separator, selector = target.partition("::")
    if separator and (tool != "pytest" or not selector or any(not part for part in selector.split("::"))):
        raise ValueError("Unsupported test selection")
    script = _source_script(["python", filename], node["cwd"])
    if not script.endswith(".py"):
        raise ValueError("Test workload must name a Git-frozen Python file")
    return script


def validate_source_workloads(verified: dict, manifest: dict) -> None:
    """Require executable Python/test paths to be tracked by the frozen commit."""
    inventory = {item["path"] for item in verified["evidence"]}
    for node in manifest["nodes"]:
        if node["tool"] == "python":
            script = _source_script(node["argv"], node["cwd"])
        elif node["tool"] in ("pytest", "unittest", "coverage"):
            script = _test_script(node)
        else:
            continue
        if script.removeprefix("/workspace/") not in inventory:
            raise ValueError("Executable workload path is not frozen Git source")



def materialize(repo: Path, commit: str, workspace: Path) -> None:
    """Copy only regular tracked blobs from a frozen Git tree; reject links/submodules."""
    workspace.mkdir(mode=0o700)
    entries = git(repo, "ls-tree", "-rz", "--full-tree", commit)
    for entry in entries.split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        mode, kind, oid = metadata.split(b" ")
        path = raw_path.decode("utf-8", "surrogateescape")
        if (path.startswith("/") or "\\" in path or
                any(part in ("", ".", "..") for part in path.split("/"))):
            raise ValueError("Git tree contains an unsafe materialization path")
        if mode not in (b"100644", b"100755") or kind != b"blob":
            raise ValueError("Git snapshot contains a symlink or non-regular entry")
        target = workspace / path
        target.parent.mkdir(parents=True, exist_ok=True)
        data = git(repo, "cat-file", "blob", oid.decode("ascii"))
        with target.open("xb") as stream:
            stream.write(data)
        target.chmod(0o555 if mode == b"100755" else 0o444)
    for directory in sorted((p for p in workspace.rglob("*") if p.is_dir()),
                            key=lambda p: len(p.parts), reverse=True):
        directory.chmod(0o555)
    workspace.chmod(0o555)


def _limit_log() -> None:
    resource.setrlimit(resource.RLIMIT_FSIZE, (_LOG_LIMIT, _LOG_LIMIT))


def validate_runtime_host() -> None:
    """Require a reachable Docker daemon enforcing resource ceilings."""
    try:
        completed = subprocess.run(
            ["docker", "info", "--format", "{{json .}}"],
            capture_output=True, text=True, check=True, timeout=10)
        info = json.loads(completed.stdout)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError) as error:
        raise ValueError("Docker daemon is unavailable") from error
    if not isinstance(info, dict) or not info.get("ServerVersion"):
        raise ValueError("Docker daemon is unavailable")
    if (info.get("CgroupDriver") not in ("cgroupfs", "systemd")
            or any(info.get(name) is not True
                   for name in ("MemoryLimit", "CpuCfsQuota", "PidsLimit"))):
        raise ValueError("Docker CPU, memory, and PID limits must be enforced")


def _run(repo_root: Path, manifest: dict, node: dict, evidence_root: Path,
         remaining: float, trial: int, trials: int) -> dict:
    limits = manifest["limits"]["per_node"][node["id"]]
    timeout = min(limits["wall_seconds"] / trials,
                  limits["tool_seconds"] / trials, remaining)
    if timeout <= 0:
        return {"node_id": node["id"], "trial": trial, "status": "deferred", "reason": "total_timeout"}
    cidfile = evidence_root / f"{node['id']}-{trial}.cid"
    stdout_path = f"{node['id']}-{trial}.stdout"
    stderr_path = f"{node['id']}-{trial}.stderr"
    stdout = evidence_root / stdout_path
    stderr = evidence_root / stderr_path
    profile_path = _profile_path(manifest, node) if node["tool"] == "cprofile" else None
    coverage_path = _coverage_path(manifest, node) if node["tool"] == "coverage" else None
    if any(path.exists() or path.is_symlink() for path in (cidfile, stdout, stderr)):
        raise ValueError("Runtime artifact path already exists")
    if any(path is not None and ((evidence_root / path).exists()
                                 or (evidence_root / path).is_symlink())
           for path in (profile_path, coverage_path)):
        raise ValueError("Tool raw output path already exists")
    cpus = min(1, limits["cpu_seconds"] / (trials * timeout))
    if cpus < 0.01:
        raise ValueError("CPU ceiling cannot be enforced by the container runtime")
    command = ["docker", "run", "--rm", "--pull=never", "--cidfile", str(cidfile),
               "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
               "--pids-limit=128", "--network=none", "--user=65534:65534",
               f"--memory={limits['memory_bytes']}", f"--cpus={cpus:.4f}",
               "--mount", f"type=bind,source={repo_root},target=/workspace,readonly",
               "--workdir", node["cwd"], "--env", "PYTHONDONTWRITEBYTECODE=1"]
    for index, path in enumerate(manifest["writable_paths"]):
        source = evidence_root / f"write-{index}"
        if source.exists() or source.is_symlink():
            if source.is_symlink() or not source.is_dir():
                raise ValueError("Runtime writable mount must be a real directory")
        else:
            source.mkdir(mode=0o700)
        source.chmod(0o777)
        command.extend(["--mount", f"type=bind,source={source},target={path}"])
    command.extend([manifest["image_digest"], *node["argv"]])
    started = time.monotonic()
    status = "completed"
    try:
        with stdout.open("xb") as out, stderr.open("xb") as err:
            completed = subprocess.run(command, stdout=out, stderr=err,
                                       timeout=timeout, preexec_fn=_limit_log)
        code = completed.returncode
        if code != 0:
            status = "failed"
    except subprocess.TimeoutExpired:
        code = None
        status = "deferred"
    finally:
        if status == "deferred" and not cidfile.is_file():
            raise ValueError("Timed-out container has no ID; cannot guarantee cleanup")
        if status != "completed" and cidfile.is_file():
            container = cidfile.read_text().strip()
            if len(container) != 64 or any(c not in "0123456789abcdef" for c in container):
                raise ValueError("Invalid container ID; cannot guarantee cleanup")
            killed = subprocess.run(["docker", "kill", container], capture_output=True, timeout=10, check=False)
            if killed.returncode != 0 and status == "deferred":
                raise ValueError("Timed-out container could not be stopped")
    record = {"node_id": node["id"], "trial": trial, "status": status,
              "reason": "timeout" if code is None else ("nonzero_exit" if code else None),
              "exit_code": code, "wall_seconds": time.monotonic() - started,
              "command_argv": node["argv"], "image_digest": manifest["image_digest"],
              "stdout_path": stdout_path, "stderr_path": stderr_path,
              "stdout_sha256": _artifact_sha(stdout, evidence_root),
              "stderr_sha256": _artifact_sha(stderr, evidence_root),
              "manifest_sha256": manifest_hash(manifest)}
    if profile_path is not None:
        profile = evidence_root / profile_path
        if profile.exists() or profile.is_symlink():
            record["profile_path"] = profile_path
            record["profile_sha256"] = _artifact_sha(profile, evidence_root, nonempty=True)
        elif status == "completed":
            record["status"] = "failed"
            record["reason"] = "missing_profile"
    if coverage_path is not None:
        coverage = evidence_root / coverage_path
        if coverage.exists() or coverage.is_symlink():
            record["coverage_path"] = coverage_path
            record["coverage_sha256"] = _artifact_sha(coverage, evidence_root, nonempty=True)
        elif status == "completed":
            record["status"] = "failed"
            record["reason"] = "missing_coverage"
    return record


def validate_runtime_plan(manifest: dict) -> None:
    """Reject unsupported declared runtime routes before any container launch."""
    manifest_hash(manifest)
    if not manifest["nodes"]:
        raise ValueError("Model-only manifest does not authorize runtime execution")
    if manifest["network"]["dependency"] or manifest["network"]["workload"]:
        raise ValueError("Network-enabled workload requires an egress-isolated runner")
    if not manifest["writable_paths"]:
        raise ValueError("Writable evidence path must be declared")
    writable = manifest["writable_paths"]
    if any("," in path or "\n" in path or "\r" in path for path in writable):
        raise ValueError("Docker mount target contains an unsupported delimiter")
    if any(left != right and right.startswith(left.rstrip("/") + "/")
           for left in writable for right in writable):
        raise ValueError("Overlapping writable mounts are unsupported")
    nodes = manifest["nodes"]
    if sum(manifest["limits"]["per_node"][node["id"]]["cpu_seconds"] for node in nodes) > manifest["limits"]["cpu_seconds"]:
        raise ValueError("Declared node CPU ceilings exceed the total runtime CPU budget")
    eligible = {}
    outputs = set()
    for node in nodes:
        if node["tool"] not in ("python", "pytest", "unittest", "coverage", "cprofile"):
            raise ValueError("Unsupported Docker tool")
        trigger = node["trigger"]
        if node["tool"] == "python":
            _source_script(node["argv"], node["cwd"])
        elif node["tool"] in ("pytest", "unittest", "coverage"):
            _test_script(node)
            if node["tool"] == "coverage":
                path = _coverage_path(manifest, node)
                if path in outputs:
                    raise ValueError("Tool raw output path is shared by multiple nodes")
                outputs.add(path)
        if trigger == "repeat3":
            if node["tool"] != "python":
                raise ValueError("Only unprofiled Python workloads can be repeated")
            eligible[node["id"]] = node
        elif trigger == "always":
            if node["tool"] == "cprofile":
                raise ValueError("Profiler requires a reproduced slowdown trigger")
        elif trigger.startswith("slowdown:"):
            parts = trigger.split(":")
            if (len(parts) != 3 or node["tool"] != "cprofile" or
                    parts[1] not in eligible or not parts[2].isdecimal() or int(parts[2]) < 1):
                raise ValueError("Profiler needs a preceding repeated control and positive threshold")
            control = eligible[parts[1]]
            if node["workload"] != control["workload"]:
                raise ValueError("Profiled workload differs from unprofiled control")
            argv = node["argv"]
            if len(argv) < 6 or argv[:3] != ["python", "-m", "cProfile"] or argv[3] != "-o":
                raise ValueError("Profile raw output path must be declared writable")
            profile = _profile_path(manifest, node)
            if profile in outputs:
                raise ValueError("Profile raw output path is shared by multiple nodes")
            outputs.add(profile)
            _source_script(["python", *argv[5:]], node["cwd"])
            if argv[5:] != control["argv"][1:] or node["cwd"] != control["cwd"]:
                raise ValueError("Profiled command differs from unprofiled control")
        else:
            raise ValueError("Unsupported DAG trigger")


def execute_nodes(verified: dict, manifest: dict, evidence_root: Path,
                  *, run_deadline: float | None = None) -> dict:
    """Execute a bounded declared DAG against verified frozen Git source.

    ``run_deadline`` is an optional absolute monotonic deadline shared with
    other operations; it cannot extend local wall/tool limits.
    """
    digest = manifest_hash(manifest)
    validate_runtime_plan(manifest)
    if run_deadline is not None and (
            type(run_deadline) not in (float, int) or not math.isfinite(run_deadline)):
        raise ValueError("Shared runtime deadline must be a finite monotonic timestamp")
    run = verified["run"]
    if run["commit"] != manifest["snapshot_sha"]:
        raise ValueError("Frozen source differs from declared runtime snapshot")
    validate_source_workloads(verified, manifest)
    nodes = manifest["nodes"]
    root = Path(evidence_root).absolute()
    repository = Path(run["repository"]).resolve()
    if root.is_symlink() or root.resolve().is_relative_to(repository):
        raise ValueError("Runtime evidence must be outside target repository and not a symlink")
    if any(char in str(root) for char in (",", "\n", "\r")):
        raise ValueError("Docker mount source contains an unsupported delimiter")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = root.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("Runtime evidence directory must be owner-only")
    if any(root.iterdir()):
        raise ValueError("Runtime evidence directory must be empty before execution")
    started = time.monotonic()
    deadline = started + min(manifest["limits"]["wall_seconds"],
                             manifest["limits"]["tool_seconds"])
    if run_deadline is not None:
        deadline = min(deadline, run_deadline)
    with tempfile.TemporaryDirectory(prefix="cert-git-") as temporary:
        workspace = Path(temporary) / "workspace"
        if any(char in str(workspace) for char in (",", "\n", "\r")):
            raise ValueError("Frozen Git mount source contains an unsupported delimiter")
        materialize(Path(run["repository"]), run["commit"], workspace)
        result = []
        timings = {}
        for node in nodes:
            trigger = node["trigger"]
            trials = 3 if trigger == "repeat3" else 1
            if trigger.startswith("slowdown:"):
                _, baseline, threshold = trigger.split(":")
                if baseline not in timings:
                    result.append({"node_id": node["id"], "status": "deferred", "reason": "control_unavailable"})
                    continue
                if statistics.median(timings[baseline]) * 1000 < int(threshold):
                    result.append({"node_id": node["id"], "status": "skipped", "reason": "slowdown_not_reproduced"})
                    continue
            samples = []
            for trial in range(trials):
                measured = _run(workspace, manifest, node, root,
                                deadline - time.monotonic(), trial, trials)
                result.append(measured)
                if measured["status"] != "completed":
                    break
                samples.append(measured["wall_seconds"])
            if len(samples) == trials:
                timings[node["id"]] = samples
        trace = {"schema_version": _SCHEMA, "snapshot_sha": run["commit"],
                 "source_run_id": run["id"], "manifest_sha256": digest,
                 "nodes": result, "runtime_attested": False,
                 "runtime_provenance": _PROVENANCE, "limitations": _LIMITATIONS}
        with (root / "execution.json").open("xb") as stream:
            stream.write((json.dumps(trace, sort_keys=True, separators=(",", ":")) + "\n").encode())
            stream.flush()
            os.fsync(stream.fileno())
        return trace


def verify_execution(source_bundle: Path, manifest: dict, evidence_root: Path) -> dict:
    """Verify frozen Git and local trace/artifact consistency, never Docker provenance."""
    verified = verify_git_source(source_bundle)
    validate_runtime_plan(manifest)
    run = verified["run"]
    digest = manifest_hash(manifest)
    if manifest["snapshot_sha"] != run["commit"]:
        raise ValueError("Runtime manifest differs from authenticated Git source")
    validate_source_workloads(verified, manifest)
    root = Path(evidence_root).absolute()
    repository = Path(run["repository"]).resolve()
    source = Path(source_bundle).resolve()
    if (root.is_symlink() or root.resolve().is_relative_to(repository)
            or root.resolve().is_relative_to(source)):
        raise ValueError("Runtime evidence must be outside source and repository")
    info = root.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("Runtime evidence directory must be owner-only")
    trace_file = root / "execution.json"
    if not stat.S_ISREG(trace_file.lstat().st_mode):
        raise ValueError("Execution trace must be a regular file")
    raw = trace_file.read_bytes()
    try:
        trace = json.loads(raw)
        canonical = (json.dumps(trace, sort_keys=True, separators=(",", ":")) + "\n").encode()
    except (UnicodeError, TypeError, ValueError) as error:
        raise ValueError("Execution trace must be canonical JSON") from error
    if raw != canonical or not isinstance(trace, dict):
        raise ValueError("Execution trace must be canonical JSON")
    expected = {"schema_version": _SCHEMA, "snapshot_sha": run["commit"],
                "source_run_id": run["id"], "manifest_sha256": digest,
                "runtime_attested": False, "runtime_provenance": _PROVENANCE,
                "limitations": _LIMITATIONS}
    if set(trace) != set(expected) | {"nodes"} or any(trace[key] != value for key, value in expected.items()):
        raise ValueError("Execution trace claims unsupported provenance or mismatched source/manifest")
    if type(trace["runtime_attested"]) is not bool or not isinstance(trace["nodes"], list):
        raise ValueError("Invalid execution trace status")
    rows = trace["nodes"]
    index = 0
    timings = {}
    for node in manifest["nodes"]:
        trigger = node["trigger"]
        if trigger.startswith("slowdown:"):
            _, baseline, threshold = trigger.split(":")
            if baseline not in timings:
                expected_skip = ("deferred", "control_unavailable")
            elif statistics.median(timings[baseline]) * 1000 < int(threshold):
                expected_skip = ("skipped", "slowdown_not_reproduced")
            else:
                expected_skip = None
            if expected_skip is not None:
                if index >= len(rows) or rows[index] != {
                        "node_id": node["id"], "status": expected_skip[0], "reason": expected_skip[1]}:
                    raise ValueError("Execution DAG trigger differs from recorded node order")
                index += 1
                continue
        trials = 3 if trigger == "repeat3" else 1
        samples = []
        for trial in range(trials):
            if index >= len(rows):
                raise ValueError("Execution trace omits a declared node")
            row = rows[index]
            index += 1
            if not isinstance(row, dict) or row.get("node_id") != node["id"] or type(row.get("trial")) is not int or row["trial"] != trial:
                raise ValueError("Execution trace node or trial order differs from manifest")
            if row == {"node_id": node["id"], "trial": trial, "status": "deferred",
                       "reason": "total_timeout"}:
                break
            fields = {"node_id", "trial", "status", "reason", "exit_code", "wall_seconds",
                      "command_argv", "image_digest", "manifest_sha256",
                      "stdout_path", "stdout_sha256", "stderr_path", "stderr_sha256"}
            has_profile = "profile_path" in row or "profile_sha256" in row
            if has_profile:
                fields |= {"profile_path", "profile_sha256"}
            has_coverage = "coverage_path" in row or "coverage_sha256" in row
            if has_coverage:
                fields |= {"coverage_path", "coverage_sha256"}
            if (set(row) != fields or node["tool"] != "cprofile" and has_profile
                    or node["tool"] != "coverage" and has_coverage):
                raise ValueError("Unexpected execution artifact fields")
            if (row["command_argv"] != node["argv"] or
                    row["image_digest"] != manifest["image_digest"] or
                    row["manifest_sha256"] != digest or
                    type(row["wall_seconds"]) not in (int, float) or
                    not math.isfinite(row["wall_seconds"]) or row["wall_seconds"] < 0):
                raise ValueError("Execution metadata differs from declared manifest")
            if (row["stdout_path"] != f"{node['id']}-{trial}.stdout" or
                    row["stderr_path"] != f"{node['id']}-{trial}.stderr"):
                raise ValueError("Execution log path differs from declared node")
            for kind in ("stdout", "stderr"):
                if row[f"{kind}_sha256"] != _artifact_sha(root / row[f"{kind}_path"], root):
                    raise ValueError("Recorded execution log differs from its bytes")
            if node["tool"] == "cprofile":
                profile_name = _profile_path(manifest, node)
                profile_file = root / profile_name
                profile_exists = profile_file.exists() or profile_file.is_symlink()
                if has_profile != profile_exists:
                    raise ValueError("Profiler artifact presence differs from trace")
                if has_profile and (row["profile_path"] != profile_name or
                                    row["profile_sha256"] != _artifact_sha(profile_file, root, nonempty=True)):
                    raise ValueError("Recorded profiler output differs from its bytes")
            if node["tool"] == "coverage":
                coverage_name = _coverage_path(manifest, node)
                coverage_file = root / coverage_name
                coverage_exists = coverage_file.exists() or coverage_file.is_symlink()
                if has_coverage != coverage_exists:
                    raise ValueError("Coverage artifact presence differs from trace")
                if has_coverage and (row["coverage_path"] != coverage_name or
                                     row["coverage_sha256"] != _artifact_sha(coverage_file, root, nonempty=True)):
                    raise ValueError("Recorded coverage output differs from its bytes")
            code = row["exit_code"]
            if (row["status"] == "completed" and (type(code) is not int or code != 0 or
                    row["reason"] is not None or node["tool"] == "cprofile" and not has_profile
                    or node["tool"] == "coverage" and not has_coverage)):
                raise ValueError("Completed node lacks its declared successful artifacts")
            if (row["status"] == "failed" and not (
                    type(code) is int and code != 0 and row["reason"] == "nonzero_exit"
                    or node["tool"] == "cprofile" and type(code) is int and code == 0
                    and not has_profile and row["reason"] == "missing_profile"
                    or node["tool"] == "coverage" and type(code) is int and code == 0
                    and not has_coverage and row["reason"] == "missing_coverage")):
                raise ValueError("Failed node has inconsistent exit status")
            if (row["status"] == "deferred" and (code is not None or row["reason"] != "timeout")):
                raise ValueError("Deferred node has inconsistent timeout status")
            if row["status"] not in ("completed", "failed", "deferred"):
                raise ValueError("Unsupported execution status")
            if row["status"] != "completed":
                break
            samples.append(row["wall_seconds"])
        if len(samples) == trials:
            timings[node["id"]] = samples
    if index != len(rows):
        raise ValueError("Execution trace has undeclared nodes or trials")
    return trace


def summarize_execution(trace: dict, evidence_root: Path) -> dict:
    """Bound the display/model excerpt of an already verified execution trace."""
    root = Path(evidence_root)
    remaining = 8192
    rows = []
    for node in trace["nodes"]:
        row = {key: node[key] for key in ("node_id", "status", "reason", "trial",
                                         "command_argv", "exit_code", "wall_seconds")
               if key in node}
        row["executed"] = "command_argv" in node
        for kind in ("stderr", "stdout"):
            if f"{kind}_path" not in node:
                continue
            name = node[f"{kind}_path"]
            raw = (root / name).read_bytes()
            size = min(len(raw), 4096, remaining)
            row[f"{kind}_path"] = name
            row[f"{kind}_truncated"] = size < len(raw)
            if size:
                text = raw[-size:].decode("utf-8", errors="replace")
                text = "".join(char for char in text if char in "\n\t" or
                               ord(char) >= 32 and ord(char) != 127)
                encoded = text.encode("utf-8")
                cap = min(remaining, 4096)
                row[f"{kind}_truncated"] |= len(encoded) > cap
                row[kind] = encoded[-cap:].decode("utf-8", errors="ignore")
                remaining -= len(row[kind].encode("utf-8"))
            else:
                row[kind] = ""
        rows.append(row)
    return {"snapshot_sha": trace["snapshot_sha"], "manifest_sha256": trace["manifest_sha256"],
            "runtime_attested": False, "nodes": rows,
            "truncated": any(row.get(f"{kind}_truncated", False) for row in rows
                             for kind in ("stderr", "stdout"))}
