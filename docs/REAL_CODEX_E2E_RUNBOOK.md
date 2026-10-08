# Windows 11 + Codex 真实端到端验收工作单（第 21 篇）

> **当前状态：NOT_VERIFIED。** GitHub Actions Windows Runner 不是你的 Windows 11 电脑，更不是一次你真正启动的 Codex 会话。本单必须由你在本机观察填写；不能把模拟事件、离线导出或 AI 编造的截图当真。

## 0. 最安全的准备方法

在 **Anaconda Prompt（CMD）**，先确认 `git`、`python`、`codex` 都是你预期的版本：

```bat
conda activate torch_env
where python
python --version
git --version
codex --version
```

不要覆盖原有 `D:\program\agent_watchdog\watchdog`。在**新的独立目录**克隆本轮成果（请事先确认目标目录不存在）：

```bat
git clone --branch feature/aw-v2-round1-21-24 https://github.com/colddreamxiaowd/Agent-Watchdog.git D:\program\agent_watchdog\Agent-Watchdog-v2-eval
cd /d D:\program\agent_watchdog\Agent-Watchdog-v2-eval
python -m unittest discover -s examples\v04\tests -v
```

这会运行代码测试，但不启动真实 Codex。路径按本机实际情况调整。把这份 **v2 克隆文件夹**作为 ```python 的源码根目录；旧文件绝不覆盖。

## 1. 新建一次性 Git 练习仓库

```bat
mkdir D:\program\agent_watchdog\hook_demo_v2
cd /d D:\program\agent_watchdog\hook_demo_v2
git init
git config user.name "Watchdog Test"
git config user.email "watchdog-test@example.invalid"
echo # Demo goal> GOAL.md
echo Original baseline> demo.txt
git add GOAL.md demo.txt
git commit -m "isolated baseline"
mkdir .codex
```

注意：已有 `hook_demo_v2` 时不得照抄这组建仓命令覆盖。保存重要工作到别处再开始。

在 `.codex\hooks.json` 用记事本**自行审查后创建**下面的项目级配置。`COMMAND_PATH` 必须替换成实际安装到的 Runner 绝对路径，以双反斜杠写 JSON；已有 Hook 不能盲目合并或复制两次：

```json
{
  "hooks": {
    "PreToolUse": [{"hooks": [{
      "type": "command",
      "command": "cmd.exe /d /c \"D:\\program\\agent_watchdog\\Agent-Watchdog-v2-eval\\examples\\v04\\watchdog\\hook_runner_v21.cmd\"",
      "timeout": 10
    }]}],
    "PostToolUse": [{"hooks": [{
      "type": "command",
      "command": "cmd.exe /d /c \"D:\\program\\agent_watchdog\\Agent-Watchdog-v2-eval\\examples\\v04\\watchdog\\hook_runner_v21.cmd\"",
      "timeout": 10
    }]}],
    "Stop": [{"hooks": [{
      "type": "command",
      "command": "cmd.exe /d /c \"D:\\program\\agent_watchdog\\Agent-Watchdog-v2-eval\\examples\\v04\\watchdog\\hook_runner_v21.cmd\"",
      "timeout": 10
    }]}]
  }
}
```

在同一 CMD 终端确保 `python` 对 Codex 可见，或者设置 `WATCHDOG_PYTHON` 为 `where python` 的完整绝对路径。请先人工打开 Runner 核对脚本内容；**不绕过 /hooks 的信任提示**。

## 2. 用独立证据先建立基线

```bat
cd /d D:\program\agent_watchdog\Agent-Watchdog-v2-eval\examples\v04\watchdog
python evidence.py --repo "D:\program\agent_watchdog\hook_demo_v2" baseline
python doctor_v21.py --repo "D:\program\agent_watchdog\hook_demo_v2"
```

`doctor` 只检查就绪条件；输出始终 `real_codex_end_to_end=NOT_VERIFIED`，不能被它自动改成通过。基线只建一次；后续不要为了掩盖越界重新运行 `baseline`。

## 3. 真实 Codex 会话观察（不能用 echo 替代）

第一个终端从 `hook_demo_v2` 启动 `codex`，先执行 `/hooks`，核查配置、命令路径及明确的信任状态。只对审查过的测试 Hook 授权。

给 Codex 这个测试任务（工作区内操作，观察实际实现过程）：

> 只在当前练习仓库新建 `add.py`，实现 `add(a, b)` 并用 Python 验证 `add(2,3)==5`。不得修改 `GOAL.md`，不得更改其他项目，不要读取用户私有文件。

第二个终端可先使用 **PowerShell** 只查看本机脱敏事件（不要推送日志）：

```powershell
Get-Content "D:\program\agent_watchdog\Agent-Watchdog-v2-eval\examples\v04\watchdog\logs\events.jsonl" -Tail 12 -Wait
```

确认至少一个 `PreToolUse/PostToolUse` 事件来自**当次**交互，时间、实际使用的工具、会话 ID、调用 ID 与 UI 手工匹配（请注意，并非所有工具走 Hook 路径）。如果只看到手工试验留下的 `demo` 数据，**不通过**。

再从 CMD 执行：

```bat
cd /d D:\program\agent_watchdog\Agent-Watchdog-v2-eval\examples\v04\watchdog
python bridge.py --repo "D:\program\agent_watchdog\hook_demo_v2" --once
python journal.py sync --log logs\events.jsonl
python runtime_v2.py --events logs\events.jsonl
python doctor_v21.py --repo "D:\program\agent_watchdog\hook_demo_v2"
```

`PostToolUse` 的存在不等于 `SUCCEEDED`；缺少数值返回码时应显示 `UNKNOWN`，属于**正确的保守行为**。

## 4. 反例与误报控制

1. 用 PowerShell 构造手工 JSON 输入，只能证明 Logger 代码可用，必须标 `SYNTHETIC`；不要据此勾选真实 Codex。
2. 停止本机 Codex 或进入休眠后，长时间没有事件只说明观测不足，不能凭此证明执行已死锁。`runtime_v2` 的 `SUSPECTED_STALL` 只在存在未见终态的配对调用时产生，且仍须人工复核。
3. 另一个普通终端手工修改 `demo.txt`，Git 会发现文件内容变化，但不能归因到 Codex。若误归因即验收失败。
4. 不要擅自运行陌生项目里的测试。`task_contract.py verify` 必须在测试合同经过你核验与批准后由人显式发起。

## 5. 本机人工见证记录（保存在私有目录，不上传 GitHub）

| 字段 | 现场填写 |
|---|---|
| 日期/本地时区 | 待填写 |
| `git --version` / `python --version` / `codex --version` | 待填写 |
| 被测试仓库绝对路径 / Git HEAD | 待填写 |
| Hook 配置路径 / `/hooks` 审核是否通过 | 待填写 |
| Codex 实际执行工具、UI 时间 | 待填写 |
| JSONL 脱敏记录时间 / `session_id` / `tool_use_id`（只保留部分） | 待填写 |
| Git 独立扫描有没有反映真实变化 | 待填写 |
| 非零结果是否确实从字段读出、无字段是否 UNKNOWN | 待填写 |
| 多会话污染 / 休眠 / 无事件反例 | 待填写 |
| 隐私、安全、回退检查 | 待填写 |
| 最终 G1 判定 | **NOT_VERIFIED，待本人填写与复核** |

## 6. 故障定位

| 现象 | 先查 |
|---|---|
| `codex` 命令找不到 | PATH、CLI 是否安装 |
| `/hooks` 未加载 | 项目受信任情况、JSON 语法、CLI 版本、是否从练习仓库启动 |
| 手工 Hook 正常但真实事件没有 | 信任审批、Runner 指向的 Python、支持哪些 tool path；不假设所有工具都触发 |
| 事件有了但 Bridge 不更新 | `cwd` 是否在目标 Git repo、日志是否同一目录、Bridge 进程是否运行 |
| 工具完成但 `UNKNOWN` | 允许的数值结果字段未出现，不是代码强制报错 |
| Windows SQLite 文件占用 | 排查未关闭的 `sqlite3.Connection`，先运行当前分支的回归测试 |
| `STALE` | 测试后文件发生变化；在明确授权下重新运行相关独立测试 |
| 结束 Rich/CLI 看板时 Codex 停止 | 不符合“监视器独立运行”目标，需要复核 Runner 是否主动干预 |

回退只需移除**此次新测试项目**的 `.codex\hooks.json` 并重启对应 Codex 会话；千万不要误删原有项目配置。日志不要发公开仓库或公开 Issue。
