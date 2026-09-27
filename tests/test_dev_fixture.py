"""Development fixture oracles must distinguish clean from each seeded defect."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = {"clean": None, "correctness": "test_page_boundary",
         "performance": "test_linear_operation_bound",
         "concurrency": "test_event_loop_progress",
         "cancellation": "test_cancellation_propagates",
         "api_contract": "test_missing_item_is_404",
         "cross_file": "test_cross_file_normalization"}


@unittest.skipUnless(importlib.util.find_spec("fastapi") and importlib.util.find_spec("httpx"),
                     "Install fixtures/development/requirements.txt to run the development oracles")
class DevelopmentFixtureTest(unittest.TestCase):
    def test_clean_and_each_seeded_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            for mutation, failing_oracle in CASES.items():
                with self.subTest(mutation=mutation):
                    output = subprocess.run([sys.executable, str(ROOT / "src" / "build_dev_fixture.py"),
                                             str(Path(directory) / mutation), "--mutation", mutation],
                                            capture_output=True, text=True, check=True)
                    record = json.loads(output.stdout)
                    self.assertEqual(record["lane"], "development_only")
                    observed = subprocess.run([sys.executable, "-m", "unittest", "oracle", "-q"],
                                              cwd=record["repository"], capture_output=True,
                                              text=True, timeout=15)
                    if failing_oracle is None:
                        self.assertEqual(observed.returncode, 0, observed.stderr)
                    else:
                        self.assertEqual(observed.returncode, 1, observed.stderr)
                        self.assertIn(failing_oracle, observed.stderr)
                        self.assertIn("Ran 6 tests", observed.stderr)
                        self.assertIn("failures=1", observed.stderr)
