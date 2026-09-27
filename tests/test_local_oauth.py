"""Local OAuth transport accounts for cache tokens and rejects mismatched replies."""

import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from modules.diagnosis import model  # noqa: E402
from modules.diagnosis.plan import context_hash  # noqa: E402


class LocalOAuthTest(unittest.TestCase):
    def test_real_loopback_http_response_and_cache_accounting(self):
        received = []
        reply = {"model": "gpt-6-luna", "status": "completed",
                 "output": [{"type": "message", "role": "assistant",
                             "content": [{"type": "output_text", "text": '{"candidates": []}'}]}],
                 "usage": {"input_tokens": 15, "output_tokens": 4, "total_tokens": 19,
                           "input_tokens_details": {"cached_tokens": 5}}}

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                received.append((self.path, dict(self.headers), json.loads(body)))
                encoded = json.dumps(reply).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, *args):
                pass

        with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            endpoint = f"http://127.0.0.1:{server.server_port}/v1/responses"
            payload = {"model": "gpt-6-luna", "instructions": "audit",
                       "input": [{"role": "user", "content": "sample"}],
                       "max_output_tokens": 50, "store": False, "stream": False}
            try:
                with patch.object(model, "LOCAL_OAUTH_ENDPOINT", endpoint):
                    response = model._request(endpoint, payload, 2)
                    self.assertEqual(response["usage"], {"input_tokens": 10,
                                     "cache_read_input_tokens": 5, "output_tokens": 4})
                    self.assertEqual(response["stop_reason"], "end_turn")
                    self.assertEqual(json.loads(response["content"][0]["text"]), {"candidates": []})
                    self.assertEqual(received[0][0], "/v1/responses")
                    self.assertEqual(received[0][2], payload)
                    self.assertNotIn("X-Api-Key", received[0][1])
                    reply["model"] = "different-model"
                    with self.assertRaisesRegex(ValueError, "provider_envelope_invalid"):
                        model._request(endpoint, payload, 2)
                    reply["model"] = "gpt-6-luna"
                    reply["usage"]["input_tokens_details"]["cached_tokens"] = 16
                    with self.assertRaisesRegex(ValueError, "usage_invalid"):
                        model._request(endpoint, payload, 2)
                    reply["usage"]["input_tokens_details"]["cached_tokens"] = 5
                    reply["status"] = "incomplete"
                    reply["output"] = []
                    incomplete = model._request(endpoint, payload, 2)
                    self.assertEqual(incomplete["stop_reason"], "incomplete")
                    self.assertEqual(incomplete["content"], [])
                    self.assertEqual(incomplete["usage"]["output_tokens"], 4)
                    reply["status"] = "completed"
                    reply["output"] = [{"type": "message", "role": "assistant",
                                        "content": [{"type": "output_text",
                                                     "text": '{"candidates": []}'}]}]
                    context = {"nodes": [{"path": "case.py", "source_sha256": "a" * 64,
                                          "source_slice": "def f(): return 1\n"}],
                               "edges": [], "truncated": False}
                    evidence = [{"path": "case.py", "source_sha256": "a" * 64, "id": "source-1"}]
                    manifest = {"schema_version": "run-manifest-v3",
                                "model": {"endpoint": endpoint, "name_version": "gpt-6-luna",
                                          "prompt_sha256": model.prompt_hash("five"),
                                          "transmitted_data": ["source", "context"]},
                                "network": {"model": True},
                                "limits": {"tokens": 5000, "wall_seconds": 20}}
                    manifest["analysis"] = {
                        "mode": "five", "roles": list(model.PERSPECTIVES), "scope": "full",
                        "symbol": None, "base_sha": None, "context_policy": "git-ast-context-v1",
                        "contexts": [{"scope_id": "full", "sha256": context_hash(context)}]}
                    candidates, audit = model.analyze(context, evidence, manifest)
                    self.assertEqual(candidates, [])
                    self.assertEqual([row["status"] for row in audit], ["completed"] * 5)
                    self.assertEqual([row["tokens"] for row in audit], [19] * 5)
                    self.assertEqual([json.loads(item[2]["input"][0]["content"])["perspective"]
                                      for item in received[4:]], list(model.PERSPECTIVES))
                    self.assertTrue(all(item[2]["store"] is False and item[2]["stream"] is False
                                        for item in received[4:]))
            finally:
                server.shutdown()
                worker.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
