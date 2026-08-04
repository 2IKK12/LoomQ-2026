import unittest
from unittest import mock

from starter_kit import adapter
from starter_kit import loomq_agent


def response(content: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


VALID_BELL = """Here is the circuit.
```qasm
OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
```
Expected results are 00 and 11 with equal probability.
"""


class L2AgentTests(unittest.TestCase):
    @mock.patch("starter_kit.loomq_agent.chat_completion")
    def test_valid_qasm_is_returned_after_one_model_call(self, complete):
        complete.return_value = response(VALID_BELL)
        answer = adapter.agent_chat("Create a Bell state")
        self.assertIn("OPENQASM 2.0;", answer)
        complete.assert_called_once()

    @mock.patch("starter_kit.loomq_agent.chat_completion")
    def test_invalid_qasm_is_repaired_using_l1_feedback(self, complete):
        invalid = """```qasm
OPENQASM 2.0;
include "qelib1.inc";
qreg q[2]; creg c[2];
H q[0]; CX q[0] q[1]; measure q -> c;
```"""
        complete.side_effect = [response(invalid), response(VALID_BELL)]
        answer = adapter.agent_chat("Repair my Bell-state circuit")
        self.assertIn("cx q[0], q[1];", answer)
        self.assertEqual(complete.call_count, 2)
        repair_message = complete.call_args_list[1].args[0][-1]["content"]
        self.assertIn("validator", repair_message)

    @mock.patch("starter_kit.loomq_agent.chat_completion")
    def test_backend_answer_does_not_require_qasm(self, complete):
        complete.return_value = response(
            "For 15 qubits and no queue, use `originq_local_simulator`."
        )
        answer = adapter.agent_chat("I need 15 qubits with zero queue")
        self.assertIn("originq_local_simulator", answer)
        complete.assert_called_once()

    @mock.patch("starter_kit.loomq_agent.chat_completion")
    def test_prompt_contains_machine_readable_backend_records(self, complete):
        complete.return_value = response("Use `braket_local_simulator`.")
        adapter.agent_chat("Recommend a free local backend")
        system = complete.call_args.args[0][0]["content"]
        self.assertIn('"id":"braket_local_simulator"', system)
        self.assertIn('"max_qubits":25', system)

    @mock.patch("starter_kit.loomq_agent.chat_completion")
    def test_invalid_api_shape_has_safe_error(self, complete):
        complete.return_value = {"unexpected": True}
        with self.assertRaisesRegex(RuntimeError, "invalid response shape"):
            adapter.agent_chat("Create a Bell state")


if __name__ == "__main__":
    unittest.main()
