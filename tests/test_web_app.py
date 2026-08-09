import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

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
        self.assertIn("不需要知道该问什么", body)
        self.assertIn("今天想体验什么", body)
        self.assertIn("theme-toggle", body)
        self.assertNotIn("高中 / 大学生", body)
        self.assertNotIn("未来可连接", body)
        self.assertIn('id="translation-proof" class="translation-proof hidden" open', body)
        self.assertIn('<details id="conversation-panel" class="conversation-panel hidden">', body)
        self.assertIn('href="styles.css"', body)
        with urllib.request.urlopen(self.base + "/app.js", timeout=2) as response:
            app = response.read().decode()
            self.assertIn("javascript", response.headers["Content-Type"])
        self.assertIn("code.trim()", app)
        self.assertNotIn("OPENQASM\\s+2(?:\\.0)?;[\\s\\S]*$", app)

    def test_health_endpoint_reports_closed_loop_api(self):
        with urllib.request.urlopen(self.base + "/api/health", timeout=2) as response:
            payload = json.loads(response.read())
        self.assertEqual(payload, {"service": "LoomQ", "api_version": "closed-loop-4"})

    @mock.patch("starter_kit.web_app.agent_chat_with_history")
    def test_chat_returns_real_l1_translation_evidence(self, chat):
        chat.return_value = f"这是 Bell 实验。\n```qasm\n{BELL}\n```"
        request = urllib.request.Request(
            self.base + "/api/chat",
            data=json.dumps({"prompt": "创建 Bell 实验", "history": []}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            payload = json.loads(response.read())
        evidence = payload["translations"]
        self.assertFalse(evidence["vendor_execution_verified"])
        self.assertEqual({item["target"] for item in evidence["targets"]}, {"braket", "originq", "spinq"})
        self.assertTrue(all(item["status"] == "generated_from_shared_ir" for item in evidence["targets"]))
        self.assertIn("OPENQASM 3.0", next(item["output"] for item in evidence["targets"] if item["target"] == "braket"))
        self.assertIn("QINIT 2", next(item["output"] for item in evidence["targets"] if item["target"] == "originq"))

    @mock.patch("starter_kit.web_app.agent_chat_with_history")
    def test_chat_endpoint_forwards_recent_conversation(self, chat):
        chat.return_value = "继续回答当前实验，不生成新电路。"
        history = [
            {"role": "user", "content": "什么是纠缠？"},
            {"role": "assistant", "content": "它表示多个量子状态之间的整体关联。"},
        ]
        request = urllib.request.Request(
            self.base + "/api/chat",
            data=json.dumps({"prompt": "那为什么不能用它超光速通信？", "history": history}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            payload = json.loads(response.read())
        self.assertEqual(payload["reply"], chat.return_value)
        self.assertIsNone(payload["qasm"])
        chat.assert_called_once_with("那为什么不能用它超光速通信？", history)

    def test_run_endpoint_executes_l1(self):
        request = urllib.request.Request(
            self.base + "/api/run",
            data=json.dumps({"qasm": BELL, "target": "braket", "shots": 2000}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            payload = json.loads(response.read())
        result = payload["result"]
        self.assertEqual(set(result["counts"]), {"00", "11"})
        self.assertEqual(sum(result["counts"].values()), 2000)
        self.assertGreater(result["counts"]["00"], 800)
        self.assertLess(result["counts"]["00"], 1200)
        self.assertEqual(result["meta"]["sampling"], "independent_shots")
        self.assertEqual(payload["result"]["bit_order"], "little")

    def test_unknown_file_is_not_exposed(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(self.base + "/../adapter.py", timeout=2)
        self.assertEqual(caught.exception.code, 404)

    @mock.patch("starter_kit.web_app.explain_experiment_result")
    def test_run_can_return_ai_explanation_grounded_in_context(self, explain):
        explain.return_value = "这是对本次 Bell 实验真实 counts 的解释。"
        request = urllib.request.Request(
            self.base + "/api/run",
            data=json.dumps(
                {
                    "qasm": BELL,
                    "target": "braket",
                    "shots": 100,
                    "explain": True,
                    "prompt": "创建一个 Bell 关联实验",
                    "agent_reply": "将运行 h 和 cx。",
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            payload = json.loads(response.read())
        self.assertEqual(payload["explanation"], explain.return_value)
        explain.assert_called_once()
        self.assertEqual(explain.call_args.args[0], "创建一个 Bell 关联实验")
        self.assertEqual(sum(payload["result"]["counts"].values()), 100)

    @mock.patch("starter_kit.web_app.explain_experiment_result")
    def test_follow_up_reuses_same_experiment_result(self, explain):
        explain.return_value = "继续围绕同一次 Bell 实验解释。"
        prior = {
            "backend": "braket_local_statevector",
            "shots": 100,
            "counts": {"00": 47, "11": 53},
            "bit_order": "little",
            "meta": {"qubits": 2},
        }
        request = urllib.request.Request(
            self.base + "/api/explain",
            data=json.dumps(
                {
                    "prompt": "创建 Bell 态",
                    "qasm": BELL,
                    "result": prior,
                    "agent_reply": "Bell 实验设计",
                    "previous_explanation": "第一次解释",
                    "question": "为什么会这样？",
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            payload = json.loads(response.read())
        self.assertEqual(payload["explanation"], explain.return_value)
        self.assertEqual(explain.call_args.kwargs["follow_up"], "为什么会这样？")
        self.assertEqual(explain.call_args.kwargs["previous_explanation"], "第一次解释")

    @mock.patch("starter_kit.web_app.explain_experiment_result")
    def test_run_result_survives_explanation_failure(self, explain):
        explain.side_effect = RuntimeError("model unavailable")
        request = urllib.request.Request(
            self.base + "/api/run",
            data=json.dumps(
                {
                    "qasm": BELL,
                    "target": "braket",
                    "shots": 100,
                    "explain": True,
                    "prompt": "创建 Bell 态",
                    "agent_reply": "Bell 实验设计",
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            payload = json.loads(response.read())
        self.assertEqual(sum(payload["result"]["counts"].values()), 100)
        self.assertNotIn("explanation", payload)
        self.assertIn("model unavailable", payload["explanation_error"])


if __name__ == "__main__":
    unittest.main()
