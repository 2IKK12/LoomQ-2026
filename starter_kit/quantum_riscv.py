"""LoomQ experimental RISC-V CUSTOM-0 quantum instruction encoding."""

from __future__ import annotations

from typing import Any

try:
    from .loomq_l1 import parse_qasm
except ImportError:
    from loomq_l1 import parse_qasm


CUSTOM_0_OPCODE = 0x0B
QINIT = 0
QH = 1
QX = 2
QCX = 3
QMEASURE = 4

NAMES = {
    QINIT: "qinit",
    QH: "qh",
    QX: "qx",
    QCX: "qcx",
    QMEASURE: "qmeasure",
}


def _field(value: int, name: str, *, minimum: int = 0, maximum: int = 31) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer in {minimum}..{maximum}")
    return value


def encode_quantum_instruction(
    operation: int,
    *,
    rd: int = 0,
    rs1: int = 0,
    rs2: int = 0,
) -> int:
    """Encode one LoomQ quantum instruction in the RISC-V CUSTOM-0 space."""
    _field(operation, "operation", maximum=7)
    _field(rd, "rd")
    _field(rs1, "rs1")
    _field(rs2, "rs2")
    if operation not in NAMES:
        raise ValueError(f"unsupported LoomQ quantum operation id {operation}")
    return CUSTOM_0_OPCODE | (rd << 7) | (operation << 12) | (rs1 << 15) | (rs2 << 20)


def decode_quantum_instruction(word: int) -> dict[str, Any]:
    if not isinstance(word, int) or isinstance(word, bool) or not 0 <= word <= 0xFFFFFFFF:
        raise ValueError("instruction word must be an unsigned 32-bit integer")
    if word & 0x7F != CUSTOM_0_OPCODE:
        raise ValueError("instruction does not use the RISC-V CUSTOM-0 opcode")
    if word >> 25:
        raise ValueError("reserved quantum instruction bits 31..25 must be zero")
    operation = (word >> 12) & 0x7
    if operation not in NAMES:
        raise ValueError(f"unsupported LoomQ quantum operation id {operation}")
    return {
        "operation": operation,
        "name": NAMES[operation],
        "rd": (word >> 7) & 0x1F,
        "rs1": (word >> 15) & 0x1F,
        "rs2": (word >> 20) & 0x1F,
    }


def qinit(qubits: int) -> int:
    return encode_quantum_instruction(QINIT, rs1=_field(qubits, "qubits", minimum=1, maximum=16))


def qh(qubit: int) -> int:
    return encode_quantum_instruction(QH, rs1=_field(qubit, "qubit"))


def qx(qubit: int) -> int:
    return encode_quantum_instruction(QX, rs1=_field(qubit, "qubit"))


def qcx(control: int, target: int) -> int:
    return encode_quantum_instruction(
        QCX,
        rs1=_field(control, "control"),
        rs2=_field(target, "target"),
    )


def qmeasure(qubit: int, destination_register: int) -> int:
    return encode_quantum_instruction(
        QMEASURE,
        rd=_field(destination_register, "destination_register", minimum=1),
        rs1=_field(qubit, "qubit"),
    )


def compile_qasm_to_custom_words(qasm: str) -> str:
    """Compile the supported H/X/CX/measurement QASM subset to `.word` assembly."""
    circuit = parse_qasm(qasm)
    words: list[tuple[int, str]] = [(qinit(circuit.qubit_count), f"QINIT {circuit.qubit_count}")]
    for operation in circuit.operations:
        if operation.name == "h":
            word = qh(operation.qubits[0])
        elif operation.name == "x":
            word = qx(operation.qubits[0])
        elif operation.name == "cx":
            word = qcx(operation.qubits[0], operation.qubits[1])
        else:
            raise ValueError(
                "the custom v1 executable subset supports h, x, cx, and measurement; "
                f"found {operation.name}"
            )
        words.append((word, operation.name.upper() + " " + ",".join(map(str, operation.qubits))))
    for qubit, classical in circuit.measurements:
        if classical >= 31:
            raise ValueError("custom measurement supports at most 31 classical destinations")
        words.append((qmeasure(qubit, classical + 1), f"MEASURE q{qubit} -> x{classical + 1}"))
    return "\n".join(f".word 0x{word:08x}  # {label}" for word, label in words) + "\n"
