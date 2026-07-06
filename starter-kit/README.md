# LoomQ · 选手 Starter Kit 快速上手指南

欢迎来到 **LoomQ · 量子接入平权计划**！本 Starter Kit 旨在为你提供打通三个量子平台（量旋 SpinQit、本源 pyqpanda、AWS Braket）的最小实现骨架和调试工具。

> 🧭 **第 0 步：如果你没接触过量子计算**——先花 30 分钟读 [QUANTUM_101.md](QUANTUM_101.md)。
> 它会告诉你：这道题让你造的是"翻译器"，不是让你学物理；评测电路只用 12 个门（白名单在题面里）；
> 真机是加分不是资格线。读完它，剩下的都是你熟悉的软件工程。

---

## 一、目录结构

```text
loomq-starter-kit/
├── README.md                 # 本上手指南
├── QUANTUM_101.md            # 零基础 30 分钟速成：本题所需的全部量子概念（程序员视角）
├── gate_identities.md        # 门分解速查表：后端不支持某门时照抄（已官方数值验证）
├── requirements.txt          # 项目依赖包声明
├── adapter.py                # 选手需要实现的统一接口模板 (包含 L1, L2, L3)
├── evaluator.py              # 官方本地自测与判定脚本 (支持 L1-L3 的一键自动评测)
├── riscv_emulator.py         # 官方配套超轻量级 RISC-V 虚拟机，用于调试 L3 混合编译
├── backend_capabilities.md   # 官方《后端能力表》：L2 智能选后端判定的唯一基准（附选型逻辑示例）
├── backend_capabilities.json # 能力表机读版：建议 Agent 直接加载作为选型知识库
├── circuits/                 # 标准基准测试线路
│   ├── bell.qasm             # 2 比特贝尔态电路
│   └── ghz3.qasm             # 3 比特 GHZ 纠缠态电路
└── examples/                 # 各平台 API 最简调用范例
    ├── run_spinq.py          # 量旋 SpinQit 接入指南
    ├── run_originq.py        # 本源 pyqpanda 接入指南
    └── run_braket.py         # AWS Braket 接入指南
```

---

## 二、环境搭建与依赖安装

推荐使用 `Python 3.9+` 构建你的虚拟环境。我们推荐使用 `uv` 来管理虚拟环境与依赖（速度更快），同时也完全兼容传统的 `pip` 方式。

### 推荐方式 (使用 uv)

```bash
# 1. 创建并激活虚拟环境
uv venv
source .venv/bin/activate

# 2. 安装基础依赖
uv pip install -r requirements.txt
```

### 兼容方式 (使用 pip)

```bash
# 1. 创建并激活虚拟环境
python3 -m venv venv
source venv/bin/activate

# 2. 安装基础依赖
pip install -r requirements.txt
```

> [!IMPORTANT]
> **关于量旋与本源 SDK 的特别提醒**：
> - **量旋 SpinQit** 可通过 `uv pip install spinqit` (或 `pip install spinqit`) 安装。它自带 Taurus 本地模拟器。
> - **本源 pyqpanda** 依赖较多，对 Apple M 系列芯片可能有兼容问题，可参考 README 前一版本或使用 Docker 运行。
> - **AWS Braket** 的 `amazon-braket-sdk` 已经默认包含在依赖中。其本地模拟器无需注册 AWS 账号且完全免费。

### 官方文档速查

| 平台 | 文档 | 代码 / 平台入口 |
|---|---|---|
| 量旋 SpinQit | [SpinQit 官方文档](https://doc.spinq.cn/doc/spinqit/index.html) | [GitHub 源码](https://github.com/SpinQTech/SpinQit) · [产品介绍页](https://www.spinq.cn/products-solutions/spinqKit) |
| 本源量子 | [pyQPanda 中文文档](https://pyqpanda-toturial.readthedocs.io/) · [真机服务用户手册](https://qcloud.originqc.com.cn/document/usermanual/rst/Computing_service1.html) | [本源量子云平台](https://qcloud.originqc.com.cn/zh)（注册后申请 API Token） |
| AWS Braket | [开发者文档](https://docs.aws.amazon.com/braket/) | [Python SDK](https://github.com/amazon-braket/amazon-braket-sdk-python) · [官方示例库](https://github.com/amazon-braket/amazon-braket-examples) |

---

## 三、快速开发说明

你需要在 [adapter.py](file:///Users/qlong/Workspace/hackthon-2026/starter-kit/adapter.py) 中根据任务层级实现以下核心接口：

### 1. Level 1 - 通用中间层对接
- `transpile(qasm_str: str, target: str) -> str`：转译 OpenQASM 2.0 至对应后端的原生指令。
- `run(qasm_str: str, target: str, shots: int) -> dict`：执行并返回标准 JSON counts 字典。

### 2. Level 2 - 说人话的智能体 (Agent)
- `agent_chat(prompt: str) -> str`：
  - 智能体交互接口。输入意图、纠错或选型提问，返回处理响应。
  - **建议**：选手在此处编写 LLM API 接入逻辑（如 Gemini / Claude），配合系统 Prompt 进行引导。
  - *本地自测*：脚本中预置了 3 个典型场景（意图生成、语法纠错、智能选型）的匹配。

### 3. Level 3 - Hybrid-QASM 混合编译 (RISC-V 挑战)
- `compile_hybrid(hybrid_qasm_str: str) -> Tuple[list, str]`：
  - 混合编译接口。输入 **Hybrid-QASM**（OpenQASM 2.0 + `classical { ... }` 经典控制块，完整文法见题面第三节），剥离出量子操作序列，并把经典块编译为 RISC-V 汇编文本。
  - **经典块文法**：整数、寄存器变量 `r1..r9`（映射 `x1..x9`）、测量位 `c[k]`（映射 `x10+k`，由评测系统注入）、运算符 `+ - == !=`、可嵌套的 `if/else` 与顺序赋值。
  - **RISC-V 汇编语法子集**：你编译出的汇编将在配套的 [riscv_emulator.py](file:///Users/qlong/Workspace/hackthon-2026/starter-kit/riscv_emulator.py) 虚拟机上运行，指令集仅需 `li`, `add`, `sub`, `addi`, `beq`, `bne`, `j`。
  - **参考实现**：adapter.py 已内置一个最小但真实的编译器骨架 `HybridQASMCompiler`（词法分析 + 递归下降解析 + 代码生成，支持任意嵌套 if/else）。它不是打表——正式评测会用随机生成的用例并穷举注入测量值，你可以直接在这个骨架上扩展（更多运算符、循环、寄存器分配优化等）。

---

## 四、本地自测与判定

我们提供了一键测试 L1、L2、L3 全级别功能的判定脚本 [evaluator.py](file:///Users/qlong/Workspace/hackthon-2026/starter-kit/evaluator.py)。

运行自测命令：
```bash
python3 evaluator.py
```

评测结果将以非常清晰的彩色表格呈现在终端，包含各测试点的保真度 (Fidelity) 以及编译逻辑正确性。
祝你取得好成绩！
