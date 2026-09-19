import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from prguard.gitops import GuardError
from prguard.llm import explain


class OllamaContractTests(unittest.TestCase):
    def test_local_chat_contract_and_schema_validation(self):
        received = []
        replies = [json.dumps({"summary": "기존 변경 원복 위험", "next_steps": ["후보를 검토하세요"]}),
                   json.dumps({"summary": 123, "next_steps": "invalid"})]

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                received.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
                payload = json.dumps({"message": {"content": replies.pop(0)}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            config = {"ollama_url": f"http://127.0.0.1:{server.server_port}"}
            result = {"status": "BLOCK", "findings": [], "candidate_available": False}
            response = explain(result, config)
            self.assertEqual(response["status"], "ok")
            self.assertEqual(response["model"], "gemma3:4b")
            self.assertEqual(received[0][0], "/api/chat")
            self.assertFalse(received[0][1]["stream"])
            self.assertEqual(received[0][1]["format"]["type"], "object")
            self.assertEqual(result["status"], "BLOCK")
            with self.assertRaises(GuardError):
                explain(result, config)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
