import unittest

from starter_kit import adapter
from starter_kit.hybrid_compiler import HybridSyntaxError
from starter_kit.riscv_emulator import TinyRISCVEmulator


HEADER = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
measure q[0] -> c[0];
'''


def run(assembly: str, c0: int = 0, c1: int = 0) -> dict[str, int]:
    emulator = TinyRISCVEmulator()
    emulator.load_program(assembly)
    emulator.set_register("x10", c0)
    emulator.set_register("x11", c1)
    return emulator.execute()


class HybridCompilerTests(unittest.TestCase):
    def test_public_branch_and_quantum_operation_order(self):
        source = HEADER + '''
classical { if (c[0] == 1) { r1 = 7; } else { r1 = 3; } }
cx q[0], q[1];
'''
        operations, assembly = adapter.compile_hybrid(source)
        self.assertEqual(
            operations,
            ["h q[0];", "measure q[0] -> c[0];", "cx q[0], q[1];"],
        )
        self.assertEqual(run(assembly, 0).get("x1"), 3)
        self.assertEqual(run(assembly, 1).get("x1"), 7)

    def test_sequential_arithmetic_and_negative_literal(self):
        source = HEADER + '''classical {
          r1 = 10;
          r2 = -3;
          r1 = r1 + 5 - r2;
        }'''
        _, assembly = adapter.compile_hybrid(source)
        state = run(assembly)
        self.assertEqual(state["x1"], 18)
        self.assertEqual(state["x2"], -3)

    def test_nested_if_else_and_two_measurement_bits(self):
        source = HEADER + '''classical {
          if (c[0] != c[1]) {
            if (c[1] == 1) { r3 = 30; } else { r3 = 20; }
          } else {
            r3 = 10;
          }
          r3 = r3 + 2;
        }'''
        _, assembly = adapter.compile_hybrid(source)
        expected = {(0, 0): 12, (0, 1): 32, (1, 0): 22, (1, 1): 12}
        for measured, value in expected.items():
            with self.subTest(measured=measured):
                self.assertEqual(run(assembly, *measured).get("x3"), value)

    def test_multiple_classical_blocks_preserve_sequence(self):
        source = HEADER + '''
classical { r1 = 2; }
x q[1];
classical { r1 = r1 + 8; }
'''
        operations, assembly = adapter.compile_hybrid(source)
        self.assertEqual(operations[-1], "x q[1];")
        self.assertEqual(run(assembly).get("x1"), 10)

    def test_arithmetic_in_condition_and_register_self_assignment(self):
        source = HEADER + '''classical {
          r1 = 3;
          r1 = r1;
          if (r1 + c[0] == 5 - c[1]) {
            r4 = 91;
          } else {
            r4 = -12;
          }
        }'''
        _, assembly = adapter.compile_hybrid(source)
        expected = {(0, 0): -12, (0, 1): -12, (1, 0): -12, (1, 1): 91}
        for measured, value in expected.items():
            with self.subTest(measured=measured):
                self.assertEqual(run(assembly, *measured).get("x4"), value)

    def test_if_without_else_and_zero_result(self):
        source = HEADER + '''classical {
          r5 = 0;
          if (c[0] == 1) { r5 = r5 + 9; }
        }'''
        _, assembly = adapter.compile_hybrid(source)
        self.assertEqual(run(assembly, 0).get("x5", 0), 0)
        self.assertEqual(run(assembly, 1).get("x5", 0), 9)

    def test_rejects_missing_block_unsupported_syntax_and_bad_qasm(self):
        with self.assertRaisesRegex(HybridSyntaxError, "at least one"):
            adapter.compile_hybrid(HEADER)
        with self.assertRaisesRegex(HybridSyntaxError, "unsupported"):
            adapter.compile_hybrid(HEADER + "classical { r1 = r2 * 3; }")
        with self.assertRaises(Exception):
            adapter.compile_hybrid(HEADER.replace("h q[0]", "z q[0]") + "classical { r1 = 1; }")


if __name__ == "__main__":
    unittest.main()
