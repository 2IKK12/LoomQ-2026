#!/usr/bin/env python3
"""
量旋 SpinQit 平台接入最小可跑示例
演示如何导入 OpenQASM 2.0 并使用 SpinQit 运行于本地 Taurus 模拟器。
"""

import json

try:
    import spinqit as sq
except ImportError:
    sq = None

def run_on_spinq_simulator(qasm_str: str, shots: int = 1024) -> dict:
    if sq is None:
        print("[Warning] 未检测到 spinqit 模块，无法真正运行量旋示例。将返回 Mock 数据。")
        return {
            "backend": "spinq_taurus_simulator_mock",
            "job_id": "mock-job-spinq-456",
            "shots": shots,
            "counts": {"00": 505, "11": 519},
            "bit_order": "little",
            "timestamp": "2026-07-06T10:00:00Z",
            "meta": {"info": "Mock data since spinqit is not installed"}
        }

    # 1. 解析 QASM 2.0 字符串为 SpinQit Program 对象
    # SpinQit 提供原生从 QASM 转 Program 的函数
    try:
        prog = sq.qasm_to_program(qasm_str)
    except Exception as e:
        raise RuntimeError(f"SpinQit 导入 QASM 失败: {e}")

    # 2. 初始化后端 (如本地 Taurus 模拟器，或云端超导真机后端)
    # 本地模拟器为 Taurus
    backend = sq.Taurus()

    # 3. 运行程序并获取结果
    # counts 格式一般为 {'00': 512, '11': 512}
    result = backend.run(prog, shots=shots)
    counts = result.counts

    return {
        "backend": "spinq_taurus_simulator",
        "job_id": getattr(result, "job_id", "spinq-taurus-local"),
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": "2026-07-06T10:00:00Z",
        "meta": {
            "qubits_count": prog.qubit_num if hasattr(prog, 'qubit_num') else "unknown"
        }
    }

def main():
    qasm_str = """
    OPENQASM 2.0;
    include "qelib1.inc";
    qreg q[2];
    creg c[2];
    h q[0];
    cx q[0],q[1];
    measure q -> c;
    """
    print("--- 待转译的 QASM 2.0 电路 ---")
    print(qasm_str.strip())
    print("----------------------------")

    res = run_on_spinq_simulator(qasm_str, shots=1024)
    print("\n运行并标准化后的统一输出结果:")
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()
