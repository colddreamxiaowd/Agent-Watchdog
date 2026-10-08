# Windows Codex App + Agent Watchdog 29–32｜真实试用指南（不是已完成的真机验收）

> **现场修订（2026-10-08）**：用户报告当前 Windows Codex Desktop 在**全局 hooks.json + commandWindows + ASCII .cmd 包装器**下已出现真实事件，原文仅项目级的安装步骤不能用来覆盖现有成功配置。请**先读 [Hook 信任修订说明](CODEX_APP_HOOK_TRUST_FIELD_FIX_20261008.md)**，不要再次运行本文件第 2 节的项目级 install。用户的真实信任审核发生在正常交互式 Codex CLI 内的 `/hooks`，并非网页版 ChatGPT，不能用 `--dangerously-bypass-hook-trust` 代替。

**本轮目标客户端：Windows 桌面 Codex App**，不是 `codex exec`、网页 ChatGPT 或独立运行的 CLI。

官方说明：[Codex App on Windows](https://openai.com/index/introducing-the-codex-app/)；[Codex Hooks](https://developers.openai.com/docs/hooks)。App 可运行多线程任务，Hooks 允许在启动、工具前后和回合结束等节点执行命令。**具体 Windows App 版本、信任和沙盒能否写入本机日志，必须在用户电脑上实际核查**，不能将 GitHub Windows Runner 结果当作实机 E2E。不要关闭 App 的隔离机制来让工具跑通。

## 1. 安装观察器：使用新的独立文件夹

在 **Anaconda Prompt（CMD）**，确认 Python/Git 正常。已有同名目录请自行选新名字，不覆盖之前的 `D:\program\agent_watchdog\watchdog`：

```bat
conda activate torch_env
git clone https://github.com/colddreamxiaowd/Agent-Watchdog.git D:\program\agent_watchdog\Agent-Watchdog-app-eval
cd /d D:\program\agent_watchdog\Agent-Watchdog-app-eval
python -m unittest discover -s examples\v04\tests -v
python scripts\validate_round1_docs.py
```

首次克隆完成后，新建**一次性** Git 仓库，仅供 App 测试（若目录已存在，不要覆盖）：

```bat
mkdir D:\program\agent_watchdog\watchdog_app_demo
cd /d D:\program\agent_watchdog\watchdog_app_demo
git init
git config user.name "Watchdog Fixture"
git config user.email "fixture@example.invalid"
echo Watchdog disposable project> GOAL.md
git add GOAL.md
git commit -m "Initial fixture"
```

## 2. 先看配置，不会写入任何 Hook

```bat
cd /d D:\program\agent_watchdog\Agent-Watchdog-app-eval\examples\v04\watchdog
python app_control_v32.py doctor --repo "D:\program\agent_watchdog\watchdog_app_demo"
python app_control_v32.py propose --repo "D:\program\agent_watchdog\watchdog_app_demo"
```

其中 `propose` 只显示将生成的 `hooks.json`。请**人工检查**配置中的 Python 绝对路径、脚本位置和 `PreToolUse/PostToolUse/Stop/SessionStart/SessionEnd`。如果项目已有 `.codex/hooks.json`，不要合并覆盖；另建干净的测试仓库。

人工同意以后，显式写入新配置（只会创建，不覆盖已有）：

```bat
python app_control_v32.py install --repo "D:\program\agent_watchdog\watchdog_app_demo" --ack-reviewed-hooks
```

Hook 代码见 `app_hook_v29.py`；输入只提取脱敏元数据，**不存原始提示/命令/工具输出，也默认不存工作区路径**。日志默认位于 `%LOCALAPPDATA%\AgentWatchdog\events.jsonl`，备份和本地 SQLite 也位于当前 Windows 用户的数据目录。Hook 启动失败应不影响 Codex 工具继续执行。

## 3. 在 Codex App 中真实测试，而不是在终端启动 CLI

打开**Windows Codex App**，选择/打开项目 `D:\program\agent_watchdog\watchdog_app_demo`。寻找 App 中对应版本的 Hook 配置或信任审核；如有可信性提示，确认路径正是你刚审阅的脚本。**不使用危险的 Hook 信任绕过选项、不授予超额沙盒权限。** 若 App 没显示 Hook 或拒绝运行，记录 G1 `NOT_VERIFIED` 并排查，不用人为伪造一条 JSON 假装接入。

在 App 开始任务前，打开第二个 **Anaconda Prompt**：

```bat
conda activate torch_env
cd /d D:\program\agent_watchdog\Agent-Watchdog-app-eval\examples\v04\watchdog
python app_control_v32.py watch --notify
```

这会在前台持续监听；**监控器停止不会结束 Codex App**。首次启动默认跳过旧日志，而当日志原本不存在、监控器先启动时会收集新创建的第一条事件。`--notify` 只对有明确证据的复核事件尝试调用 Windows 气泡提示，具体系统通知权限和是否显示仍需实机检查；即使通知不可用，告警会留在私有 SQLite 中。不建议在首次试用时开启 `--include-existing`。

在 App 里只要求：

> 这是一个一次性练习仓库。只创建 add.py，提供 add(a,b) 函数，并实际调用 add(2,3) 验证等于 5。不要修改 GOAL.md，不要读取外部文件。

另外一个 **PowerShell** 可查看私有日志（不要上传）：

```powershell
Get-Content "$env:LOCALAPPDATA\AgentWatchdog\events.jsonl" -Tail 10 -Wait
```

## 4. 什么证据才允许说“真实 Codex App 接入成功”？

必须同时证明：① App 在对应的测试项目运行；② App 的工具操作实际触发了本次安装的 Hook；③ 本地日志出现与 App UI 时间/会话/工具匹配的全新事件，而非自己手工输入的 fixture；④ 你人工确认是否存在缺失的 Hook 路径；⑤ 关闭监控窗口时 App 能继续工作。用户自己保存截图/本地证据，记录部分脱敏 event_id 即可，不能在公开 GitHub 上传轨迹。

只有在你完成这套操作并提供**去敏后的现场结果**，才能把“真实 Codex App G1 已验证”提请独立复核。源码中的 `doctor` 固定报告 `NOT_VERIFIED`；不会因为看到一个 JSON 文件就自动宣告真机通过。

## 5. 日常使用：状态、日志、恢复

```bat
python app_control_v32.py status
python app_control_v32.py backup
```

`status` 是私有数据库健康检查，不是真实 App 进程保活探测；`backup` 用 SQLite 在线备份，放到同一用户私有目录且不覆盖。备份可能包含脱敏的会话标识，仍然属于私有敏感工作资料。程序**不会自动从备份恢复**，避免把旧审计和旧提醒悄悄覆盖当前状态。关闭前台窗口后再运行 `watch --notify` 会读取持久游标，已记录的事件不会因为重复扫描无限提醒。

### 失败/边界诊断

| 情况 | 正确处理 |
|---|---|
| App 正常但始终没有新日志 | 先检查项目 Hooks 是否加载并受信任、是否使用了正确项目、Python 与 Windows 沙盒权限；不把无日志判死锁 |
| `PostToolUse` 但结果 `UNKNOWN` | Codex 未提供被当前安全解析器接受的明确退出码；不是已通过，也不是失败 |
| 频繁出现 `SUSPECTED_STALL` | 可能休眠、缺少终态或不同工具路径；先看 App，不能自动杀掉它 |
| 多个 Bash FAILED | 默认只是 `FAILURE_CLUSTER_REVIEW`，不是“循环已证实” |
| Windows 不显示通知 | 检查消息显示权限； SQLite 保留告警，但弹窗显示尚未通过验收 |
| 想撤回 Hook | **只删除这个测试仓库新建的** `.codex/hooks.json`，重启相应 App 会话；不要碰其他项目的配置 |
| Codex App 看起来没跟着变化 | Codex App 的真实配置来源、sandbox 和非 CLI 路径可能不同，需要用真实 App 做兼容性排查 |

## 6. 结果登记（用户本地私有）

`G1`：`NOT_VERIFIED`，待实机操作。 `G3`：`NOT_EVALUATED`（无真实标签、precision/recall）。`G4`：`NOT_VERIFIED`（休眠、崩溃、跨天通知、恢复、沙盒覆盖）。

本轮代码+合成 CI 是**可以真正试用的工程基础**；仍未达到可无条件后台托管、完全监督所有 Codex App 行为的正式 V1.0 标准。
