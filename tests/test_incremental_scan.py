"""Immutable source facts cache behavior across Git snapshots."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "modules"))
from static_scan.cache import FactsCache  # noqa: E402
from static_scan.orchestrator import graph, scan  # noqa: E402


class IncrementalScanTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        self.cache = FactsCache(Path(self.temp.name) / "cache")
        self.git("init", "-q")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def commit(self):
        self.git("add", "-A")
        self.git("-c", "user.email=test@example.org", "-c", "user.name=Test",
                 "commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def test_hit_change_corruption_and_clean_equivalence(self):
        source = self.repo / "pkg.py"
        source.write_text("def first():\n    return 1\n")
        first = self.commit()
        clean = scan(self.repo, first)
        self.assertEqual(scan(self.repo, first, cache=self.cache), clean)
        self.assertEqual(self.cache.events[0]["origin"], "miss")
        artifact = self.cache.events[0]["artifact_sha256"]
        source.write_text("raise RuntimeError('working tree is not source')\n")
        self.assertEqual(scan(self.repo, first, cache=self.cache), clean)
        self.assertEqual(self.cache.events[0]["origin"], "hit")
        self.assertEqual(self.cache.events[0]["artifact_sha256"], artifact)

        second = self.commit()
        self.assertEqual(scan(self.repo, second, cache=self.cache), scan(self.repo, second))
        self.assertEqual(self.cache.events[0]["origin"], "miss")
        entry = next(path for path in self.cache.directory.glob("*.json")
                     if json.loads(path.read_text())["identity"]["source_sha256"]
                     == clean["files"][0]["source_sha256"])
        self.assertNotEqual(self.cache.events[0]["source_sha256"], clean["files"][0]["source_sha256"])

        envelope = json.loads(entry.read_text())
        envelope["payload"]["symbols"] = [{"name": "forged"}]
        entry.write_text(json.dumps(envelope))
        scan(self.repo, first, cache=self.cache)
        self.assertEqual(self.cache.events[0]["origin"], "miss")
        self.assertEqual(scan(self.repo, first, cache=self.cache), clean)
        self.assertEqual(self.cache.events[0]["origin"], "hit")

    def test_graph_uses_cached_facts_without_caching_edges(self):
        (self.repo / "pkg.py").write_text("def first():\n    return 1\n")
        revision = self.commit()
        result, database = graph(self.repo, revision, cache=self.cache)
        try:
            self.assertEqual(result, scan(self.repo, revision))
            self.assertEqual(self.cache.events[0]["origin"], "miss")
        finally:
            database.close()
        result, database = graph(self.repo, revision, cache=self.cache)
        try:
            self.assertEqual(self.cache.events[0]["origin"], "hit")
            self.assertEqual(result, scan(self.repo, revision))
        finally:
            database.close()


    def test_other_repository_and_cli_cache_events(self):
        (self.repo / "pkg.py").write_text("value = 1\n")
        revision = self.commit()
        scan(self.repo, revision, cache=self.cache)
        original_key = self.cache.events[0]["cache_key"]
        second = Path(self.temp.name) / "second"
        second.mkdir()
        subprocess.run(["git", "-C", str(second), "init", "-q"], check=True)
        (second / "pkg.py").write_text("value = 1\n")
        subprocess.run(["git", "-C", str(second), "add", "pkg.py"], check=True)
        subprocess.run(["git", "-C", str(second), "-c", "user.email=a@b.c",
                        "-c", "user.name=A", "commit", "-qm", "fixture"], check=True)
        self.assertEqual(scan(second, "HEAD", cache=self.cache), scan(second, "HEAD"))
        self.assertEqual(self.cache.events[0]["origin"], "miss")
        self.assertNotEqual(self.cache.events[0]["cache_key"], original_key)
        command = [sys.executable, str(ROOT / "src" / "scan_sources.py"), str(self.repo),
                   revision, str(Path(self.temp.name) / "out"), "--cache-dir", str(self.cache.directory)]
        first = subprocess.run(command, check=True, capture_output=True, text=True)
        output = json.loads(first.stdout)
        self.assertEqual(output["cache_events"][0]["origin"], "hit")
        self.assertEqual(output["stage"], "source_scanned")
        denied = subprocess.run([*command[:-1], str(self.repo / "inside")], capture_output=True)
        self.assertEqual(denied.returncode, 2)

if __name__ == "__main__":
    unittest.main()
