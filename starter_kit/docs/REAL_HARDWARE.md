# LoomQ Web 量子真机连接

LoomQ 的比赛 `adapter.run()` 保持本地、无依赖且可复现。网页中的“量子真机”是额外产品功能，由 `hardware_runner.py` 隔离，不会改变 L1 评测契约。

## 当前真机网关

当前支持 Amazon Braket 门模型 QPU。LoomQ 先用 L1 将 OpenQASM 2.0 转为 Braket OpenQASM 3.0，再通过官方 SDK 提交任务。实现依据 AWS 官方的 OpenQASM 任务流程：

- <https://docs.aws.amazon.com/braket/latest/developerguide/braket-openqasm-create-submit-task.html>
- <https://docs.aws.amazon.com/braket/latest/developerguide/braket-monitor-tasks-sdk.html>

## 本机配置

先在启动 LoomQ 的 Python 3.10 环境中安装官方 SDK。正式提交不依赖这个可选包，因此它不写入比赛基线 `requirements.txt`。

```bash
python3 -m pip install amazon-braket-sdk
```

按 AWS 标准方式配置凭证，再设置：

```bash
export LOOMQ_BRAKET_DEVICE_ARN='arn:aws:braket:<region>::device/qpu/<provider>/<device>'
export LOOMQ_BRAKET_S3_BUCKET='<your-results-bucket>'
export LOOMQ_BRAKET_S3_PREFIX='loomq-web'
export LOOMQ_BRAKET_POLL_TIMEOUT_SECONDS='900'
python3 web_app.py
```

`LOOMQ_BRAKET_DEVICE_ARN` 必须包含 `/qpu/`。LoomQ 会拒绝把 Braket 云模拟器标记成真机。AWS 账号密钥由官方凭证链读取，网页不接收、不显示、不保存密钥。

## 返回结果

网页使用和比赛一致的统一字段：

- `backend`: 真实 QPU Device ARN
- `job_id`: Braket Quantum Task ID，可在控制台溯源
- `shots`: 提交的重复次数
- `counts`: 真机返回的测量计数
- `bit_order`: LoomQ 归一化标记
- `timestamp`: LoomQ 取得结果的 UTC 时间
- `meta.execution_type`: `real_hardware`

真机任务可能排队、超时或失败。网页会显示原始错误和 job_id，不会用本地模拟结果替换失败的真机任务。
