#!/usr/bin/env python3
"""
LoomQ 量子接入平权计划 - 评测与自动判定脚本

本脚本用于选手在本地测试自己的实现是否符合大赛契约（L1、L2、L3 各级别契约），
集成了基于 Hellinger Fidelity 判定 L1 和 L2，以及基于 TinyRISCVEmulator 判定 L3 混合编译。
"""

import os
import sys
import json
import math
import argparse
import re
from typing import Dict, Any, Optional, Tuple, List

# 引入本地轻量级 RISC-V 模拟器
try:
    from riscv_emulator import TinyRISCVEmulator
except ImportError:
    TinyRISCVEmulator = None

# 尝试导入选手的适配器
try:
    import adapter
except ImportError:
    adapter = None

# 理想分布表（用于 L1 和 L2 用例校验）
IDEAL_DISTRIBUTIONS = {
    "bell.qasm": {"00": 0.5, "11": 0.5},
    "ghz3.qasm": {"000": 0.5, "111": 0.5}
}

# 若 circuits/ 下存在 ideal_distributions.json（正式评测时由官方注入完整 8 电路表），自动合并加载
_ideal_json = os.path.join(os.path.dirname(os.path.abspath(__file__)), "circuits", "ideal_distributions.json")
if os.path.exists(_ideal_json):
    with open(_ideal_json, encoding="utf-8") as _f:
        IDEAL_DISTRIBUTIONS.update(json.load(_f))

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def calculate_hellinger_fidelity(p: Dict[str, float], q: Dict[str, float]) -> float:
    all_states = set(p.keys()).union(set(q.keys()))
    sum_diff_sq = sum((math.sqrt(p.get(s, 0.0)) - math.sqrt(q.get(s, 0.0))) ** 2 for s in all_states)
    return max(0.0, min(1.0, 1.0 - (1.0 / math.sqrt(2.0)) * math.sqrt(sum_diff_sq)))


def validate_schema(result_dict: Dict[str, Any]) -> Tuple[bool, str]:
    required_fields = ["backend", "job_id", "shots", "counts", "bit_order", "timestamp"]
    for field in required_fields:
        if field not in result_dict:
            return False, f"缺失必填字段: {field}"
    if not isinstance(result_dict["shots"], int) or result_dict["shots"] <= 0:
        return False, "shots 必须是正整数"
    if not isinstance(result_dict["counts"], dict):
        return False, "counts 必须是字典对象"
    counts_sum = sum(result_dict["counts"].values())
    if abs(counts_sum - result_dict["shots"]) > result_dict["shots"] * 0.01:
        return False, f"counts 采样总数 ({counts_sum}) 与 shots ({result_dict['shots']}) 不符"
    for k in result_dict["counts"].keys():
        if not all(char in '01' for char in k):
            return False, f"counts 的 key 必须是二进制字符串，当前为: '{k}'"
    if result_dict["bit_order"] != "little":
        return False, "bit_order 必须为 'little'"
    return True, "Schema 校验通过"


# ----------------------------------------------------
# L1 评测核心
# ----------------------------------------------------
def evaluate_l1(qasm_file: str, target: str, shots: int) -> Dict[str, Any]:
    qasm_name = os.path.basename(qasm_file)
    if adapter is None:
        return {"status": "FAIL", "reason": "未找到 adapter.py"}
        
    try:
        with open(qasm_file, 'r', encoding='utf-8') as f:
            qasm_str = f.read()
        
        # 运行
        res_data = adapter.run(qasm_str, target, shots)
        
        # 校验
        schema_ok, schema_msg = validate_schema(res_data)
        if not schema_ok:
            return {"status": "FAIL", "reason": f"Schema 错误: {schema_msg}"}
            
        fidelity = None
        if qasm_name in IDEAL_DISTRIBUTIONS:
            ideal = IDEAL_DISTRIBUTIONS[qasm_name]
            p_dist = {k: v / res_data["shots"] for k, v in res_data["counts"].items()}
            fidelity = calculate_hellinger_fidelity(p_dist, ideal)
            
        if fidelity is not None and fidelity < 0.97:
            return {"status": "FAIL", "fidelity": fidelity, "reason": f"保真度不足 ({fidelity:.4f} < 0.97)"}

        if res_data.get("meta", {}).get("is_mock"):
            return {"status": "PASS", "fidelity": fidelity, "reason": "通过(Mock数据,正式评测计0分)"}
        return {"status": "PASS", "fidelity": fidelity, "reason": "测试通过"}
    except Exception as e:
        return {"status": "FAIL", "reason": f"运行异常: {e}"}


# ----------------------------------------------------
# L2 (智能体) 评测核心
# ----------------------------------------------------
def extract_qasm(text: str) -> Optional[str]:
    """从 Agent 的文本响应中提取含有 OPENQASM 的代码块"""
    match = re.search(r'(OPENQASM\s+2\.0;.*?(?=^\s*```|\Z))', text, re.DOTALL | re.MULTILINE)
    if match:
        return match.group(1).strip()
    # 尝试匹配无标记的代码行
    if "OPENQASM 2.0;" in text:
        idx = text.find("OPENQASM 2.0;")
        return text[idx:].split("```")[0].strip()
    return None


def evaluate_l2_agent() -> List[Tuple[str, str, Dict[str, Any]]]:
    """对 Level 2 智能体进行客观评测"""
    results = []
    if adapter is None or not hasattr(adapter, 'agent_chat'):
        return [("L2_Agent", "all", {"status": "SKIP", "reason": "未在 adapter.py 中检测到 agent_chat 实现"})]
        
    print(f"\n{Colors.BOLD}🔍 正在评估 L2 智能体 (Agent)...{Colors.ENDC}")
    
    # 1. 意图生成评测
    prompt_1 = "生成一个 3 比特的最大纠缠态 (GHZ 态)，并进行全测量"
    try:
        reply_1 = adapter.agent_chat(prompt_1)
        qasm_1 = extract_qasm(reply_1)
        if not qasm_1:
            results.append(("L2_Prompt1_生成", "GHZ-3", {"status": "FAIL", "reason": "未能从智能体回复中解析出 QASM 电路"}))
        else:
            # 仿真验证生成的 QASM
            res = adapter.run(qasm_1, "spinq", 8192)
            p_dist = {k: v / 8192 for k, v in res["counts"].items()}
            fid = calculate_hellinger_fidelity(p_dist, IDEAL_DISTRIBUTIONS["ghz3.qasm"])
            if fid >= 0.97:
                results.append(("L2_Prompt1_生成", "GHZ-3", {"status": "PASS", "fidelity": fid, "reason": "智能体成功生成并仿真通过"}))
            else:
                results.append(("L2_Prompt1_生成", "GHZ-3", {"status": "FAIL", "fidelity": fid, "reason": "生成的电路不满足 GHZ 态保真度"}))
    except Exception as e:
        results.append(("L2_Prompt1_生成", "GHZ-3", {"status": "FAIL", "reason": f"异常: {e}"}))

    # 2. 语法纠错评测
    prompt_2 = "我想制备一个贝尔态，但这段代码报错了，帮我修好：H q[0]; CX q[0] q[1] (提示: 未定义寄存器且门名大小写错误)"
    try:
        reply_2 = adapter.agent_chat(prompt_2)
        qasm_2 = extract_qasm(reply_2)
        if not qasm_2:
            results.append(("L2_Prompt2_纠错", "Bell", {"status": "FAIL", "reason": "未能从智能体回复中解析出 QASM 电路"}))
        else:
            res = adapter.run(qasm_2, "spinq", 8192)
            p_dist = {k: v / 8192 for k, v in res["counts"].items()}
            fid = calculate_hellinger_fidelity(p_dist, IDEAL_DISTRIBUTIONS["bell.qasm"])
            if fid >= 0.97:
                results.append(("L2_Prompt2_纠错", "Bell", {"status": "PASS", "fidelity": fid, "reason": "智能体成功纠错并修复电路"}))
            else:
                results.append(("L2_Prompt2_纠错", "Bell", {"status": "FAIL", "fidelity": fid, "reason": "修复后的电路保真度不正确"}))
    except Exception as e:
        results.append(("L2_Prompt2_纠错", "Bell", {"status": "FAIL", "reason": f"异常: {e}"}))

    # 3. 智能选后端评测
    prompt_3 = "我需要运行一个 15 个量子比特的电路，并且要保证零等待排队，请问应该选择哪个平台？"
    try:
        reply_3 = adapter.agent_chat(prompt_3)
        # 按官方《后端能力表》核对：15 比特 + 零排队 -> 无排队且比特数 >= 15 的后端
        correct_ids = ["spinq_taurus_simulator", "originq_local_simulator", "braket_local_simulator"]
        cap_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend_capabilities.json")
        if os.path.exists(cap_path):
            with open(cap_path, encoding="utf-8") as f:
                caps = json.load(f)["backends"]
            correct_ids = [b["id"] for b in caps if b["queue"] == "none" and b["max_qubits"] >= 15]
        if any(cid in reply_3 for cid in correct_ids):
            results.append(("L2_Prompt3_选型", "Text", {"status": "PASS", "reason": "回复包含正确的规范后端标识"}))
        else:
            results.append(("L2_Prompt3_选型", "Text", {"status": "FAIL", "reason": "回复未包含能力表核定的规范后端标识"}))
    except Exception as e:
        results.append(("L2_Prompt3_选型", "Text", {"status": "FAIL", "reason": f"异常: {e}"}))
        
    return results


# ----------------------------------------------------
# L3 (混合编译) 评测核心
# ----------------------------------------------------
def evaluate_l3_compile() -> List[Tuple[str, str, Dict[str, Any]]]:
    """对 Level 3 混合指令编译进行客观判定"""
    results = []
    if adapter is None or not hasattr(adapter, 'compile_hybrid'):
        return [("L3_Hybrid", "all", {"status": "SKIP", "reason": "未在 adapter.py 中检测到 compile_hybrid 实现"})]
        
    if TinyRISCVEmulator is None:
        return [("L3_Hybrid", "all", {"status": "FAIL", "reason": "本地环境缺少 riscv_emulator.py 文件"})]
        
    print(f"\n{Colors.BOLD}🔍 正在评估 L3 混合编译与分支控制流...{Colors.ENDC}")
    
    # Hybrid-QASM 测试用例（文法见题面第三节）。正式评测将随机生成同文法的多组用例
    # 并穷举注入测量值组合，此处为本地自测样例。
    hybrid_qasm = """
    OPENQASM 2.0;
    include "qelib1.inc";
    qreg q[2];
    creg c[2];
    h q[0];
    measure q[0] -> c[0];
    classical {
      if (c[0] == 1) {
        r1 = 100;
      } else {
        r1 = 10;
      }
      r1 = r1 + 5;
    }
    cx q[0], q[1];
    """
    # 上述经典块的参考语义：c[0]=1 -> r1=105；c[0]=0 -> r1=15
    expected = {1: 105, 0: 15}

    try:
        # 1. 编译
        quantum_ops, riscv_asm = adapter.compile_hybrid(hybrid_qasm)
        if not riscv_asm or not isinstance(quantum_ops, list):
            return [("L3_Hybrid_编译", "compile", {"status": "FAIL", "reason": "编译返回的汇编代码为空或量子操作格式不符"})]

        # 2. 注入不同测量值 (c[0] -> x10)，逐一比对寄存器终态与参考语义
        for meas_val, expect_x1 in expected.items():
            emu = TinyRISCVEmulator()
            emu.load_program(riscv_asm)
            emu.set_register("x10", meas_val)  # 注入测量结果
            state = emu.execute()
            val = state.get("x1", 0)
            label = f"RISCV_c0={meas_val}"
            if val == expect_x1:
                results.append(("L3_混合_经典段", label, {"status": "PASS", "reason": f"x1={val} 与参考语义一致"}))
            else:
                results.append(("L3_混合_经典段", label, {"status": "FAIL", "reason": f"x1={val}，参考语义应为 {expect_x1}"}))
            
    except Exception as e:
        results.append(("L3_Hybrid", "execute", {"status": "FAIL", "reason": f"编译与模拟执行时发生异常: {e}"}))
        
    return results


def main():
    parser = argparse.ArgumentParser(description="LoomQ 评测与判定脚本 (Stage 2)")
    parser.add_argument("--target", type=str, default="spinq,originq", help="运行平台 (braket, spinq, originq)")
    parser.add_argument("--shots", type=int, default=8192, help="采样 shots (与正式评测一致，为统计涨落留余量)")
    args = parser.parse_args()

    targets = [t.strip() for t in args.target.split(",")]
    circuits_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "circuits")
    
    if not os.path.exists(circuits_dir):
        print(f"{Colors.FAIL}[Error]{Colors.ENDC} circuits 目录不存在。")
        sys.exit(1)
        
    qasm_files = [os.path.join(circuits_dir, f) for f in os.listdir(circuits_dir) if f.endswith(".qasm")]

    print(f"{Colors.HEADER}==================================================")
    print(f"🌟 LoomQ · 量子接入平权计划 (Stage 2 评测系统) 🌟")
    print(f"=================================================={Colors.ENDC}")
    print(f"发现 L1 测试电路: {len(qasm_files)} 个")
    print(f"测试后端: {', '.join(targets)}")
    
    eval_results = []

    # 1. 评估 L1
    for qasm_file in sorted(qasm_files):
        for target in targets:
            res = evaluate_l1(qasm_file, target, args.shots)
            eval_results.append((f"L1_{os.path.basename(qasm_file)}", target, res))

    # 2. 评估 L2
    l2_res = evaluate_l2_agent()
    eval_results.extend(l2_res)

    # 3. 评估 L3
    l3_res = evaluate_l3_compile()
    eval_results.extend(l3_res)

    # 美化打印汇总报告
    print("\n" + f"{Colors.HEADER}==================== 评 测 报 告 汇 总 ===================={Colors.ENDC}")
    print(f"{Colors.BOLD}{'测试模块/电路':<25} {'测试目标':<10} {'Fidelity':<10} {'状态':<10} {'判定说明':<30}{Colors.ENDC}")
    print("-" * 85)
    
    passed = 0
    total = 0
    
    for label, target, res in eval_results:
        if res["status"] == "SKIP":
            status_str = f"{Colors.WARNING}SKIP{Colors.ENDC}"
            fid_str = "N/A"
        else:
            total += 1
            if res["status"] == "PASS":
                status_str = f"{Colors.OKGREEN}PASS{Colors.ENDC}"
                passed += 1
            else:
                status_str = f"{Colors.FAIL}FAIL{Colors.ENDC}"
            fid_str = f"{res['fidelity']:.4f}" if res.get("fidelity") is not None else "N/A"
            
        reason = res.get("reason", "")
        if len(reason) > 30:
            reason = reason[:27] + "..."
            
        print(f"{label:<25} {target:<10} {fid_str:<10} {status_str:<10} {reason:<30}")
        
    print("-" * 85)
    rate = (passed / total) * 100 if total > 0 else 0
    print(f"有效测试通过率: {passed}/{total} ({rate:.1f}%)")
    
    if passed == total and total > 0:
        print(f"\n{Colors.OKGREEN}🎉 恭喜！当前所有启用的本地测试顺利通过！契约完整度 100%{Colors.ENDC}")
    else:
        print(f"\n{Colors.FAIL}❌ 存在未通过的测试。请根据判定说明调试你的接口实现。{Colors.ENDC}")
    print(f"{Colors.HEADER}=========================================================={Colors.ENDC}")


if __name__ == "__main__":
    main()
