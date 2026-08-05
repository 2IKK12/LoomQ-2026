import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from starter_kit.web_app import LoomQHandler


BELL = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
'''


class WebAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), LoomQHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_index_and_assets_are_served(self):
        with urllib.request.urlopen(self.base + "/", timeout=2) as response:
            body = response.read().decode()
        self.assertIn("说出你的想法", body)
        self.assertIn("/styles.css", body)
        with urllib.request.urlopen(self.base + "/app.js", timeout=2) as response:
            self.assertIn("javascript", response.headers["Content-Type"])

    def test_run_endpoint_executes_l1(self):
        request = urllib.request.Request(
            self.base + "/api/run",
            data=json.dumps({"qasm": BELL, "target": "braket", "shots": 100}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            payload = json.loads(response.read())
        self.assertEqual(payload["result"]["counts"], {"00": 50, "11": 50})
        self.assertEqual(payload["result"]["bit_order"], "little")

    def test_unknown_file_is_not_exposed(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(self.base + "/../adapter.py", timeout=2)
        self.assertEqual(caught.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
