import unittest

from starter_kit.quantum_riscv import (
    CUSTOM_0_OPCODE,
    compile_qasm_to_custom_words,
    decode_quantum_instruction,
    qcx,
    qh,
    qinit,
    qmeasure,
    qx,
)
from starter_kit.riscv_emulator import TinyRISCVEmulator


BELL = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
'''


class QuantumRISCVTests(unittest.TestCase):
    def test_encoding_round_trip(self):
        words = [qinit(3), qh(0), qx(2), qcx(0, 1), qmeasure(1, 4)]
        self.assertTrue(all(word & 0x7F == CUSTOM_0_OPCODE for word in words))
        self.assertEqual([decode_quantum_instruction(word)["name"] for word in words], [
            "qinit", "qh", "qx", "qcx", "qmeasure"
        ])

    def test_qasm_to_encoded_bell_executes_correlated_measurements(self):
        assembly = compile_qasm_to_custom_words(BELL)
        outcomes = set()
        for seed in range(20):
            emulator = TinyRISCVEmulator(quantum_seed=seed)
            emulator.load_program(assembly)
            state = emulator.execute()
            outcome = (state.get("x1", 0), state.get("x2", 0))
            self.assertIn(outcome, {(0, 0), (1, 1)})
            outcomes.add(outcome)
            self.assertEqual(emulator.quantum_trace[:3], ["qinit 2", "h q[0]", "cx q[0], q[1]"])
        self.assertEqual(outcomes, {(0, 0), (1, 1)})

    def test_x_and_measure_is_deterministic(self):
        program = "\n".join([
            f".word 0x{qinit(1):08x}",
            f".word 0x{qx(0):08x}",
            f".word 0x{qmeasure(0, 3):08x}",
        ])
        emulator = TinyRISCVEmulator()
        emulator.load_program(program)
        self.assertEqual(emulator.execute()["x3"], 1)

    def test_rejects_non_custom_and_unsupported_gate(self):
        with self.assertRaisesRegex(ValueError, "CUSTOM-0"):
            decode_quantum_instruction(0x13)
        bad = BELL.replace("h q[0];", "s q[0];")
        with self.assertRaisesRegex(ValueError, "supports h, x, cx"):
            compile_qasm_to_custom_words(bad)


if __name__ == "__main__":
    unittest.main()
