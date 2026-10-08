# Agent Watchdog · 第 04–12 篇配套参考代码

这不是一个替换掉原项目的重构包。它直接复用读者上传的第三篇 `evidence.py` 与 `watchdog_rules.json`，通过额外模块学习从事件桥接到合同、验收、持久事件记录和交接。

## 使用原则

- **不要直接把本目录的 `evidence.py` 覆盖你的旧版。** 这是从第三篇源码包提取的兼容参考副本。
- 先在你的原项目目录备份 `hook_runner.cmd`，再复制本例的新文件。
- `hook_runner_v04.cmd` 默认启动 `python`；如果真实 Codex 找不到 Conda Python，手工配置 `WATCHDOG_PYTHON` 为 `where python` 的真实路径。
- 监控目标仍是 `D:\program\agent_watchdog\hook_demo`；把本目录的 `hook_demo` 样例拷过去前，先核对原仓库文件，不要覆盖已经做过的第三篇实验。
- `Hook Logger` 与 `Bridge` 不自动测试、不 kill、不修改工作区。用户显式执行 `task_contract.py verify A1` 才会运行受信任的测试代码。
- 代码是教学参考实现，**还没有经过你的 Windows 11 + 真实 Codex Hooks 现场验收**。

## 源码速查

| 文件 | 篇章 | 用途 |
|---|---|---|
| `hook_logger_v04.py` | 04 | 只采集 allowlist 元数据 |
| `hook_runner_v04.cmd` | 04 | Windows Hook 启动器 |
| `bridge.py` | 04 | Git 独立证据扫描、节流及防抖 |
| `monitor04.py` | 04/08 | Rich 只读面板 |
| `evidence.py` | 03/04 | 用户上传的第三篇原版 |
| `task_contract.py` | 05/06 | 合同批准与逐项验收 |
| `risk.py` | 07/11 | 事实 + 启发式风险提示 |
| `watchdog_cli.py` | 08/11/12 | status / alerts / handoff |
| `journal.py` | 09/12 | JSONL → SQLite，备份 |
| `agent_adapter.py` | 10 | 显式导入 Codex exec JSONL 的脱敏元数据 |

## 在本目录做安全的自动测试

Python 3.9+、Git；Rich 仅在实际启动 Rich 面板时需要。

```bat
cd /d <你的克隆仓库路径>
python -m unittest discover -s examples\v04\tests -v
```

自动化测试将临时建立独立 Git 仓库，不启动 Codex，不联网，不修改已上传的教程文件。

## 真实接入顺序

1. 验证你本机第三篇 `evidence.py ... baseline/scan/test` 已经能工作。
2. 复制新增的 v0.4 文件，运行 `bridge.py --repo ... --once`。
3. 启动 Bridge、Monitor，用 PowerShell JSON 模拟一次 `PostToolUse`。
4. 仔细检查原 `hook_runner.cmd`，再改为指向新版 Logger。
5. 在受信任的 `hook_demo/.codex/hooks.json` 中使用新 Runner，CLI `/hooks` 审核并信任。
6. 用真实 Codex 执行小任务，**以真实日志作为端到端验收依据**。
7. 继续第 05–12 篇，不把模拟事件当真实 Codex 成果。

## 安全与局限

日志、SQLite、合同状态均写在本机。GitHub 不应包含这些本地状态；仓库 `.gitignore` 已排除相应目录。

这套参考代码没有做 OS 级进程隔离，也不等于能够抵抗拥有同一文件权限的恶意 Agent。Git 指纹涵盖跟踪与未忽略文件；被忽略文件、外部服务和数据库不在当前证据范围内。


## 第 13–16 篇：真实验收、事件适配、进度与范围检查

在第 04–12 篇的相同 `watchdog` 目录新增如下只读模块（不会删除、重构原来的 evidence/contract/journal）：

| 章 | 脚本 | 功能与明确边界 |
|---|---|---|
| 13 | `integration_check.py` | 联调就绪状态；无法自行证明真实 Codex 事件来源 |
| 14 | `appserver_adapter.py` | 仅导入手工提供的 App Server NDJSON；不接管连接或审批 |
| 15 | `progress.py` | 将经批准的合同验收对应里程碑；不计算语义完成率 |
| 16 | `scope_guard.py` | 检测 Git 可见路径越界；不推断修改作者或语义动机 |

Windows cmd 基本命令示例（使用你已经配置好的 `torch_env` 环境）：

```bat
cd /d D:\program\agent_watchdog\watchdog
python integration_check.py --repo "D:\program\agent_watchdog\hook_demo"
python progress.py --repo "D:\program\agent_watchdog\hook_demo"
python scope_guard.py --repo "D:\program\agent_watchdog\hook_demo"
```

App Server 的脱敏导入命令（仅对你自己明确授权导出的 JSONL 文件执行）：

```bat
python appserver_adapter.py appserver_demo.ndjson --out logs\appserver_safe.jsonl
python journal.py sync --log logs\appserver_safe.jsonl
```

运行全套隔离测试：

```bat
python -m unittest discover -s examples\v04\tests -v
```

真实 Codex 端到端的人工检查表见 [CHAPTERS_13-16.md](CHAPTERS_13-16.md)。

## 第 17–20 篇：异常监督、Web、备份与 V1.0 发布门槛

本轮只追加四个模块，保持现有接口：`supervision.py` 负责分开输出事实与启发式提示；`dashboard.py` 提供本地 Streamlit 只读视图；`operations.py` 对 SQLite 与 Git 报告进行数据级诊断、显式备份；`release_gate.py` 拒绝将未经本机验证的参考实现伪装成正式 V1.0。

- [安装与 Windows 综合验收](CHAPTERS_17-20.md)
- [全部未通过的人工声明模板](RELEASE_ATTESTATION.example.json)
- [完整自动化测试](tests/test_release_round.py)

**发布状态**：第 20 篇代表主线教程完成与 Release Candidate 准备，不是用户 Windows 现场验收完成，也不是 GitHub 产品 Release 已经创建。
