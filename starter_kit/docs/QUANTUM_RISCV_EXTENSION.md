# LoomQ Quantum RISC-V CUSTOM-0 Extension v1

## Scope and honesty boundary

This experimental extension demonstrates an executable path from a validated
QASM circuit to encoded RISC-V custom instruction words. Version 1 executes
`QINIT`, `QH`, `QX`, `QCX`, and `QMEASURE`. It does **not** claim that the full
12-gate L1 whitelist is encoded, that a physical RISC-V chip implements these
instructions, or that its local statevector measurements are quantum-hardware
evidence.

## 32-bit encoding

All instructions use the standard RISC-V `CUSTOM-0` major opcode `0001011`
(`0x0b`). Bits `31..25` are reserved and must be zero.

```text
31       25 24    20 19    15 14  12 11     7 6       0
+-----------+--------+--------+------+---------+---------+
| 0000000   |  rs2   |  rs1   | op3  |   rd    | 0001011 |
+-----------+--------+--------+------+---------+---------+
```

| op3 | Mnemonic | rs1 | rs2 | rd | Effect |
|---:|---|---|---|---|---|
| 0 | `QINIT` | qubit count (1–16) | 0 | 0 | Initialize `|0...0>` |
| 1 | `QH` | target qubit | 0 | 0 | Apply Hadamard |
| 2 | `QX` | target qubit | 0 | 0 | Apply Pauli-X |
| 3 | `QCX` | control qubit | target qubit | 0 | Apply controlled-X |
| 4 | `QMEASURE` | measured qubit | 0 | destination `x1..x31` | Sample, collapse, write 0/1 |

Reserved fields are validated during execution. Invalid opcodes, operation IDs,
qubit indices, register destinations, or instructions issued before `QINIT`
fail explicitly.

## Implementation

- Encoding, decoding, and QASM lowering: `starter_kit/quantum_riscv.py`
- Simulator extension: `starter_kit/riscv_emulator.py`
- End-to-end tests: `tests/test_quantum_riscv.py`

The lowering function parses QASM with the existing L1 parser before emitting
`.word 0x........` assembly, so malformed circuits and unsupported gates are not
silently encoded. The emulator decodes each 32-bit word and executes a small
statevector with seeded sampling and measurement collapse. The Bell test runs
20 independent seeds and requires every result to be correlated (`00` or `11`).

## Reproduce

From the fork root:

```bash
python3 -m unittest tests.test_quantum_riscv -v
```

This command tests encoding round trips, invalid encodings, deterministic
`X → measure`, and the complete QASM → encoded CUSTOM-0 words → decoded quantum
execution → classical RISC-V register result path.
