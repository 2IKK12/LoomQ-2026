import math
import unittest

from starter_kit import adapter
from starter_kit.loomq_l1 import QASMError, parse_qasm


def program(body: str, qubits: int = 3, bits: int | None = None) -> str:
    bits = qubits if bits is None else bits
    return f'''OPENQASM 2.0;
include "qelib1.inc";
qreg q[{qubits}];
creg c[{bits}];
{body}
'''


class L1ParserTests(unittest.TestCase):
    def test_all_whitelisted_gates_and_angle_expressions_parse(self):
        source = program(
            """
            h q[0]; x q[0]; s q[0]; sdg q[0]; t q[0]; tdg q[0];
            rz(-pi/2 + pi/4) q[0]; ry(2*pi/3) q[1];
            cx q[0], q[1]; cu1(pi/7) q[0], q[2];
            swap q[1], q[2]; ccx q[0], q[1], q[2];
            measure q -> c;
            """
        )
        circuit = parse_qasm(source)
        self.assertEqual(len(circuit.operations), 12)
        self.assertAlmostEqual(circuit.operations[6].parameter, -math.pi / 4)

    def test_multiple_registers_are_flattened_without_changing_bit_order(self):
        source = """OPENQASM 2.0;
        include "qelib1.inc";
        qreg left[1]; qreg right[2];
        creg low[1]; creg high[2];
        x left[0]; x right[1];
        measure left[0] -> low[0];
        measure right[0] -> high[0];
        measure right[1] -> high[1];
        """
        result = adapter.run(source, "spinq", 32)
        self.assertEqual(result["counts"], {"101": 32})

    def test_comments_and_barriers_are_accepted(self):
        source = program(
            """// prepare a state
            h q[0]; /* no-op scheduling marker */ barrier q;
            measure q -> c;
            """
        )
        self.assertEqual(len(parse_qasm(source).operations), 1)

    def test_rejects_non_whitelist_gate_and_unsafe_parameter(self):
        with self.assertRaisesRegex(QASMError, "outside the 12-gate whitelist"):
            parse_qasm(program("z q[0]; measure q -> c;"))
        with self.assertRaisesRegex(QASMError, "unsupported gate parameter"):
            parse_qasm(program("ry(__import__('os')) q[0]; measure q -> c;"))

    def test_rejects_invalid_indices_and_shots(self):
        with self.assertRaisesRegex(QASMError, "index out of range"):
            parse_qasm(program("x q[9]; measure q -> c;"))
        with self.assertRaisesRegex(ValueError, "positive integer"):
            adapter.run(program("measure q -> c;"), "spinq", 0)


class L1TranspilerTests(unittest.TestCase):
    def setUp(self):
        self.source = program(
            "h q[0]; cu1(pi/2) q[0], q[1]; cx q[0], q[2]; measure q -> c;"
        )

    def test_spinq_is_complete_openqasm_2(self):
        output = adapter.transpile(self.source, "spinq")
        self.assertIn("OPENQASM 2.0;", output)
        self.assertIn("qreg q[3];", output)
        self.assertIn("measure q[2] -> c[2];", output)

    def test_braket_uses_openqasm_3_standard_gate_names(self):
        output = adapter.transpile(self.source, "braket")
        self.assertIn("OPENQASM 3.0;", output)
        self.assertIn("cp(", output)
        self.assertIn("cnot q[0], q[2];", output)
        self.assertIn("c[0] = measure q[0];", output)

    def test_originq_uses_contract_gate_names(self):
        output = adapter.transpile(self.source, "originq")
        self.assertTrue(output.startswith("QINIT 3\nCREG 3\n"))
        self.assertIn("CU1(", output)
        self.assertIn("CNOT q[0], q[2]", output)
        self.assertIn("MEASURE q[2], c[2]", output)

    def test_rejects_unknown_target(self):
        with self.assertRaisesRegex(ValueError, "unsupported target"):
            adapter.transpile(self.source, "unknown")


class L1SimulatorTests(unittest.TestCase):
    def assert_counts(self, body: str, expected: dict[str, int], shots: int = 100):
        for target in ("spinq", "originq", "braket"):
            with self.subTest(target=target):
                result = adapter.run(program(body), target, shots)
                self.assertEqual(result["counts"], expected)
                self.assertEqual(sum(result["counts"].values()), shots)
                self.assertEqual(result["bit_order"], "little")
                self.assertNotIn("is_mock", result["meta"])

    def test_x_and_swap(self):
        self.assert_counts("x q[0]; swap q[0], q[2]; measure q -> c;", {"100": 100})

    def test_ccx(self):
        self.assert_counts("x q[0]; x q[1]; ccx q[0], q[1], q[2]; measure q -> c;", {"111": 100})

    def test_ry_pi(self):
        self.assert_counts("ry(pi) q[1]; measure q -> c;", {"010": 100})

    def test_phase_family_cancels(self):
        self.assert_counts(
            "x q[0]; s q[0]; sdg q[0]; t q[0]; tdg q[0]; rz(2*pi) q[0]; measure q -> c;",
            {"001": 100},
        )

    def test_cu1_preserves_bell_measurement_distribution(self):
        source = program("h q[0]; cx q[0], q[1]; cu1(pi/3) q[0], q[1]; measure q -> c;")
        for target in ("spinq", "originq", "braket"):
            with self.subTest(target=target):
                result = adapter.run(source, target, 10_000)
                self.assertEqual(set(result["counts"]), {"000", "011"})
                self.assertEqual(sum(result["counts"].values()), 10_000)
                self.assertGreater(result["counts"]["000"], 4_500)
                self.assertLess(result["counts"]["000"], 5_500)
                self.assertEqual(result["meta"]["sampling"], "independent_shots")


if __name__ == "__main__":
    unittest.main()
