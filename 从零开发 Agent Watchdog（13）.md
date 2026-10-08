# 从零开发 Agent Watchdog（13）：第一次完整联调——让“能运行的模块”变成“可信的监督链路”

系列教程 · 第 13 篇 | Windows 11 · Codex CLI · Hooks · Git · SQLite · 端到端验收

上一节，我们已经能够备份 SQLite、生成任务交接摘要，以及在监督器重启后重新计算 Git 证据。乍看之下，Watchdog 的主要组件都已经齐了：`hook_logger_v04.py`、`bridge.py`、`evidence.py`、`task_contract.py`、`journal.py` 和 `monitor04.py`。

但是，“这些程序分别能运行”和“它们真的监督了你电脑上的 Codex”是两件完全不同的事。

想象这样的场景：你启动两个终端，面板显示 `PostToolUse`，Git 变化数量也变成 1。你兴奋地认为完成了联调。实际上这条 `PostToolUse` 可能只是刚才手工 `echo` 进去的；那个文件可能是你自己在 VS Code 里修改的；测试显示 `PASSED` 也可能对应昨天的代码。**把三个无关的现象拼在一起，不等于建立了可靠的因果证据链。**

本篇要做的不是再堆一个模型，而是给第 01–12 篇交一次工程答卷：哪些模块连通、哪些现象来自模拟、哪些已经在真实 Codex CLI 里验证，以及哪些仍不可判断。

## 一、完成这一篇，你应该交付什么？

我们要得到四样东西：

1. 一份能够在你的 Windows 环境运行的**联调检查报告**，它只读 Git 与日志，不会控制 Codex。
2. 一套逐步升级的联调实验：单模块 → 模拟链路 → 真实 Codex → 反例验证。
3. 一张由你亲自填写的**真实验收记录**，包含时间、会话、仓库、失败与修复情况。
4. 一条明确的红线：报告不能因为看到了 `source=codex_hook` 字符串，就自动宣布真实 Codex 验收成功。

我们新增的文件只有一个：[`integration_check.py`](examples/v04/watchdog/integration_check.py)。它位于原来的 `examples/v04/watchdog/` 里，直接调用旧版 `bridge.scan()`、`task_contract.acceptance_status()` 和 `journal.summary()`，不重写你熟悉的证据检查器。

```text
真实 Codex CLI（需要你本机确认）      人工模拟输入（仅用于单元测试）
              │                                 │
              └────────────┬────────────────────┘
                           ▼
                  hook_runner_v04.cmd
                           ▼
                   hook_logger_v04.py
                           ▼
                   logs/events.jsonl
                           ▼
                 bridge.py ──→ evidence.py
                           ▼
                  Git 事实 / 测试状态
                           ▼
              integration_check.py  ← 读取 SQLite / 合同
                           ▼
                 机器可核查的准备状态
                           +
                人工确认真实 Codex 来源
                           ▼
                       联调验收
```

请留意流程最下方的“人工确认”。这是有意保留的。当前 Logger 接收到的是标准输入中的 JSON，它没有对输入程序做身份认证；任何能调用 Logger 的程序都可以构造一条类似的事件。我们不能把一个字段值当作安全证明。

## 二、准备环境：不要覆盖你已经写好的代码

以下命令以 **Anaconda Prompt / cmd** 为例，而不是 PowerShell。路径来自你项目原来的约定：

```bat
conda activate torch_env
cd /d D:\program\agent_watchdog
where python
python --version
git --version
codex --version
```

如果 `codex --version` 不存在，先确认你实际使用的是 Codex CLI 还是桌面扩展；不要为了修这个报错重装 CUDA 或 PyTorch。本篇不使用 StepWise，也不需要下载模型。

把本仓库新版 `examples/v04/watchdog/integration_check.py` 复制到你原来的 `watchdog` 目录。其他脚本应当先与仓库 `examples/v04/watchdog/` 核对，**不要因为示例目录里存在同名文件，就批量覆盖自己本机已经修改过的 `evidence.py`**。

完成后应当类似：

```text
D:\program\agent_watchdog\
├── hook_demo\              # 单独的 Git 实验仓库
│   ├── .codex\hooks.json   # 受信任项目的 Hook 设置
│   ├── hello.py
│   ├── test_hello.py
│   └── GOAL.md
└── watchdog\
    ├── evidence.py          # 第 03 篇
    ├── hook_runner_v04.cmd
    ├── hook_logger_v04.py
    ├── bridge.py            # 第 04 篇
    ├── task_contract.py     # 第 05–06 篇
    ├── journal.py           # 第 09 篇
    ├── monitor04.py         # 第 04/08 篇
    ├── integration_check.py # 第 13 篇新增
    ├── logs\events.jsonl
    ├── state\...
    └── data\journal.sqlite3
```

有一条容易混淆的命令：`cd /d` 是 cmd 的写法。若你使用 PowerShell，直接执行 `Set-Location D:\program\agent_watchdog\watchdog` 即可。不要在 PowerShell 里把 cmd 的所有语法照搬过来。

## 三、我们先设计一个绝对不能误判的反例

假设你从未启动 Codex，仅用 Python 伪造了一行：

```json
{"event":"PostToolUse","source":"codex_hook","cwd":"D:\\program\\agent_watchdog\\hook_demo"}
```

如果一个监控器看到 `source` 是 `codex_hook` 就报告“真实接入完成”，那么任何人都能让它通过验收。我们在 `integration_check.py` 中故意返回以下字段：

```json
{
  "hook_records_observed": 1,
  "hook_events_are_authenticated": false,
  "real_codex_end_to_end": "NOT_VERIFIED"
}
```

这不是功能做得不够多，而是**一个经过明确设计的安全边界**。它回答的是“我观察到了符合格式的事件”，不是“我证明了事件来自 Codex”。

核心逻辑大致相当于：

```python
report = bridge.scan(repo, "integration-readiness")
state = task_contract.acceptance_status(repo)
database = journal.summary(db)

result = {
    "git": report,
    "contract_stage": state["stage"],
    "journal_integrity": database["integrity"],
    "real_codex_end_to_end": "NOT_VERIFIED"
}
```

完整源码已经放在 [`integration_check.py`](examples/v04/watchdog/integration_check.py)，而不是让你从页面上复制缺少换行的 Python 大段代码。

**进一步的原理：** 程序只统计日志中带有事件名称、且 `cwd` 属于被监控 Git 仓库的完整 JSONL 行；不把 `tool_input`、命令参数或工具输出装进报告。它还会重新扫描 Git 工作树，所以即便所有 Hook 事件都丢失了，独立的文件变化仍然可能被检测出来。

## 四、实验 A：不用 Codex，验证检查器能够正常启动

先在隔离的 Git 测试仓库执行：

```bat
cd /d D:\program\agent_watchdog\watchdog
python evidence.py --repo "D:\program\agent_watchdog\hook_demo" scan
python bridge.py --repo "D:\program\agent_watchdog\hook_demo" --once
python integration_check.py --repo "D:\program\agent_watchdog\hook_demo"
```

如果没有合同、没有 SQLite，也不应该抛出一连串莫名其妙的异常。你可能会看到以下**示意输出**：

```json
{
  "hook_log_exists": false,
  "hook_records_observed": 0,
  "journal_exists": false,
  "journal_integrity": "NOT_CHECKED",
  "contract_stage": "NO_CONTRACT",
  "real_codex_end_to_end": "NOT_VERIFIED"
}
```

这个实验通过的条件是脚本退出码为 0、能拿到仓库扫描信息，而不是输出变绿。如果仓库尚未建立基线，请返回第 03 篇明确执行 `baseline`；不要为了让界面好看而悄悄重建基线，因为那会改变今后文件变化的参照点。

## 五、实验 B：模拟事件 + Git 实际变化

开第一个 Anaconda Prompt 运行 Bridge：

```bat
conda activate torch_env
cd /d D:\program\agent_watchdog\watchdog
python bridge.py --repo "D:\program\agent_watchdog\hook_demo"
```

第二个终端打开面板：

```bat
conda activate torch_env
cd /d D:\program\agent_watchdog\watchdog
python monitor04.py --repo "D:\program\agent_watchdog\hook_demo"
```

第三个终端模拟一次文件修改：

```bat
cd /d D:\program\agent_watchdog\hook_demo
echo # chapter13 simulation>>hello.py
```

然后用 PowerShell 生成正确的 JSON，避免 Windows `echo` 在引号和反斜杠上产生歧义：

```powershell
$event = @{
  hook_event_name = "PostToolUse"
  tool_name = "Bash"
  session_id = "SIMULATED-13"
  cwd = "D:\program\agent_watchdog\hook_demo"
} | ConvertTo-Json -Compress
$event | & "D:\program\agent_watchdog\watchdog\hook_runner_v04.cmd"
```

回到第一个终端，应当看到新的 Git 扫描；第二个终端应当显示文件变化或测试证据状态更新。**这里有两个独立事实**：第一，你的输入成功写入 Logger；第二，Bridge 读到了当前 Git 文件内容。它们还不能证明修改是由 Codex 执行的，因为本实验就是你自己手工改的文件。

如果 Bridge 未更新，按顺序检查：日志末尾是否新增记录 → 记录中是否存在 `cwd` → `cwd` 是否属于所监控的 Git 根目录 → Bridge 是否仍在运行 → 防抖与最短扫描间隔是否已经满足。不要第一反应就重新安装 Conda。

## 六、实验 C：真正的 Codex 端到端验收

前面的实验只能证明自己的代码可以配合。现在才轮到真实 Codex。

请先检查 `hook_runner_v04.cmd` 中 Python 的**绝对路径**与 Logger 文件路径，确保使用你实际的 Conda 环境。再检查 `hook_demo/.codex/hooks.json` 是否指向这一 Runner，且没有重复添加同一个 Hook。

在测试仓库启动：

```bat
cd /d D:\program\agent_watchdog\hook_demo
codex
```

进入 CLI 后，按当前版本提供的 Hook 管理入口检查配置和信任状态（支持时可使用 `/hooks`）。确保不是在未经检查的情况下放行外部命令 Hook。然后输入这个**最小、低风险的任务**：

> 在当前测试仓库创建 `chapter13_probe.py`，包含 `def add(a, b): return a + b`，用 Python 运行一次 `add(2,3)` 验证返回 5。不要修改 `GOAL.md` 或其他仓库。

请记录实验时间和 Codex 会话标识；再检查 `events.jsonl`、Bridge 终端和 `git status`。只有你明确知道“这个工具操作实际在 Codex 中发生”“Hook 配置已经由当前 CLI 加载”“新增事件发生在对应时间窗口”时，才能在**人工验收记录**写“已确认真实接入”。`integration_check.py` 故意不会替你自动填写这一项。

> 官方依据：Codex Hooks 的事件与项目级信任要求见 [Hooks 文档](https://developers.openai.com/codex/hooks)。Hook 覆盖并非所有内部执行路径，不能因此把它当作无遗漏的全量审计。

### 一张可以真的填写的验收表

| 需要验证的事实 | 你应保存的证据 | 状态 |
|---|---|---|
| Codex CLI 在测试仓库启动 | `codex --version`、启动目录 | 待本机填写 |
| Hook 已加载并受信任 | `/hooks` 截图或等价界面记录 | 待本机填写 |
| Codex 完成一次工具操作 | 当前会话中的操作结果 | 待本机填写 |
| Logger 收到同时间窗口的事件 | 脱敏 JSONL 摘要 | 待本机填写 |
| Git 独立扫描观察到目标文件 | `bridge.py --once` 报告 | 待本机填写 |
| A1 测试通过、修改后会 STALE | `task_contract.py status` | 待本机填写 |
| 关闭并重启面板后仍能恢复 | 数据库与 Git 再扫描 | 待本机填写 |

表中任何一个“待填写”，都意味着第 13 篇的**用户本机完整验收尚未闭合**。不要因为文章已经写完而将其自动替换为“成功”。

## 七、实验 D：让测试通过，然后故意让证据失效

当你已经按第 05–06 篇批准合同后，先执行：

```bat
python task_contract.py --repo "D:\program\agent_watchdog\hook_demo" status
python task_contract.py --repo "D:\program\agent_watchdog\hook_demo" verify A1
```

然后在 `hello.py` 中添加一行注释，重新执行 `status`。如果文件快照改变，旧的 A1 应当显示 `STALE`。这个机制虽然保守（注释也会触发重新检查），但它能够避免把旧测试结果移植到新代码。注意：**此命令会执行合同中指定的测试程序**，必须先审核合同，只能在可信仓库里主动调用；Bridge 和 Hook 不会自动运行它。

## 八、为什么我们的联调报告不自动标 `PASS`？

工程里存在不同等级的证据：

| 来源 | 可以支持什么 | 无法支持什么 |
|---|---|---|
| 模拟 Hook 事件 | Logger 能解析格式 | 真实 Codex 已运行 |
| 真实 Hook 日志 + 本机操作记录 | 某些 Codex 事件已被观察 | 所有操作都被观察 |
| Git 文件快照 | 当前受监控文件变化 | 必定是谁修改的 |
| 测试退出码 0 | 指定测试在指定快照返回成功 | 项目所有目标都完成 |
| 合同中所有验收条件 PASSED | 已配置条件具备当前证据 | 未配置的自然语言要求均已满足 |

这正是 Agent Watchdog 与普通“AI 运行看板”的核心区别：**我们宁愿输出一个真实的 `UNKNOWN`，也不要输出没有证据的 `SUCCESS`。**

## 九、常见故障与定位顺序

**Hook 日志没新增。** 检查是从哪个目录启动 Codex、项目是否受信任、`.codex/hooks.json` 是否被当前版本读取、Runner 的 Python 路径是否正确、Runner 手工测试是否输出 `{}`。不要根据聊天窗口看起来在推理，就断言一定应该有 `PostToolUse`。

**Bridge 报仓库路径不匹配。** 同一台电脑可能同时有几个 Codex 项目。`cwd` 是一条路由线索，不是强认证；确认配置的 Git 仓库根目录与本次任务工作目录一致。

**`TEST_STALE` 一直出现。** 检查是否在测试之后有未忽略文件被改变（包括生成文件）。如果是临时缓存，按合理的 `.gitignore` 管理；不要通过重建基线来掩盖问题。

**SQLite 读不到事件。** `journal.py` 是一个明确执行的导入命令，Hook 追加 JSONL 并不等于 SQLite 自动同步。先运行 `python journal.py sync`，再用 `python journal.py summary` 核对。下一阶段才考虑更完善的调度。

## 十、课后练习与本篇总结

练习一：预测“只有模拟事件而没有文件变化”时联调报告各字段如何变化。练习二：修改 `GOAL.md`，预期 Bridge 会怎样报告？练习三：说明为什么真实 Codex 中某条命令成功执行，不等于所有合同验收条件都已通过。

本篇已经给了你一个能运行的**联调准备检查器**，也把真正的 Windows 端到端验证变成了有证据的操作流程。源代码在隔离测试中经过验证，但**你本机的真实 Codex 验收仍需要按表填写**。

下一篇，我们讨论更深一层的问题：Hook 只提供有限的元数据。如果要看 `thread / turn / item` 这种细分执行状态，应该怎样借助 Codex App Server 的结构化事件，同时又不保存用户提示和工具原始输出？

延伸阅读：[Codex Hooks](https://developers.openai.com/codex/hooks) · [Git ls-files](https://git-scm.com/docs/git-ls-files) · [本篇源文件](examples/v04/watchdog/integration_check.py) · [相关测试](examples/v04/tests/test_next.py)。
