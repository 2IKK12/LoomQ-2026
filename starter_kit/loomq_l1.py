"""LoomQ L1: OpenQASM 2 parser, target emitters, and local simulator.

The implementation deliberately uses one backend-neutral circuit model.  Target
emitters and the simulator consume that same model so hidden circuits cannot be
handled by sample-specific output tables.
"""

from __future__ import annotations

import ast
import cmath
import hashlib
import math
import random
import re
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Sequence, Tuple


SUPPORTED_TARGETS = ("spinq", "originq", "braket")
SUPPORTED_GATES = {
    "h",
    "x",
    "s",
    "sdg",
    "t",
    "tdg",
    "rz",
    "ry",
    "cx",
    "cu1",
    "swap",
    "ccx",
}
GATE_ARITY = {
    "h": 1,
    "x": 1,
    "s": 1,
    "sdg": 1,
    "t": 1,
    "tdg": 1,
    "rz": 1,
    "ry": 1,
    "cx": 2,
    "cu1": 2,
    "swap": 2,
    "ccx": 3,
}
PARAMETER_GATES = {"rz", "ry", "cu1"}


@dataclass(frozen=True)
class Operation:
    name: str
    qubits: Tuple[int, ...]
    parameter: float | None = None


@dataclass(frozen=True)
class Circuit:
    qubit_count: int
    classical_count: int
    operations: Tuple[Operation, ...]
    measurements: Tuple[Tuple[int, int], ...]


class QASMError(ValueError):
    """Raised for invalid or unsupported OpenQASM input."""


def _safe_angle(expression: str) -> float:
    """Evaluate a numeric angle containing pi and basic arithmetic only."""
    try:
        node = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:
        raise QASMError(f"invalid gate parameter: {expression!r}") from exc

    def evaluate(item: ast.AST) -> float:
        if isinstance(item, ast.Expression):
            return evaluate(item.body)
        if isinstance(item, ast.Constant) and isinstance(item.value, (int, float)):
            return float(item.value)
        if isinstance(item, ast.Name) and item.id == "pi":
            return math.pi
        if isinstance(item, ast.UnaryOp) and isinstance(item.op, (ast.UAdd, ast.USub)):
            value = evaluate(item.operand)
            return value if isinstance(item.op, ast.UAdd) else -value
        if isinstance(item, ast.BinOp) and isinstance(
            item.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)
        ):
            left, right = evaluate(item.left), evaluate(item.right)
            if isinstance(item.op, ast.Add):
                return left + right
            if isinstance(item.op, ast.Sub):
                return left - right
            if isinstance(item.op, ast.Mult):
                return left * right
            if right == 0:
                raise QASMError("gate parameter divides by zero")
            return left / right
        raise QASMError(f"unsupported gate parameter: {expression!r}")

    value = evaluate(node)
    if not math.isfinite(value):
        raise QASMError("gate parameter must be finite")
    return value


def _statements(qasm: str) -> Iterable[str]:
    without_block_comments = re.sub(r"/\*.*?\*/", "", qasm, flags=re.DOTALL)
    without_comments = re.sub(r"//[^\n]*", "", without_block_comments)
    for statement in without_comments.split(";"):
        statement = statement.strip()
        if statement:
            yield statement


def parse_qasm(qasm: str) -> Circuit:
    if not isinstance(qasm, str) or not qasm.strip():
        raise QASMError("qasm_str must be a non-empty string")

    qregs: Dict[str, Tuple[int, int]] = {}
    cregs: Dict[str, Tuple[int, int]] = {}
    operations: List[Operation] = []
    measurements: List[Tuple[int, int]] = []
    qubit_count = classical_count = 0
    saw_header = False

    def declare(registers: Dict[str, Tuple[int, int]], name: str, size: int, offset: int) -> int:
        if name in registers:
            raise QASMError(f"duplicate register: {name}")
        if size <= 0:
            raise QASMError(f"register {name} must have positive size")
        registers[name] = (offset, size)
        return offset + size

    def resolve(reference: str, registers: Dict[str, Tuple[int, int]], kind: str) -> int:
        match = re.fullmatch(r"([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]", reference.strip())
        if not match or match.group(1) not in registers:
            raise QASMError(f"invalid {kind} reference: {reference!r}")
        offset, size = registers[match.group(1)]
        index = int(match.group(2))
        if index >= size:
            raise QASMError(f"{kind} index out of range: {reference!r}")
        return offset + index

    for statement in _statements(qasm):
        if re.fullmatch(r"OPENQASM\s+2(?:\.0)?", statement, flags=re.IGNORECASE):
            saw_header = True
            continue
        if re.fullmatch(r'include\s+["\']qelib1\.inc["\']', statement, flags=re.IGNORECASE):
            continue
        declaration = re.fullmatch(
            r"(qreg|creg)\s+([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]",
            statement,
            flags=re.IGNORECASE,
        )
        if declaration:
            kind, name, raw_size = declaration.groups()
            if kind.lower() == "qreg":
                qubit_count = declare(qregs, name, int(raw_size), qubit_count)
            else:
                classical_count = declare(cregs, name, int(raw_size), classical_count)
            continue
        if statement.lower().startswith("barrier "):
            continue
        measurement = re.fullmatch(r"measure\s+(.+?)\s*->\s*(.+)", statement, flags=re.IGNORECASE)
        if measurement:
            source, destination = (part.strip() for part in measurement.groups())
            if source in qregs and destination in cregs:
                qoffset, qsize = qregs[source]
                coffset, csize = cregs[destination]
                if qsize != csize:
                    raise QASMError("whole-register measurement sizes differ")
                measurements.extend((qoffset + i, coffset + i) for i in range(qsize))
            else:
                measurements.append(
                    (resolve(source, qregs, "qubit"), resolve(destination, cregs, "classical bit"))
                )
            continue

        gate = re.fullmatch(r"([A-Za-z_]\w*)\s*(?:\((.*)\))?\s+(.+)", statement)
        if not gate:
            raise QASMError(f"unsupported statement: {statement!r}")
        name, raw_parameter, raw_operands = gate.groups()
        name = name.lower()
        if name not in SUPPORTED_GATES:
            raise QASMError(f"gate {name!r} is outside the 12-gate whitelist")
        if (name in PARAMETER_GATES) != (raw_parameter is not None):
            requirement = "requires" if name in PARAMETER_GATES else "does not accept"
            raise QASMError(f"gate {name} {requirement} a parameter")
        operands = tuple(
            resolve(reference, qregs, "qubit") for reference in raw_operands.split(",")
        )
        if len(operands) != GATE_ARITY[name]:
            raise QASMError(f"gate {name} expects {GATE_ARITY[name]} qubits")
        if len(set(operands)) != len(operands):
            raise QASMError(f"gate {name} cannot use the same qubit twice")
        operations.append(
            Operation(name, operands, _safe_angle(raw_parameter) if raw_parameter is not None else None)
        )

    if not saw_header:
        raise QASMError("missing OPENQASM 2.0 header")
    if qubit_count == 0:
        raise QASMError("at least one qreg is required")
    if classical_count == 0:
        raise QASMError("at least one creg is required")
    if not measurements:
        raise QASMError("at least one measurement is required")
    return Circuit(qubit_count, classical_count, tuple(operations), tuple(measurements))


def _angle(value: float | None) -> str:
    assert value is not None
    if abs(value) < 5e-16:
        return "0"
    return format(value, ".17g")


def _qasm_operation(operation: Operation, braket: bool = False) -> str:
    name = operation.name
    if braket:
        name = {"cx": "cnot", "cu1": "cp"}.get(name, name)
    parameter = f"({_angle(operation.parameter)})" if operation.parameter is not None else ""
    operands = ", ".join(f"q[{index}]" for index in operation.qubits)
    return f"{name}{parameter} {operands};"


def emit_target(circuit: Circuit, target: str) -> str:
    if target not in SUPPORTED_TARGETS:
        raise ValueError(f"unsupported target {target!r}; choose from {SUPPORTED_TARGETS}")
    if target == "spinq":
        lines = [
            "OPENQASM 2.0;",
            'include "qelib1.inc";',
            f"qreg q[{circuit.qubit_count}];",
            f"creg c[{circuit.classical_count}];",
        ]
        lines.extend(_qasm_operation(operation) for operation in circuit.operations)
        lines.extend(f"measure q[{q}] -> c[{c}];" for q, c in circuit.measurements)
        return "\n".join(lines) + "\n"
    if target == "braket":
        lines = [
            "OPENQASM 3.0;",
            'include "stdgates.inc";',
            f"qubit[{circuit.qubit_count}] q;",
            f"bit[{circuit.classical_count}] c;",
        ]
        lines.extend(_qasm_operation(operation, braket=True) for operation in circuit.operations)
        lines.extend(f"c[{c}] = measure q[{q}];" for q, c in circuit.measurements)
        return "\n".join(lines) + "\n"

    names = {
        "sdg": "SDAG",
        "tdg": "TDAG",
        "cx": "CNOT",
        "ccx": "TOFFOLI",
        "cu1": "CU1",
    }
    lines = [f"QINIT {circuit.qubit_count}", f"CREG {circuit.classical_count}"]
    for operation in circuit.operations:
        name = names.get(operation.name, operation.name.upper())
        operands = ", ".join(f"q[{index}]" for index in operation.qubits)
        parameter = f"({_angle(operation.parameter)})" if operation.parameter is not None else ""
        lines.append(f"{name}{parameter} {operands}")
    lines.extend(f"MEASURE q[{q}], c[{c}]" for q, c in circuit.measurements)
    return "\n".join(lines) + "\n"


def _apply_single(state: List[complex], qubit: int, matrix: Sequence[Sequence[complex]]) -> None:
    stride = 1 << qubit
    for base in range(0, len(state), stride * 2):
        for offset in range(stride):
            zero, one = base + offset, base + offset + stride
            a, b = state[zero], state[one]
            state[zero] = matrix[0][0] * a + matrix[0][1] * b
            state[one] = matrix[1][0] * a + matrix[1][1] * b


def _simulate(circuit: Circuit) -> Tuple[List[complex], int]:
    state = [0j] * (1 << circuit.qubit_count)
    state[0] = 1 + 0j
    root_half = 1 / math.sqrt(2)
    fixed = {
        "h": ((root_half, root_half), (root_half, -root_half)),
        "x": ((0, 1), (1, 0)),
        "s": ((1, 0), (0, 1j)),
        "sdg": ((1, 0), (0, -1j)),
        "t": ((1, 0), (0, cmath.exp(1j * math.pi / 4))),
        "tdg": ((1, 0), (0, cmath.exp(-1j * math.pi / 4))),
    }
    layers = [0] * circuit.qubit_count
    for operation in circuit.operations:
        name, qubits, theta = operation.name, operation.qubits, operation.parameter
        if name in fixed:
            _apply_single(state, qubits[0], fixed[name])
        elif name == "ry":
            assert theta is not None
            cosine, sine = math.cos(theta / 2), math.sin(theta / 2)
            _apply_single(state, qubits[0], ((cosine, -sine), (sine, cosine)))
        elif name == "rz":
            assert theta is not None
            _apply_single(
                state,
                qubits[0],
                ((cmath.exp(-0.5j * theta), 0), (0, cmath.exp(0.5j * theta))),
            )
        elif name in {"cx", "cu1", "swap", "ccx"}:
            updated = state.copy()
            if name == "cx":
                control, target = qubits
                for basis, amplitude in enumerate(state):
                    if basis & (1 << control):
                        updated[basis ^ (1 << target)] = amplitude
            elif name == "cu1":
                assert theta is not None
                control, target = qubits
                phase = cmath.exp(1j * theta)
                for basis, amplitude in enumerate(state):
                    if basis & (1 << control) and basis & (1 << target):
                        updated[basis] = amplitude * phase
            elif name == "swap":
                first, second = qubits
                mask = (1 << first) | (1 << second)
                for basis, amplitude in enumerate(state):
                    if bool(basis & (1 << first)) != bool(basis & (1 << second)):
                        updated[basis ^ mask] = amplitude
            else:
                first, second, target = qubits
                for basis, amplitude in enumerate(state):
                    if basis & (1 << first) and basis & (1 << second):
                        updated[basis ^ (1 << target)] = amplitude
            state = updated
        else:  # Defensive: parsing already rejects this.
            raise QASMError(f"cannot simulate gate {name}")
        layer = max(layers[index] for index in qubits) + 1
        for index in qubits:
            layers[index] = layer
    return state, max(layers, default=0)


def execute(circuit: Circuit, target: str, shots: int, source_qasm: str) -> dict:
    if target not in SUPPORTED_TARGETS:
        raise ValueError(f"unsupported target {target!r}; choose from {SUPPORTED_TARGETS}")
    if not isinstance(shots, int) or isinstance(shots, bool) or shots <= 0:
        raise ValueError("shots must be a positive integer")
    started = time.perf_counter()
    state, depth = _simulate(circuit)
    probabilities: Dict[str, float] = {}
    for basis, amplitude in enumerate(state):
        classical = ["0"] * circuit.classical_count
        for qubit, cbit in circuit.measurements:
            classical[cbit] = "1" if basis & (1 << qubit) else "0"
        key = "".join(reversed(classical))
        probabilities[key] = probabilities.get(key, 0.0) + abs(amplitude) ** 2

    outcomes = [(key, probability) for key, probability in probabilities.items() if probability > 1e-15]
    sampler = random.Random()
    samples = sampler.choices(
        [key for key, _ in outcomes],
        weights=[probability for _, probability in outcomes],
        k=shots,
    )
    counts = dict(sorted(Counter(samples).items()))
    execution_ms = (time.perf_counter() - started) * 1000

    digest = hashlib.sha256(f"{target}\0{shots}\0{source_qasm}".encode()).hexdigest()[:20]
    backend = {
        "spinq": "spinq_local_statevector",
        "originq": "originq_local_statevector",
        "braket": "braket_local_statevector",
    }[target]
    return {
        "backend": backend,
        "job_id": f"local-{digest}",
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "meta": {
            "transpiled_gates": len(circuit.operations),
            "depth": depth,
            "qubits": circuit.qubit_count,
            "simulator": "loomq_statevector_v1",
            "sampling": "independent_shots",
            "execution_ms": round(execution_ms, 3),
            "ideal_probabilities": {
                key: round(probability, 12) for key, probability in sorted(probabilities.items())
            },
        },
    }
