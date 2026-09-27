"""Owner choices remain append-only and distinct from deferred evidence."""

import json
import multiprocessing
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from modules.evidence.provenance import write_source_run  # noqa: E402
from modules.findings.actions import append_action, read_actions  # noqa: E402
from modules.findings.admission import admit, priority_rows  # noqa: E402


def fixture(root):
    bundle = write_source_run(root / "evidence", str(root / "repo"), {
        "commit": "a" * 40, "python_parser": "3.14", "files": [{
            "path": "sample.py", "source_sha256": "b" * 64, "blob_oid": "c" * 40,
            "symbols": [], "symbol_table_names": [], "imports": [], "flags": {},
        }],
    })
    evidence_id = json.loads((bundle / "evidence.jsonl").read_text())["id"]
    findings = admit(bundle, [{"root_symbol": "sample.fn", "mechanism": "failure",
                               "condition": "called", "impact": "exception", "trigger": "call",
                               "taxonomy": "correctness", "severity": "High",
                               "location": {"path": "sample.py", "line": 1},
                               "evidence_ids": [evidence_id],
                               "next_action": {"action": "inspect", "oracle": "reproduces",
                                               "time_minutes": 5}}])
    directory = root / "owner"
    directory.mkdir(mode=0o700)
    return bundle, findings, directory


def concurrent_append(args):
    append_action(*args)


class UserActionsTest(unittest.TestCase):
    def test_explicit_latest_actions_do_not_change_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle, findings, owner = fixture(Path(directory))
            finding_id = findings[0]["id"]
            self.assertEqual(read_actions(bundle, findings, owner), {})
            self.assertIsNone(priority_rows(findings)[0]["user_action"])
            for action in ("verify", "fix", "accept_risk", "dismiss"):
                record = append_action(bundle, findings, finding_id, action, owner, True)
                self.assertEqual(record["action"], action)
                self.assertEqual(read_actions(bundle, findings, owner), {finding_id: action})
            row = priority_rows(findings, actions=read_actions(bundle, findings, owner))[0]
            self.assertEqual((row["user_action"], row["evidence_status"]), ("dismiss", "deferred"))
            self.assertEqual(sorted(bundle.iterdir()), sorted([bundle / "run.json", bundle / "evidence.jsonl"]))
            log = next(owner.iterdir())
            self.assertEqual(log.stat().st_mode & 0o777, 0o600)
            self.assertEqual(len(log.read_text().splitlines()), 4)

    def test_different_current_scope_keeps_other_actions_in_history(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle, findings, owner = fixture(Path(directory))
            first = findings[0]
            candidate = {key: first[key] for key in ("root_symbol", "mechanism", "condition",
                         "impact", "trigger", "taxonomy", "severity", "location",
                         "evidence_ids", "next_action")}
            candidate["root_symbol"] = "other.fn"
            other = admit(bundle, [candidate])[0]
            append_action(bundle, findings, first["id"], "verify", owner, True)
            append_action(bundle, [other], other["id"], "fix", owner, True)
            self.assertEqual(read_actions(bundle, findings, owner), {first["id"]: "verify"})
            self.assertEqual(read_actions(bundle, [other], owner), {other["id"]: "fix"})

    def test_rejects_unconfirmed_wrong_finding_repository_and_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, findings, owner = fixture(root)
            finding_id = findings[0]["id"]
            with self.assertRaisesRegex(ValueError, "confirmation"):
                append_action(bundle, findings, finding_id, "dismiss", owner, False)
            with self.assertRaisesRegex(ValueError, "Unknown"):
                append_action(bundle, findings, "Funknown", "verify", owner, True)
            with self.assertRaises(ValueError):
                append_action(bundle, [{**findings[0], "repository": "other"}], finding_id, "verify", owner, True)
            with self.assertRaises(ValueError):
                append_action(bundle, [{**findings[0], "evidence_ids": ["other-run"]}],
                              finding_id, "verify", owner, True)
            with self.assertRaisesRegex(ValueError, "outside"):
                append_action(bundle, findings, finding_id, "verify", bundle, True)
            (root / "repo").mkdir()
            (root / "repo" / "inside").mkdir(mode=0o700)
            with self.assertRaisesRegex(ValueError, "outside"):
                append_action(bundle, findings, finding_id, "verify", root / "repo" / "inside", True)

    def test_corrupt_log_is_not_rewritten(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle, findings, owner = fixture(Path(directory))
            finding_id = findings[0]["id"]
            append_action(bundle, findings, finding_id, "verify", owner, True)
            log = next(owner.iterdir())
            original = log.read_bytes() + b"{broken\n"
            log.write_bytes(original)
            with self.assertRaises(ValueError):
                read_actions(bundle, findings, owner)
            with self.assertRaises(ValueError):
                append_action(bundle, findings, finding_id, "fix", owner, True)
            self.assertEqual(log.read_bytes(), original)
            run = bundle / "run.json"
            run.write_bytes(run.read_bytes().replace(b"source_scanned", b"source_changed"))
            with self.assertRaises(ValueError):
                read_actions(bundle, findings, owner)

    def test_concurrent_appends_preserve_each_record(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle, findings, owner = fixture(Path(directory))
            args = (bundle, findings, findings[0]["id"], "verify", owner, True)
            processes = [multiprocessing.Process(target=concurrent_append, args=(args,)) for _ in range(8)]
            for process in processes:
                process.start()
            for process in processes:
                process.join(timeout=10)
                self.assertEqual(process.exitcode, 0)
            self.assertEqual(len(next(owner.iterdir()).read_text().splitlines()), len(processes))
            self.assertEqual(read_actions(bundle, findings, owner), {findings[0]["id"]: "verify"})


if __name__ == "__main__":
    unittest.main()
