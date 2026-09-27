"""Clean-full replay compares static parser facts at one immutable commit."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "modules"))
from static_scan.cache import DISABLED_MARKER, FactsCache, digest  # noqa: E402
from static_scan.orchestrator import scan  # noqa: E402
from static_scan.replay import replay  # noqa: E402


class ScanReplayTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        self.cache = FactsCache(Path(self.temp.name) / "cache")
        subprocess.run(["git", "-C", str(self.repo), "init", "-q"], check=True)
        (self.repo / "pkg.py").write_text("import asyncio\nasync def run():\n    await asyncio.sleep(0)\n")
        self.git("add", "pkg.py")
        self.git("-c", "user.email=test@example.org", "-c", "user.name=Test",
                 "commit", "-qm", "fixture")
        self.commit = self.git("rev-parse", "HEAD")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args],
                              check=True, capture_output=True, text=True).stdout.strip()

    def test_hit_and_matching_replay(self):
        scan(self.repo, self.commit, cache=self.cache)
        result, metadata = replay(self.repo, self.commit, self.cache)
        self.assertEqual(metadata["status"], "match")
        self.assertEqual(metadata["cache_events"][0]["origin"], "hit")
        self.assertEqual(result, scan(self.repo, self.commit))
        self.assertIsNone(self.cache.disabled_reason)

    def test_valid_self_hash_wrong_facts_disables_future_hits(self):
        expected = scan(self.repo, self.commit, cache=self.cache)
        entry = next(self.cache.directory.glob("*.json"))
        envelope = json.loads(entry.read_text())
        envelope["payload"]["flags"]["await"] = False
        payload = json.dumps(envelope["payload"], sort_keys=True, ensure_ascii=True,
                             separators=(",", ":")).encode()
        envelope["payload_sha256"] = digest(payload)
        entry.write_text(json.dumps(envelope))
        result, metadata = replay(self.repo, self.commit, self.cache)
        self.assertEqual(result, expected)
        self.assertEqual(metadata["status"], "mismatch")
        self.assertEqual(metadata["cache_events"][0]["origin"], "hit")
        self.assertEqual(metadata["disabled_reason"], "replay_mismatch")
        self.assertTrue((self.cache.directory / DISABLED_MARKER).exists())
        self.assertTrue(entry.exists())
        self.assertEqual(scan(self.repo, self.commit, cache=FactsCache(self.cache.directory)), expected)
        self.assertEqual(self.cache.events[0]["origin"], "hit")
        fresh = FactsCache(self.cache.directory)
        scan(self.repo, self.commit, cache=fresh)
        self.assertEqual(fresh.events[0]["origin"], "disabled")

    def test_malformed_disable_marker_fails_closed(self):
        self.cache.directory.mkdir()
        (self.cache.directory / DISABLED_MARKER).write_text("not-json")
        result, metadata = replay(self.repo, self.commit, self.cache)
        self.assertEqual(result, scan(self.repo, self.commit))
        self.assertEqual(metadata["status"], "disabled")
        self.assertEqual(metadata["disabled_reason"], "invalid_disabled_marker")
        self.assertEqual(self.cache.events[0]["origin"], "disabled")

    def test_bare_git_repository_replay(self):
        bare = Path(self.temp.name) / "bare.git"
        subprocess.run(["git", "clone", "--bare", "-q", str(self.repo), str(bare)],
                       check=True, capture_output=True)
        result, metadata = replay(bare, self.commit, FactsCache(Path(self.temp.name) / "bare-cache"))
        self.assertEqual(metadata["status"], "match")
        self.assertEqual(result["commit"], self.commit)

    def test_cli_returns_clean_source_after_mismatch(self):
        command = [sys.executable, str(ROOT / "src" / "scan_sources.py"),
                   str(self.repo), self.commit, str(Path(self.temp.name) / "out"),
                   "--cache-dir", str(self.cache.directory)]
        first = subprocess.run([*command, "--clean-replay"], check=True,
                               capture_output=True, text=True)
        self.assertEqual(json.loads(first.stdout)["clean_replay"]["status"], "match")
        entry = next(self.cache.directory.glob("*.json"))
        envelope = json.loads(entry.read_text())
        envelope["payload"]["flags"]["await"] = False
        payload = json.dumps(envelope["payload"], sort_keys=True, ensure_ascii=True,
                             separators=(",", ":")).encode()
        envelope["payload_sha256"] = digest(payload)
        entry.write_text(json.dumps(envelope))
        second = subprocess.run([*command, "--clean-replay"], check=True,
                                capture_output=True, text=True)
        response = json.loads(second.stdout)
        self.assertEqual(response["clean_replay"]["status"], "mismatch")
        self.assertEqual(response["source_bundle"], json.loads(first.stdout)["source_bundle"])
        third = subprocess.run(command, check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(third.stdout)["cache_events"][0]["origin"], "disabled")

    def test_cli_clean_replay_preserves_symbol_context(self):
        command = [sys.executable, str(ROOT / "src" / "scan_sources.py"),
                   str(self.repo), self.commit, str(Path(self.temp.name) / "out"),
                   "--cache-dir", str(self.cache.directory), "--clean-replay",
                   "--symbol", "run"]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        response = json.loads(result.stdout)
        self.assertEqual(response["clean_replay"]["status"], "match")
        self.assertTrue(any(node["name"] == "run" for node in response["context"]["nodes"]))

    def test_repository_local_cache_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside the repository"):
            replay(self.repo, self.commit, FactsCache(self.repo / "cache"))


if __name__ == "__main__":
    unittest.main()
