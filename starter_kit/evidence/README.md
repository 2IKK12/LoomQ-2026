# LoomQ 人工评分证据

这份文件是人工评分材料的统一入口。请直接编辑它，只填写要申报的项目。截图、原始结果或图表统一放在 `starter_kit/evidence/files/`，也可以引用 `starter_kit/` 中已有的代码和文档。

证据包是可选的。没有申报某项人工分时，留空即可，不影响自动评分。

## 提交前填写

把要申报项目的方框改成 `[x]`，并填写对应内容：

- [x] L1 真机
- [x] L2 交互体验
- [x] 工程与产品化
- [x] 自定义量子 RISC-V Bonus
- [x] 新手引导与视觉叙事 Bonus

## L1 真机

每个有效真机平台计 5 分，最多两个平台。模拟器不计真机分。每个平台复制并填写一次下面的信息：

```text
平台名称：[填写]
平台 job ID：[填写]
运行时间：[填写，带时区]
shots：[填写]
实际执行的 QASM：[填写仓库内路径]
平台返回的原始结果：[填写仓库内路径]
任务页截图：[选填，填写仓库内路径]
```

建议把文件放进 `evidence/files/`，比如：

```text
evidence/files/spinq-circuit.qasm
evidence/files/spinq-result.json
evidence/files/spinq-screenshot.png
```

工作人员会核对 job ID、运行时间、电路、shots 和原始结果。截图只能辅助说明，不能代替 job ID 和原始结果。

本源量子真机：

```text
平台名称：Origin Quantum Cloud / 本源悟空 180
平台 job ID：B66CD75184D321AB9B7479930B4C3240
运行时间：2026-08-09 21:06:35.155 至 21:06:48.980（UTC+8）
shots：1000
实际执行的 QASM：starter_kit/evidence/files/origin-wukong-180-bell.qasm
提交到平台的 OriginIR：starter_kit/evidence/files/origin-wukong-180-input.originir
平台返回的原始结果：starter_kit/evidence/files/origin-wukong-180-result.csv
任务元数据：starter_kit/evidence/files/origin-wukong-180-job.json
任务成功与结果截图：starter_kit/evidence/files/origin-wukong-180-task-result.png
提交前线路与后端截图：starter_kit/evidence/files/origin-wukong-180-editor.png
映射前后线路截图：starter_kit/evidence/files/origin-wukong-180-mapped-circuit.png
编译前后 OriginIR 截图：starter_kit/evidence/files/origin-wukong-180-compiled-originir.png
```

平台将逻辑量子比特映射到物理量子比特 `q[115]`、`q[124]`，并将逻辑线路编译为含 `RPHI`、`CZ`、`BARRIER` 和测量的芯片线路。原始概率为 `00=0.06`、`01=0.145`、`10=0.498`、`11=0.297`。结果与理想 Bell 分布偏差较大，本证据如实保留平台输出，只申报真实硬件执行，不把该结果描述为高保真 Bell 态。

截图分工：`editor` 证明提交前在线真机后端与线路；`task-result` 证明 job ID、成功状态、shots、运行时间和平台结果；`mapped-circuit` 证明逻辑线路到物理比特的映射；`compiled-originir` 证明输入 OriginIR 到芯片原生门序列的编译。截图仅作辅助，数值依据仍为平台导出的 CSV。

## L2 交互体验

请填写：

```text
启动界面或 CLI 的命令：cd starter_kit && python3 web_app.py
测试入口或页面地址：http://127.0.0.1:8765
适合现场体验的 3 个用户任务：
1. 输入“创建一个两量子比特 Bell 关联实验，只使用 H 和 CX，并测量全部量子比特”，查看回答、L1 共享 IR、Braket/OriginQ/SpinQ 三种目标格式并运行 1,024 shots。
2. 在上一轮之后输入“改成5个，并测量全部量子比特”，验证多轮修改得到 5-qubit GHZ 电路，结果集中在 00000 与 11111，且对话记录可展开查看。
3. 输入“量子计算会不会让人类变得更幸福？”，验证系统先诚实回答开放问题；若提供学习实验，实验必须生成可见 QASM、通过 L1 白名单并进入同一翻译和运行闭环。
截图或演示视频：无（以最终代码现场运行结果为准）
```

本地真实模型预检命令（需要参赛者自己的 `LOOMQ_LLM_*` 环境变量）：

```text
python3 evaluator.py --level l2
python3 l2_smoke_test.py
```

2026-08-09 本地预检结果分别为 1/1 与 6/6 通过；这只记录赛前自测，不声称是正式评分。`l2_smoke_test.py` 的闭环用例将模型生成的 QASM 交给 L1 本地模拟器执行，再把实际 counts 交给模型解释。

工作人员会在组委会统一模型环境中运行最终代码，测试新手是否看得懂、出错后能否得到有效帮助、结果是否清楚，以及多轮回答是否一致。选手自己的对话截图只用于说明产品流程，不直接证明得分。

## 工程与产品化

已有内容可以直接引用主 README 或其他项目文档，不必复制到本目录。

```text
干净环境中的构建和启动命令：starter_kit/README.md（“环境”“启动零基础交互界面”）；无第三方 Python 依赖
架构说明：starter_kit/docs/L1_ARCHITECTURE.md；starter_kit/docs/L2_AGENT.md；starter_kit/docs/L3_HYBRID.md
目标用户和使用场景：首次接触量子计算的学习者及跨学科探索者，用自然语言提出问题，经可验证 QASM 和共享 IR 连接多种目标格式，再运行本地理想模拟器理解 counts
完整使用流程：starter_kit/README.md；starter_kit/docs/L2_AGENT.md；前端实现位于 starter_kit/web/，本地服务入口为 starter_kit/web_app.py
```

工作人员会按最终 commit 实际构建和启动，并检查文档与代码是否一致、产品是否真的降低了量子计算的使用门槛。

## 自定义量子 RISC-V Bonus

以下三项必须齐全且测试通过，才获得 8 分：

```text
指令编码规格：starter_kit/docs/QUANTUM_RISCV_EXTENSION.md
模拟器扩展实现：starter_kit/riscv_emulator.py；编码/解码与 QASM lowering 位于 starter_kit/quantum_riscv.py
端到端测试命令：python3 -m unittest tests.test_quantum_riscv -v
```

## 新手引导与视觉叙事 Bonus

请填写已有材料的路径，不要求为评分另写一套文档：

```text
零基础首次运行指南：starter_kit/README.md（“启动零基础交互界面”）；starter_kit/web/index.html 的四阶段引导
量子概念解释：starter_kit/QUANTUM_101.md；starter_kit/loomq_agent.py 的零基础回答规则；结果页通俗解释
结果可视化：starter_kit/web/app.js 的真实 counts 柱状图；starter_kit/web/index.html 的测量标签说明
错误恢复或无障碍引导：starter_kit/web/app.js 的连接/校验/运行错误分流、失败时保留输入与会话恢复；starter_kit/web/styles.css 的键盘焦点、移动端和 prefers-reduced-motion 支持
```

以上四项各 1 分。普通项目 README 完整不代表自动获得 Bonus。

## 提交规则

- 所有材料都要在截止前进入最终提交的 commit，工作人员不接受截止后补交。
- 外部视频可以用稳定只读链接，源码、原始结果和复现命令应保存在仓库中。
- 整个 fork commit 的归档包不得超过 100 MiB。
- 不要提交 API Key、Token、Cookie、个人身份信息或平台账户隐私。
- 如申报 L1 真机分，在最终提交 Issue 的 `Hardware evidence` 中填写 `starter_kit/evidence/README.md`。
