#!/usr/bin/env python3
"""Real-model L2 smoke tests for generation, repair, and backend selection.

This is an entrant-side diagnostic, not an official score. It intentionally uses
prompt wording and constraints different from the public evaluator example.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Callable

try:
    from . import adapter
    from .evaluator import calculate_hellinger_fidelity
    from .loomq_agent import extract_qasm
except ImportError:
    import adapter
    from evaluator import calculate_hellinger_fidelity
    from loomq_agent import extract_qasm


@dataclass(frozen=True)
class Case:
    name: str
    prompt: str
    check: Callable[[str], tuple[bool, str]]


def distribution_check(expected: dict[str, float]) -> Callable[[str], tuple[bool, str]]:
    def check(answer: str) -> tuple[bool, str]:
        qasm = extract_qasm(answer)
        if not qasm:
            return False, "answer contains no OpenQASM 2.0 program"
        try:
            result = adapter.run(qasm, "braket", 8192)
        except Exception as exc:
            return False, f"L1 rejected generated QASM: {type(exc).__name__}: {exc}"
        observed = {key: count / result["shots"] for key, count in result["counts"].items()}
        fidelity = calculate_hellinger_fidelity(observed, expected)
        return fidelity >= 0.97, f"semantic fidelity={fidelity:.6f}"

    return check


def backend_check(allowed: set[str]) -> Callable[[str], tuple[bool, str]]:
    def check(answer: str) -> tuple[bool, str]:
        matches = sorted(identifier for identifier in allowed if identifier in answer)
        return bool(matches), "matched=" + (", ".join(matches) if matches else "none")

    return check


CASES = (
    Case(
        "generate-ghz4",
        "我是零基础学生。请为四个量子比特制备 GHZ 态，测量所有比特，并给我完整可运行的 OpenQASM 2.0。",
        distribution_check({"0000": 0.5, "1111": 0.5}),
    ),
    Case(
        "repair-bell",
        """我的目标是制备贝尔态，但这段代码无法运行，请保持目标不变并修好它：
OPENQASM 2.0;
H q[0]
CX q[0] q[1]
请返回完整 OpenQASM 2.0 程序。""",
        distribution_check({"00": 0.5, "11": 0.5}),
    ),
    Case(
        "backend-zero-queue-15q",
        "我有一个 15 比特电路，不能等待排队，也不想登录任何云账号。请给出规范后端标识。",
        backend_check(
            {"spinq_taurus_simulator", "originq_local_simulator", "braket_local_simulator"}
        ),
    ),
    Case(
        "backend-free-real-5q",
        "我必须在真实量子硬件上运行 5 比特实验，可以排队和注册，但不接受纯付费方案。应选什么？",
        backend_check({"spinq_cloud_qpu", "originq_wukong"}),
    ),
    Case(
        "backend-free-local-30q",
        "我需要本地、免费、无排队地运行恰好 30 比特的电路，请回复官方规范 ID。",
        backend_check({"originq_local_simulator"}),
    ),
)


def main() -> int:
    records = []
    for case in CASES:
        try:
            answer = adapter.agent_chat(case.prompt)
            passed, detail = case.check(answer)
        except Exception as exc:
            passed, detail = False, f"{type(exc).__name__}: {exc}"
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {case.name}: {detail}")
        records.append({"case": case.name, "status": status, "detail": detail})
    summary = {
        "passed": sum(item["status"] == "PASS" for item in records),
        "failed": sum(item["status"] == "FAIL" for item in records),
        "total": len(records),
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
