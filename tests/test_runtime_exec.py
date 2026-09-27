"""Executable snapshots must stay in frozen Git and declared bounded Docker runs."""

import contextlib
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from modules.evidence.authenticity import verify_git_source  # noqa: E402
from modules.evidence.provenance import write_source_run  # noqa: E402
from modules.run_policy import LOCAL_OAUTH_ENDPOINT, manifest_hash  # noqa: E402
from modules.runtime_exec.docker import (  # noqa: E402
    _artifact_sha, execute_nodes, materialize, summarize_execution,
    validate_runtime_host, validate_runtime_plan, validate_source_workloads,
    verify_execution,
)
from modules.runtime_exec import docker  # noqa: E402
import run_approved  # noqa: E402
from modules.static_scan.orchestrator import scan  # noqa: E402


class RuntimeExecTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def freeze(self):
        self.git("add", "-A")
        self.git("-c", "user.name=A", "-c", "user.email=a@b.c", "commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def manifest(self, sha):
        baseline = {"wall_seconds": 10, "cpu_seconds": 10, "memory_bytes": 1048576,
                    "tokens": 100, "tool_seconds": 10}
        total = {**baseline, "wall_seconds": 30, "cpu_seconds": 30, "tool_seconds": 30}
        return {"schema_version": "run-manifest-v3", "snapshot_sha": sha,
                "analysis": None,
                "image_digest": "sha256:" + "a" * 64,
                "tools": ["python", "cprofile"],
                "nodes": [
                    {"id": "base", "argv": ["python", "bench.py"], "cwd": "/workspace",
                     "workload": "bench.py", "trigger": "repeat3", "tool": "python"},
                    {"id": "profile", "argv": ["python", "-m", "cProfile", "-o",
                                                "/work/evidence/profile.pstats", "bench.py"],
                     "cwd": "/workspace", "workload": "bench.py",
                     "trigger": "slowdown:base:20", "tool": "cprofile"}],
                "limits": {**total, "per_node": {"base": baseline, "profile": baseline}},
                "network": {"dependency": False, "model": False, "workload": False},
                "writable_paths": ["/work/evidence"],
                "model": {"endpoint": None, "name_version": None,
                          "prompt_sha256": None, "transmitted_data": []}}

    def test_model_only_manifest_cannot_run_runtime(self):
        manifest = self.manifest("a" * 40)
        manifest["tools"] = []
        manifest["nodes"] = []
        manifest["limits"]["per_node"] = {}
        manifest["network"]["model"] = True
        manifest["model"] = {"endpoint": LOCAL_OAUTH_ENDPOINT, "name_version": "gpt-6-luna",
                             "prompt_sha256": "c" * 64, "transmitted_data": ["source", "context"]}
        manifest["analysis"] = {
            "mode": "five",
            "roles": ["structure", "correctness", "performance", "concurrency", "tests"],
            "scope": "symbol", "symbol": "bench.run", "base_sha": None,
            "context_policy": "git-ast-context-v1",
            "contexts": [{"scope_id": "symbol:bench.run", "sha256": "d" * 64}]}
        self.assertEqual(len(manifest_hash(manifest)), 64)
        with self.assertRaisesRegex(ValueError, "does not authorize runtime"):
            validate_runtime_plan(manifest)

    def test_materialize_frozen_regular_blobs_not_dirty_worktree(self):
        (self.repo / "bench.py").write_text("print('frozen')\n")
        sha = self.freeze()
        (self.repo / "bench.py").write_text("raise RuntimeError('dirty')\n")
        destination = self.root / "snapshot"
        materialize(self.repo, sha, destination)
        self.assertEqual((destination / "bench.py").read_text(), "print('frozen')\n")
        self.assertEqual((destination / "bench.py").stat().st_mode & 0o222, 0)

    def test_rejects_git_symlink_without_reading_external_file(self):
        (self.repo / "bench.py").write_text("print('safe')\n")
        (self.repo / "linked.py").symlink_to("/etc/passwd")
        sha = self.freeze()
        with self.assertRaisesRegex(ValueError, "symlink"):
            materialize(self.repo, sha, self.root / "snapshot")

    def test_profiler_requires_repeated_same_workload_and_declared_output(self):
        valid = self.manifest("a" * 40)
        validate_runtime_plan(valid)
        valid["nodes"][1]["workload"] = "other.py"
        with self.assertRaisesRegex(ValueError, "workload differs"):
            validate_runtime_plan(valid)
        valid["nodes"][1]["workload"] = "bench.py"
        valid["nodes"][1]["argv"][4] = "/tmp/undeclared.pstats"
        with self.assertRaisesRegex(ValueError, "declared writable"):
            validate_runtime_plan(valid)
        valid["nodes"][1]["argv"][4] = "/work/evidence/profile.pstats"
        valid["network"]["workload"] = True
        with self.assertRaisesRegex(ValueError, "Network-enabled"):
            validate_runtime_plan(valid)

    def test_cli_executes_without_receipt_with_mocked_docker(self):
        bundle, manifest, output, expected = self.failed_trace()
        for artifact in output.iterdir():
            artifact.unlink()
        output.rmdir()
        file = self.root / "manifest.json"
        file.write_text(json.dumps(manifest))
        stdout = io.StringIO()

        def failed_launch(_workspace, _manifest, _node, root, _remaining, trial, _trials):
            self.assertEqual(trial, 0)
            (root / "base-0.stdout").write_bytes(b"")
            (root / "base-0.stderr").write_bytes(b"docker: image unavailable\n")
            return expected["nodes"][0].copy()

        with patch.object(sys, "argv", ["run_approved.py", str(bundle), str(file),
                                        str(output)]), patch.object(
                run_approved, "validate_runtime_host") as host, patch.object(
                docker, "_run", side_effect=failed_launch) as launch, contextlib.redirect_stdout(stdout):
            self.assertEqual(run_approved.main(), 0)
        host.assert_called_once_with()
        launch.assert_called_once()
        trace = json.loads(stdout.getvalue())
        self.assertEqual(trace, expected)
        self.assertEqual(verify_execution(bundle, manifest, output), expected)

    def test_changed_commit_and_workload_rejected_without_container(self):
        bundle, manifest, output, _ = self.failed_trace()
        verified = verify_git_source(bundle)
        wrong_commit = json.loads(json.dumps(manifest))
        wrong_commit["snapshot_sha"] = "a" * 40
        with patch.object(docker, "materialize") as materialize_mock:
            with self.assertRaisesRegex(ValueError, "source differs"):
                execute_nodes(verified, wrong_commit, output)
            materialize_mock.assert_not_called()
        wrong_workload = json.loads(json.dumps(manifest))
        for node in wrong_workload["nodes"]:
            node["workload"] = "missing.py"
            node["argv"][-1] = "missing.py"
        with patch.object(docker, "materialize") as materialize_mock:
            with self.assertRaisesRegex(ValueError, "not frozen Git source"):
                execute_nodes(verified, wrong_workload, output)
            materialize_mock.assert_not_called()
        manifest_file = self.root / "invalid-manifest.json"
        for candidate, error in ((wrong_commit, "authenticated source commit"),
                                 (wrong_workload, "not frozen Git source")):
            manifest_file.write_text(json.dumps(candidate))
            stderr = io.StringIO()
            with self.subTest(error=error), patch.object(
                    sys, "argv", ["run_approved.py", str(bundle), str(manifest_file),
                                  str(self.root / "new-runtime")]), patch.object(
                    run_approved, "validate_runtime_host") as host, contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as rejected:
                    run_approved.main()
                self.assertEqual(rejected.exception.code, 2)
                self.assertIn(error, stderr.getvalue())
                host.assert_not_called()
        self.assertFalse((self.root / "new-runtime").exists())

    def test_host_preflight_requires_enforced_limits(self):
        for missing in ("CgroupDriver", "MemoryLimit", "CpuCfsQuota", "PidsLimit"):
            info = {"ServerVersion": "1", "CgroupDriver": "systemd",
                    "MemoryLimit": True, "CpuCfsQuota": True, "PidsLimit": True}
            info[missing] = None
            with self.subTest(missing=missing), patch.object(
                    docker.subprocess, "run",
                    return_value=subprocess.CompletedProcess([], 0, json.dumps(info))):
                with self.assertRaisesRegex(ValueError, "must be enforced"):
                    validate_runtime_host()

    def failed_trace(self):
        """Offline failed launch logs: deliberately no simulated Docker success."""
        (self.repo / "bench.py").write_text("print('frozen')\n")
        sha = self.freeze()
        bundle = write_source_run(self.root / "source", str(self.repo), scan(self.repo, sha))
        manifest = self.manifest(sha)
        output = self.root / "runtime"
        output.mkdir(mode=0o700)
        stdout, stderr = b"", b"docker: image unavailable\n"
        (output / "base-0.stdout").write_bytes(stdout)
        (output / "base-0.stderr").write_bytes(stderr)
        trace = {
            "schema_version": "approved-execution-v1", "snapshot_sha": sha,
            "source_run_id": json.loads((bundle / "run.json").read_text())["id"],
            "manifest_sha256": manifest_hash(manifest), "runtime_attested": False,
            "runtime_provenance": "caller_declared_unattested",
            "limitations": "A container trace is not an oracle or confirmed finding.",
            "nodes": [
                {"node_id": "base", "trial": 0, "status": "failed",
                 "reason": "nonzero_exit", "exit_code": 125, "wall_seconds": 0.5,
                 "command_argv": manifest["nodes"][0]["argv"],
                 "image_digest": manifest["image_digest"],
                 "manifest_sha256": manifest_hash(manifest),
                 "stdout_path": "base-0.stdout", "stderr_path": "base-0.stderr",
                 "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
                 "stderr_sha256": hashlib.sha256(stderr).hexdigest()},
                {"node_id": "profile", "status": "deferred", "reason": "control_unavailable"},
            ],
        }
        return bundle, manifest, output, trace

    @staticmethod
    def store_trace(output, trace):
        (output / "execution.json").write_text(
            json.dumps(trace, sort_keys=True, separators=(",", ":")) + "\n")

    def test_offline_trace_replays_real_git_and_exact_logs_without_attestation(self):
        bundle, manifest, output, trace = self.failed_trace()
        self.store_trace(output, trace)
        (self.repo / "bench.py").write_text("print('dirty workspace')\n")
        self.assertEqual(verify_execution(bundle, manifest, output), trace)
        manifest_file = self.root / "manifest.json"
        manifest_file.write_text(json.dumps(manifest))
        inspected = subprocess.run([
            sys.executable, str(ROOT / "src" / "run_approved.py"), "--verify",
            str(bundle), str(manifest_file), str(output)], capture_output=True, text=True)
        self.assertEqual(inspected.returncode, 0, inspected.stderr)
        self.assertFalse((output / "base-0.cid").exists())
        self.assertFalse(json.loads(inspected.stdout)["runtime_attested"])

    def test_verified_log_summary_is_bounded_and_cleans_control_bytes(self):
        bundle, manifest, output, trace = self.failed_trace()
        stderr = b"\x1b[31m" + b"x" * 9000 + b"\n\x00"
        (output / "base-0.stderr").write_bytes(stderr)
        trace["nodes"][0]["stderr_sha256"] = hashlib.sha256(stderr).hexdigest()
        self.store_trace(output, trace)
        verified = verify_execution(bundle, manifest, output)
        summary = summarize_execution(verified, output)
        self.assertTrue(summary["truncated"])
        self.assertFalse(summary["runtime_attested"])
        self.assertEqual(summary["nodes"][1]["executed"], False)
        self.assertNotIn("exit_code", summary["nodes"][1])
        self.assertLessEqual(len(summary["nodes"][0]["stderr"].encode()), 4096)
        self.assertNotIn("\x00", summary["nodes"][0]["stderr"])
        self.assertNotIn("\x1b", summary["nodes"][0]["stderr"])

    def test_trace_rejects_modified_bytes_forged_success_and_invalid_order(self):
        bundle, manifest, output, trace = self.failed_trace()
        self.store_trace(output, trace)
        (output / "base-0.stderr").write_bytes(b"altered")
        with self.assertRaisesRegex(ValueError, "log differs"):
            verify_execution(bundle, manifest, output)
        (output / "base-0.stderr").write_bytes(b"docker: image unavailable\n")
        trace["runtime_attested"] = True
        self.store_trace(output, trace)
        with self.assertRaisesRegex(ValueError, "unsupported provenance"):
            verify_execution(bundle, manifest, output)
        trace["runtime_attested"] = False
        trace["nodes"][0]["status"] = "completed"
        self.store_trace(output, trace)
        with self.assertRaisesRegex(ValueError, "Completed node"):
            verify_execution(bundle, manifest, output)
        trace["nodes"].reverse()
        self.store_trace(output, trace)
        with self.assertRaisesRegex(ValueError, "node or trial order"):
            verify_execution(bundle, manifest, output)

    def test_trace_rejects_changed_git_manifest_and_symlink_artifacts(self):
        bundle, manifest, output, trace = self.failed_trace()
        self.store_trace(output, trace)
        changed = json.loads(json.dumps(manifest))
        changed["image_digest"] = "sha256:" + "b" * 64
        with self.assertRaisesRegex(ValueError, "manifest"):
            verify_execution(bundle, changed, output)
        (output / "base-0.stdout").unlink()
        (output / "base-0.stdout").symlink_to(output / "base-0.stderr")
        with self.assertRaisesRegex(ValueError, "regular file"):
            verify_execution(bundle, manifest, output)
        (output / "base-0.stdout").unlink()
        (output / "base-0.stdout").write_bytes(b"")
        (bundle / "evidence.jsonl").write_text(
            (bundle / "evidence.jsonl").read_text().replace(
                hashlib.sha256(b"print('frozen')\n").hexdigest(), "0" * 64))
        with self.assertRaises(ValueError):
            verify_execution(bundle, manifest, output)

    def test_unsupported_runtime_paths_are_rejected_before_execution(self):
        valid = self.manifest("a" * 40)
        cases = [
            (lambda m: m["nodes"][0]["argv"].__setitem__(1, "/work/evidence/script.py"),
             "frozen Git source"),
            (lambda m: m["nodes"][1]["argv"].__setitem__(4, "/work/evidence/../../outside"),
             "normalized"),
            (lambda m: m["nodes"][1]["argv"].__setitem__(5, "other.py"),
             "Profiled command differs"),
            (lambda m: m["writable_paths"].append("/work/evidence/more"),
             "Overlapping writable mounts"),
            (lambda m: m["writable_paths"].__setitem__(0, "/work/evidence,readonly=false"),
             "unsupported delimiter"),
            (lambda m: (m["tools"].append("pytest"), m["nodes"][0].update(
                {"tool": "pytest", "trigger": "always",
                 "argv": ["pytest", "--pyargs", "bench"]})),
             "one explicit frozen test path"),
        ]
        for mutate, message in cases:
            candidate = json.loads(json.dumps(valid))
            mutate(candidate)
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                validate_runtime_plan(candidate)

    def test_focused_pytest_asyncio_unittest_coverage_stay_in_git(self):
        (self.repo / "tests").mkdir()
        (self.repo / "tests" / "test_async.py").write_text(
            "import asyncio\n\ndef test_cancel():\n    assert asyncio.run(asyncio.sleep(0, True))\n")
        sha = self.freeze()
        bundle = write_source_run(self.root / "source", str(self.repo), scan(self.repo, sha))
        verified = verify_git_source(bundle)
        manifest = self.manifest(sha)
        selected = manifest["nodes"][0]
        selected.update({"id": "focus", "tool": "pytest", "trigger": "always",
                         "workload": "tests/test_async.py::test_cancel",
                         "argv": ["pytest", "-q", "--asyncio-mode=auto",
                                  "tests/test_async.py::test_cancel"]})
        manifest["nodes"] = [selected]
        manifest["limits"]["per_node"] = {"focus": manifest["limits"]["per_node"]["base"]}
        manifest["tools"] = ["pytest"]
        validate_runtime_plan(manifest)
        validate_source_workloads(verified, manifest)
        selected["tool"] = "unittest"
        selected["argv"] = ["unittest", "-q", "tests/test_async.py"]
        manifest["tools"] = ["unittest"]
        validate_runtime_plan(manifest)
        validate_source_workloads(verified, manifest)
        selected["tool"] = "coverage"
        selected["argv"] = ["coverage", "run", "--data-file=/work/evidence/focus.coverage",
                            "-m", "pytest", "-q", "tests/test_async.py::test_cancel"]
        manifest["tools"] = ["coverage"]
        validate_runtime_plan(manifest)
        validate_source_workloads(verified, manifest)
        selected["argv"][-1] = "tests/missing.py::test_cancel"
        with self.assertRaisesRegex(ValueError, "not frozen Git source"):
            validate_source_workloads(verified, manifest)
        selected["argv"][-1] = "tests/test_async.py::test_cancel"
        selected["argv"][2] = "--data-file=/work/evidence/../escape"
        with self.assertRaisesRegex(ValueError, "normalized"):
            validate_runtime_plan(manifest)

    def test_focused_test_flags_cannot_enable_discovery_or_external_paths(self):
        valid = self.manifest("a" * 40)
        node = valid["nodes"][0]
        node.update({"tool": "pytest", "trigger": "always", "argv": [
            "pytest", "-q", "tests/test_async.py::test_cancel"]})
        valid["tools"] = ["pytest", "cprofile"]
        for argv in (["pytest", "-q"], ["pytest", "--pyargs", "pkg"],
                     ["pytest", "/work/evidence/test_external.py"],
                     ["pytest", "tests/test_async.py", "tests/test_other.py"]):
            node["argv"] = argv
            with self.subTest(argv=argv), self.assertRaises(ValueError):
                validate_runtime_plan(valid)

    def test_profiler_bytes_require_real_regular_nonempty_output(self):
        output = self.root / "runtime"
        output.mkdir(mode=0o700)
        profile = output / "write-0" / "profile.pstats"
        profile.parent.mkdir()
        profile.write_bytes(b"profile fixture")
        self.assertEqual(_artifact_sha(profile, output, nonempty=True),
                         hashlib.sha256(b"profile fixture").hexdigest())
        profile.write_bytes(b"")
        with self.assertRaisesRegex(ValueError, "nonempty"):
            _artifact_sha(profile, output, nonempty=True)
        profile.unlink()
        profile.symlink_to(self.repo)
        with self.assertRaisesRegex(ValueError, "regular file"):
            _artifact_sha(profile, output, nonempty=True)

    def test_expired_shared_deadline_deferred_without_docker_or_log_claims(self):
        bundle, manifest, output, _ = self.failed_trace()
        (output / "base-0.stdout").unlink()
        (output / "base-0.stderr").unlink()
        output.rmdir()
        trace = execute_nodes(verify_git_source(bundle), manifest, output,
                              run_deadline=time.monotonic() - 1)
        self.assertEqual(trace["nodes"], [
            {"node_id": "base", "trial": 0, "status": "deferred", "reason": "total_timeout"},
            {"node_id": "profile", "status": "deferred", "reason": "control_unavailable"},
        ])
        self.assertEqual(verify_execution(bundle, manifest, output), trace)
        self.assertFalse((output / "base-0.stdout").exists())

    def test_source_bundle_and_owner_boundaries_reject_without_launch(self):
        bundle, manifest, output, _ = self.failed_trace()
        file = self.root / "manifest.json"
        file.write_text(json.dumps(manifest))
        forbidden = bundle / "execution"
        denied = subprocess.run([
            sys.executable, str(ROOT / "src" / "run_approved.py"),
            str(bundle), str(file), str(forbidden)],
            capture_output=True, text=True)
        self.assertEqual(denied.returncode, 2)
        self.assertIn("outside target repository and source bundle", denied.stderr)
        self.assertFalse(forbidden.exists())
        output.chmod(0o755)
        with self.assertRaisesRegex(ValueError, "owner-only"):
            verify_execution(bundle, manifest, output)


if __name__ == "__main__":
    unittest.main()
