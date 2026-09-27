"""A declared run needs a matching single-use local approval before execution."""

import copy
import json
import os
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from modules.diagnosis.plan import context_hash, prepare_analysis
from modules.evidence.authenticity import verify_git_source
from modules.evidence.provenance import write_source_run
from modules.run_policy import (LOCAL_OAUTH_ENDPOINT, PolicyError, consume_approval,
                                issue_approval, manifest_hash, verify_approval)
from modules.static_scan.orchestrator import scan


class RunPolicyTest(unittest.TestCase):
    def manifest(self):
        bounds = {"wall_seconds": 30, "cpu_seconds": 30, "memory_bytes": 1024 * 1024,
                  "tokens": 100, "tool_seconds": 30}
        return {"schema_version": "run-manifest-v3", "snapshot_sha": "a" * 40,
                "analysis": None,
                "image_digest": "sha256:" + "b" * 64,
                "tools": ["pytest"],
                "nodes": [{"id": "focused", "argv": ["pytest", "tests/test_worker.py"],
                           "cwd": "/workspace", "workload": "tests/test_worker.py",
                           "trigger": "approved focused test", "tool": "pytest"}],
                "limits": {**bounds, "per_node": {"focused": bounds}},
                "network": {"dependency": False, "model": False, "workload": False},
                "writable_paths": ["/work/evidence"],
                "model": {"endpoint": None, "name_version": None, "prompt_sha256": None,
                          "transmitted_data": []}}

    def model_analysis(self):
        return {"mode": "five",
                "roles": ["structure", "correctness", "performance", "concurrency", "tests"],
                "scope": "symbol", "symbol": "worker.run", "base_sha": None,
                "context_policy": "git-ast-context-v1",
                "contexts": [{"scope_id": "symbol:worker.run", "sha256": "d" * 64}]}

    def test_v2_manifest_cannot_authorize_or_consume_approval(self):
        manifest = self.manifest()
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory) / "approval.json"
            digest = manifest_hash(manifest)
            issue_approval(manifest, manifest["snapshot_sha"], receipt, digest)
            old = {**manifest, "schema_version": "run-manifest-v2"}
            with self.assertRaises(PolicyError):
                manifest_hash(old)
            with self.assertRaises(PolicyError):
                verify_approval(old, old["snapshot_sha"], receipt)
            with self.assertRaises(PolicyError):
                consume_approval(old, old["snapshot_sha"], receipt)
            self.assertFalse(Path(str(receipt) + ".used").exists())

    def test_analysis_plan_is_bound_to_single_use_approval(self):
        manifest = self.manifest()
        manifest["network"]["model"] = True
        manifest["model"] = {"endpoint": LOCAL_OAUTH_ENDPOINT, "name_version": "pinned-model",
                             "prompt_sha256": "c" * 64, "transmitted_data": ["source", "context"]}
        manifest["analysis"] = self.model_analysis()
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory) / "approval.json"
            digest = manifest_hash(manifest)
            issue_approval(manifest, manifest["snapshot_sha"], receipt, digest)
            changes = [
                {"mode": "boundary", "roles": manifest["analysis"]["roles"] + ["assumptions"]},
                {"contexts": [{"scope_id": "symbol:worker.run", "sha256": "e" * 64}]},
                {"symbol": "worker.other",
                 "contexts": [{"scope_id": "symbol:worker.other", "sha256": "d" * 64}]},
                {"scope": "full", "symbol": None,
                 "contexts": [{"scope_id": "module:worker.py", "sha256": "d" * 64}]},
            ]
            for change in changes:
                altered = copy.deepcopy(manifest)
                altered["analysis"].update(change)
                with self.subTest(change=change), self.assertRaises(PolicyError):
                    consume_approval(altered, altered["snapshot_sha"], receipt)
                self.assertFalse(Path(str(receipt) + ".used").exists())
            self.assertEqual(consume_approval(manifest, manifest["snapshot_sha"], receipt), digest)

    def test_incomplete_or_ambiguous_analysis_cannot_be_approved(self):
        manifest = self.manifest()
        manifest["network"]["model"] = True
        manifest["model"] = {"endpoint": LOCAL_OAUTH_ENDPOINT, "name_version": "pinned-model",
                             "prompt_sha256": "c" * 64, "transmitted_data": ["source", "context"]}
        manifest["analysis"] = self.model_analysis()
        changes = [
            {"mode": "unknown"}, {"roles": ["correctness"]},
            {"roles": list(reversed(manifest["analysis"]["roles"]))},
            {"scope": "unknown"}, {"symbol": ""}, {"symbol": None},
            {"base_sha": "a" * 40}, {"context_policy": "custom"},
            {"contexts": []},
            {"contexts": [{"scope_id": "symbol:worker.run", "sha256": None}]},
            {"contexts": [{"scope_id": "symbol:worker.run", "sha256": "x" * 64}]},
            {"contexts": [{"scope_id": "symbol:worker.other", "sha256": "d" * 64}]},
            {"contexts": manifest["analysis"]["contexts"] * 2},
            {"scope": "impact", "symbol": None, "base_sha": None},
            {"scope": "impact", "symbol": None, "base_sha": "a" * 64},
            {"scope": "full", "symbol": None,
             "contexts": [{"scope_id": "module:../worker.py", "sha256": "d" * 64}]},
            {"mode": "plain", "roles": ["all"], "scope": "full", "symbol": None},
            {"extra": True},
        ]
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory) / "approval.json"
            for change in changes:
                altered = copy.deepcopy(manifest)
                altered["analysis"].update(change)
                with self.subTest(change=change), self.assertRaises(PolicyError):
                    issue_approval(altered, altered["snapshot_sha"], receipt, context_hash(altered))
                self.assertFalse(receipt.exists())
            for analysis in (None, {}, []):
                altered = copy.deepcopy(manifest)
                altered["analysis"] = analysis
                with self.subTest(analysis=analysis), self.assertRaises(PolicyError):
                    issue_approval(altered, altered["snapshot_sha"], receipt, context_hash(altered))

    def test_v1_and_missing_analysis_are_rejected_before_receipt_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory) / "approval.json"
            for legacy in (True, False):
                manifest = self.manifest()
                del manifest["analysis"]
                if legacy:
                    manifest["schema_version"] = "run-manifest-v1"
                with self.subTest(legacy=legacy), self.assertRaises(PolicyError):
                    issue_approval(manifest, manifest["snapshot_sha"], receipt, context_hash(manifest))
                self.assertFalse(receipt.exists())
            manifest = self.manifest()
            manifest["analysis"] = self.model_analysis()
            with self.assertRaises(PolicyError):
                manifest_hash(manifest)

    def test_unavailable_context_is_allowed_only_for_batch_modules(self):
        manifest = self.manifest()
        manifest["network"]["model"] = True
        manifest["model"] = {"endpoint": LOCAL_OAUTH_ENDPOINT, "name_version": "pinned-model",
                             "prompt_sha256": "c" * 64, "transmitted_data": ["source", "context"]}
        manifest["analysis"] = {**self.model_analysis(), "scope": "impact", "symbol": None,
                                "base_sha": "a" * 40,
                                "contexts": [{"scope_id": "module:broken.py", "sha256": None}]}
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory) / "approval.json"
            digest = manifest_hash(manifest)
            issue_approval(manifest, manifest["snapshot_sha"], receipt, digest)
            self.assertEqual(verify_approval(manifest, manifest["snapshot_sha"], receipt), digest)
            manifest["analysis"]["mode"] = "single"
            manifest["analysis"]["roles"] = ["all"]
            with self.assertRaises(PolicyError):
                manifest_hash(manifest)

    def test_analysis_uses_frozen_source_and_preserves_unavailable_batch_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            def git(*args):
                return subprocess.run(["git", "-C", str(repo), *args], check=True,
                                      capture_output=True, text=True).stdout.strip()
            git("init", "-q")
            frozen = "def work():\n    return 1\n"
            (repo / "sample.py").write_text(frozen)
            (repo / "broken.py").write_text("def broken(:\n")
            git("add", ".")
            git("-c", "user.email=a@b.c", "-c", "user.name=A", "commit", "-qm", "fixture")
            sha = git("rev-parse", "HEAD")
            bundle = write_source_run(root / "out", str(repo), scan(repo, sha))
            verified = verify_git_source(bundle)
            (repo / "sample.py").write_text("raise RuntimeError('dirty worktree')\n")
            plain, contexts, plan = prepare_analysis(verified, mode="plain", symbol="module:sample.py")
            self.assertIsNone(plan)
            self.assertEqual(contexts["symbol:module:sample.py"]["nodes"][0]["source_slice"], frozen)
            self.assertEqual(plain["contexts"], [
                {"scope_id": "symbol:module:sample.py",
                 "sha256": context_hash(contexts["symbol:module:sample.py"])}])
            batch, contexts, _ = prepare_analysis(verified, scope="full")
            self.assertIsNone(contexts["module:broken.py"])
            self.assertEqual(batch["contexts"][0], {"scope_id": "module:broken.py", "sha256": None})
            self.assertTrue(any(node["source_slice"] == frozen
                                for node in contexts["module:sample.py"]["nodes"]))
            with self.assertRaises(ValueError):
                prepare_analysis(verified, mode="single", scope="full")
            with self.assertRaises(ValueError):
                prepare_analysis(verified, symbol="missing_symbol")



    def test_snapshot_and_manifest_bind_single_use_receipt(self):
        manifest = self.manifest()
        digest = manifest_hash(manifest)
        self.assertEqual(digest, manifest_hash(dict(reversed(list(manifest.items())))))
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory) / "approval.json"
            with self.assertRaises(PolicyError):
                issue_approval(manifest, manifest["snapshot_sha"], receipt, "wrong")
            self.assertFalse(receipt.exists())
            issue_approval(manifest, manifest["snapshot_sha"], receipt, digest)
            self.assertEqual(os.stat(receipt).st_mode & 0o077, 0)
            self.assertEqual(verify_approval(manifest, manifest["snapshot_sha"], receipt), digest)
            altered = copy.deepcopy(manifest)
            altered["nodes"][0]["argv"].append("-q")
            with self.assertRaises(PolicyError):
                verify_approval(altered, altered["snapshot_sha"], receipt)
            self.assertEqual(consume_approval(manifest, manifest["snapshot_sha"], receipt), digest)
            with self.assertRaises(PolicyError):
                consume_approval(manifest, manifest["snapshot_sha"], receipt)

    def test_changed_snapshot_and_unpinned_tools_are_denied(self):
        manifest = self.manifest()
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory) / "approval.json"
            with self.assertRaises(PolicyError):
                issue_approval(manifest, "c" * 40, receipt, manifest_hash(manifest))
        manifest["nodes"][0]["argv"] = ["bash", "-c", "echo unsafe"]
        with self.assertRaises(PolicyError):
            manifest_hash(manifest)
        manifest = self.manifest()
        manifest["tools"] = ["cprofile"]
        manifest["nodes"][0].update(tool="cprofile", argv=["python", "-m", "cProfile", "bench.py"])
        self.assertEqual(len(manifest_hash(manifest)), 64)


    def test_declared_model_transmission_requires_explicit_network_permission(self):
        manifest = self.manifest()
        manifest["model"] = {"endpoint": "https://model.example/v1/chat/completions",
                             "name_version": "model-pinned-2026", "prompt_sha256": "c" * 64,
                             "transmitted_data": ["source", "context"]}
        manifest["analysis"] = self.model_analysis()
        with self.assertRaises(PolicyError):
            manifest_hash(manifest)
        manifest["network"]["model"] = True
        self.assertEqual(len(manifest_hash(manifest)), 64)
        manifest["model"]["transmitted_data"] = ["harness_credentials"]
        with self.assertRaises(PolicyError):
            manifest_hash(manifest)


    def test_local_oauth_requires_exact_loopback_and_approved_source(self):
        manifest = self.manifest()
        manifest["model"] = {"endpoint": LOCAL_OAUTH_ENDPOINT, "name_version": "gpt-6-luna",
                             "prompt_sha256": "c" * 64, "transmitted_data": ["source", "context"]}
        manifest["analysis"] = self.model_analysis()
        with self.assertRaises(PolicyError):
            manifest_hash(manifest)
        manifest["network"]["model"] = True
        self.assertEqual(len(manifest_hash(manifest)), 64)
        for endpoint in ("http://localhost:10531/v1/responses",
                         "http://127.0.0.1:10532/v1/responses",
                         "http://127.0.0.1:10531/v1/responses?x=1",
                         "http://0.0.0.0:10531/v1/responses",
                         "http://127.0.0.1:10531/v1/chat/completions"):
            manifest["model"]["endpoint"] = endpoint
            with self.subTest(endpoint=endpoint), self.assertRaises(PolicyError):
                manifest_hash(manifest)

    def test_model_only_manifest_grants_no_executable_node(self):
        manifest = self.manifest()
        manifest["tools"] = []
        manifest["nodes"] = []
        manifest["limits"]["per_node"] = {}
        manifest["network"]["model"] = True
        manifest["model"] = {"endpoint": LOCAL_OAUTH_ENDPOINT, "name_version": "gpt-6-sol",
                             "prompt_sha256": "c" * 64, "transmitted_data": ["source", "context"]}
        manifest["analysis"] = self.model_analysis()
        self.assertEqual(len(manifest_hash(manifest)), 64)
        manifest["tools"] = ["python"]
        with self.assertRaisesRegex(PolicyError, "model-only"):
            manifest_hash(manifest)
        manifest["tools"] = []
        manifest["model"]["endpoint"] = None
        with self.assertRaises(PolicyError):
            manifest_hash(manifest)

    def test_cli_denies_noninteractive_or_in_repository_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            def git(*args):
                return subprocess.run(["git", "-C", str(repo), *args], check=True,
                                      capture_output=True, text=True).stdout.strip()
            git("init", "-q")
            (repo / "worker.py").write_text("pass\n")
            git("add", "worker.py")
            git("-c", "user.email=a@b.c", "-c", "user.name=A", "commit", "-qm", "fixture")
            manifest = self.manifest()
            manifest["snapshot_sha"] = git("rev-parse", "HEAD")
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            command = [sys.executable, str(ROOT / "src" / "approve_run.py"),
                       str(repo), str(manifest_path)]
            outside = root / "approval.json"
            self.assertEqual(subprocess.run([*command, str(outside)], capture_output=True).returncode, 2)
            self.assertFalse(outside.exists())
            self.assertEqual(subprocess.run([*command, str(repo / "approval.json")], capture_output=True).returncode, 2)
            self.assertFalse((repo / "approval.json").exists())

if __name__ == "__main__":
    unittest.main()
