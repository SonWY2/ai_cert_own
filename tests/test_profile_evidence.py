"""Trusted local cProfile artifacts remain unattested runtime summaries."""

import cProfile
import json
import hashlib
import marshal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from modules.evidence.profile import normalize_trusted_pstats  # noqa: E402
from modules.evidence.provenance import write_source_run  # noqa: E402
from modules.static_scan.orchestrator import scan  # noqa: E402

COMMIT = "a" * 40
MANIFEST = "b" * 64


class ProfileEvidenceTest(unittest.TestCase):
    def bundle(self, tmp):
        return write_source_run(tmp / "evidence", "example", {
            "commit": COMMIT, "python_parser": "3.14", "files": [{
                "path": "sample.py", "source_sha256": "c" * 64,
                "blob_oid": "d" * 40, "symbols": [], "symbol_table_names": [],
                "imports": [], "flags": {},
            }],
        })

    def summarize(self, artifact, source, **overrides):
        args = dict(artifact=artifact, source_bundle=source, snapshot_sha=COMMIT,
                    command_argv=["python", "sample.py"], manifest_hash=MANIFEST,
                    node_id="profile", trusted_artifact=True)
        args.update(overrides)
        return normalize_trusted_pstats(**args)

    def test_trusted_summary_is_sorted_and_unmapped_paths_stay_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.bundle(root)
            artifact = root / "profile.pstats"
            profiler = cProfile.Profile()
            profiler.enable()
            sum(range(100))
            profiler.disable()
            profiler.dump_stats(str(artifact))

            summary = self.summarize(artifact, source)
            self.assertEqual(summary["source_run_id"], source.name)
            self.assertEqual(summary["artifact_sha256"], hashlib.sha256(artifact.read_bytes()).hexdigest())
            self.assertEqual(summary["provenance"], "caller_declared_unattested")
            self.assertTrue(summary["hotspots"])
            self.assertTrue(all(row["file_mapping"] == "unknown" and row["file"] is None
                                for row in summary["hotspots"]))
            self.assertEqual(summary["hotspots"], sorted(summary["hotspots"], key=lambda row: (
                -row["cumulative_seconds"], -row["self_seconds"], row["profiler_file"],
                row["line"], row["function"])))

    def test_exact_relative_source_path_maps_without_claiming_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.bundle(root)
            artifact = root / "profile.pstats"
            artifact.write_bytes(marshal.dumps({("sample.py", 1, "work"): (1, 2, 0.1, 0.2, {})}))
            row = self.summarize(artifact, source)["hotspots"][0]
            self.assertEqual((row["file"], row["file_mapping"], row["calls"]),
                             ("sample.py", "resolved", 2))

    def test_selected_trusted_hotspot_locates_only_matching_git_function(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            def git(*args):
                return subprocess.run(["git", "-C", str(repo), *args], check=True,
                                      capture_output=True, text=True).stdout.strip()
            git("init", "-q")
            (repo / "sample.py").write_text(
                "if True:\n    @dec\n    def work():\n        return 1\n")
            git("add", "sample.py")
            git("-c", "user.name=A", "-c", "user.email=a@b.c", "commit", "-qm", "frozen")
            commit = git("rev-parse", "HEAD")
            bundle = write_source_run(root / "out", str(repo), scan(repo, commit))
            limits = {"wall_seconds": 30, "cpu_seconds": 30, "memory_bytes": 1048576,
                      "tokens": 100, "tool_seconds": 30}
            manifest = {"schema_version": "run-manifest-v3", "snapshot_sha": commit,
                        "analysis": None,
                        "image_digest": "sha256:" + "c" * 64, "tools": ["cprofile"],
                        "nodes": [{"id": "profile", "argv": ["python", "-m", "cProfile", "sample.py"],
                                   "cwd": "/workspace", "workload": "sample.py",
                                   "trigger": "local slowdown", "tool": "cprofile"}],
                        "limits": {**limits, "per_node": {"profile": limits}},
                        "network": {"dependency": False, "model": False, "workload": False},
                        "writable_paths": ["/work/evidence"],
                        "model": {"endpoint": None, "name_version": None,
                                  "prompt_sha256": None, "transmitted_data": []}}
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            artifact = root / "profile.pstats"
            artifact.write_bytes(marshal.dumps({
                ("sample.py", 2, "work"): (1, 1, 0.2, 0.2, {}),
                ("/other/sample.py", 1, "work"): (1, 1, 0.1, 0.1, {})}))
            (repo / "sample.py").write_text("raise RuntimeError('worktree')\n")
            command = [sys.executable, str(ROOT / "src" / "summarize_profile.py"),
                       str(bundle), str(manifest_path), "profile", str(artifact),
                       "--trusted-local-artifact"]
            located = subprocess.run([*command, "--hotspot-index", "0"],
                                     capture_output=True, text=True)
            self.assertEqual(located.returncode, 0, located.stderr)
            result = json.loads(located.stdout)
            self.assertEqual(result["provenance"], "caller_declared_unattested")
            self.assertEqual(result["hotspot_context"]["frame"]["node_id"],
                             "function:sample.py:work:3")
            self.assertEqual(result["hotspot_context"]["nodes"][0]["source_slice"],
                             "    @dec\n    def work():\n        return 1\n")
            self.assertNotIn("worktree", located.stdout)
            denied = subprocess.run([*command, "--hotspot-index", "1"],
                                    capture_output=True, text=True)
            self.assertEqual(denied.returncode, 2)
            self.assertIn("not mapped", denied.stderr)
            for key, expected in ((("sample.py", 2, "other"), "matching Git function"),
                                  (("sample.py", 3, "work"), "matching Git function"),
                                  (("sample.py", 4, "work"), "matching Git function"),
                                  (("sample.py", 1, "work"), "matching Git function"),
                                  (("sample.py", 9, "work"), "frame must identify")):
                artifact.write_bytes(marshal.dumps({key: (1, 1, 0.1, 0.1, {})}))
                denied = subprocess.run([*command, "--hotspot-index", "0"],
                                        capture_output=True, text=True)
                self.assertEqual(denied.returncode, 2)
                self.assertIn(expected, denied.stderr)
            self.assertEqual(subprocess.run([*command, "--hotspot-index", "-1"],
                                            capture_output=True).returncode, 2)
            artifact.write_bytes(marshal.dumps({("sample.py", 2, "work"): (1, 1, 0.1, 0.1, {})}))
            forged = scan(repo, commit)
            forged["files"][0]["source_sha256"] = "0" * 64
            fake_bundle = write_source_run(root / "out", str(repo), forged)
            rejected = subprocess.run([command[0], command[1], str(fake_bundle),
                                       *command[3:], "--hotspot-index", "0"],
                                      capture_output=True, text=True)
            self.assertEqual(rejected.returncode, 2)
            self.assertIn("Git commit", rejected.stderr)

    def test_cli_requires_explicit_trust_and_declared_profile_node(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.bundle(root)
            artifact = root / "profile.pstats"
            artifact.write_bytes(marshal.dumps({("sample.py", 1, "work"): (1, 1, 0.1, 0.1, {})}))
            bounds = {"wall_seconds": 30, "cpu_seconds": 30, "memory_bytes": 1048576,
                      "tokens": 100, "tool_seconds": 30}
            manifest = {"schema_version": "run-manifest-v3", "snapshot_sha": COMMIT,
                        "analysis": None,
                        "image_digest": "sha256:" + "c" * 64, "tools": ["cprofile"],
                        "nodes": [{"id": "profile", "argv": ["python", "-m", "cProfile", "sample.py"],
                                   "cwd": "/workspace", "workload": "sample.py",
                                   "trigger": "measured slowdown", "tool": "cprofile"}],
                        "limits": {**bounds, "per_node": {"profile": bounds}},
                        "network": {"dependency": False, "model": False, "workload": False},
                        "writable_paths": ["/work/evidence"],
                        "model": {"endpoint": None, "name_version": None,
                                  "prompt_sha256": None, "transmitted_data": []}}
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            command = [sys.executable, str(ROOT / "src" / "summarize_profile.py"),
                       str(source), str(manifest_path), "profile", str(artifact)]
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)
            run = subprocess.run([*command, "--trusted-local-artifact"], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)["provenance"], "caller_declared_unattested")
            manifest["nodes"][0]["tool"] = "python"
            manifest_path.write_text(json.dumps(manifest))
            self.assertEqual(subprocess.run([*command, "--trusted-local-artifact"],
                                            capture_output=True).returncode, 2)

    def test_rejects_untrusted_corrupt_and_mismatched_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.bundle(root)
            artifact = root / "invalid.pstats"
            artifact.write_bytes(b"not a pstats file")
            with self.assertRaisesRegex(ValueError, "trusted_artifact"):
                self.summarize(artifact, source, trusted_artifact=False)
            with self.assertRaisesRegex(ValueError, "Snapshot SHA"):
                self.summarize(artifact, source, snapshot_sha="e" * 40)
            with self.assertRaisesRegex(ValueError, "Invalid pstats"):
                self.summarize(artifact, source)
            (source / "run.json").write_bytes(b"corrupted")
            with self.assertRaises(ValueError):
                self.summarize(artifact, source)


if __name__ == "__main__":
    unittest.main()
