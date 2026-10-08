# 从零开发 Agent Watchdog（04）：把 Codex 事件、Git 检查和实时监控面板连接起来

系列教程 · 第 4 篇（重新整理版） | Windows 11 · Python · Git · Codex Hooks

前三篇，我们分别实现了三个模块：

- `hook_logger.py`：接收 Codex 的执行事件。
- `monitor.py`：显示实时事件。
- `evidence.py`：检查文件变更、受保护文件和测试证据。

但它们还没有真正连接起来。

例如，Codex 修改了 `hello.py`，Hook 虽然记录了事件，却不会自动更新 Git 检查结果。用户仍然需要手动输入 `python evidence.py ... scan`。

本篇目标：让 Codex 完成操作后，Watchdog 自动更新证据状态，并显示在实时面板上。

## 一、我们要实现的效果

V0.4 系统工作流程

Codex

修改代码、执行工具

Hook Logger

只保存必要的事件元数据

Bridge · 新增模块

合并事件、节流、触发 Git 检查

Evidence

检查文件变化、保护文件、测试证据是否过期

Monitor 04

在独立终端实时展示结果

这里最重要的改变，是新增了 Bridge（事件桥接器）。

我们不让 Hook 直接扫描整个仓库，因为 Codex 可能连续执行几十次工具操作。如果每次 Hook 都计算所有文件的 SHA-256，就可能让 Agent 变慢。

因此我们改成两个独立过程：

轻量 Hook 负责记录，Bridge 负责合并事件后扫描。

这也是后续接入 StepWise、异常提醒和任务验收系统时可以继续复用的架构。

## 二、本篇源码已经准备好

我保留了与你前面教程相兼容的模块接口，并完成了桥接器、监控面板和测试用例。

Agent Watchdog 04 源码包

包含 Python 源码、安装说明与集成测试

&#x20;下载 Agent Watchdog 04 完整 ZIP

核心文件

`bridge.py` 查看源码

`monitor04.py` 查看源码

`hook_logger_v04.py` 查看源码

`README.md` 查看使用说明

新的 Python 代码已在隔离测试环境运行，3 项自动化集成测试全部通过，覆盖文件证据失效、日志脱敏、跨仓库隔离与事件节流等行为。



这并不等于已经在你的 Windows Codex 环境验收成功。下面就来完成这一部分。

## 三、安装源码：只新增三个文件

先解压下载的 ZIP。

把下面三个文件复制到你现有的：

`D:\program\agent_watchdog\watchdog`

| 文件                   | 作用                 |
| -------------------- | ------------------ |
| `hook_logger_v04.py` | 接收带有仓库路径的 Codex 事件 |
| `bridge.py`          | 自动触发 Git 证据检查      |
| `monitor04.py`       | 显示事件与证据状态          |

压缩包里也包含 `evidence.py`、`monitor.py` 和 `watchdog_rules.json`，方便完整复现。但如果你已经修改过这些文件，不要直接覆盖原文件。

这次的目录应该变为：

```
D:\program\agent_watchdog\
│
├── StepWise\
│
├── hook_demo\
│   └── .codex\
│       └── hooks.json
│
└── watchdog\
    ├── hook_logger.py
    ├── hook_logger_v04.py     ← 新增
    ├── hook_runner.cmd
    ├── monitor.py
    ├── monitor04.py           ← 新增
    ├── evidence.py
    ├── bridge.py              ← 新增
    ├── watchdog_rules.json
    │
    ├── logs\
    │   └── events.jsonl
    │
    └── state\
        └── ...\
```

打开 Anaconda Prompt：

```
conda activate torch_env
cd /d D:\program\agent_watchdog\watchdog
```

检查所需环境：

```
git --version
python -c "import rich; print('Rich OK')"
```

如果 Rich 没装，才需要执行：

```
python -m pip install rich
```

本篇不用再次运行 ModernBERT，也不用下载任何 AI 模型。

## 四、升级 Hook：让事件携带仓库路径

这是本篇第一个关键改动。

上一版的日志类似：

```
{
  "event": "PostToolUse",
  "tool": "Bash",
  "session_id": "abc"
}
```

但存在一个问题：

假设你同时运行两个 Codex：

```
Codex A → 项目 A
Codex B → 项目 B
```

Bridge 怎么知道事件来自哪一个项目？

答案是增加 `cwd` 字段。

Codex 官方 Hook 事件有 `cwd` 字段，表示当前会话的工作目录。

[image](https://www.google.com/s2/favicons?domain=https://developers.openai.com\&sz=32)

ChatGPT Learn



新版事件：

```
{
  "event": "PostToolUse",
  "tool": "Bash",
  "session_id": "abc",
  "cwd": "D:\\program\\agent_watchdog\\hook_demo"
}
```

我们的 Bridge 会确认这个目录属于正在监控的 Git 仓库。

### 修改 hook_runner.cmd

先备份原文件。在 `watchdog` 目录执行：

```
copy hook_runner.cmd hook_runner.backup.cmd
notepad hook_runner.cmd
```

把里面原来的：

```
hook_logger.py
```

改成：

```
hook_logger_v04.py
```

修改后应类似：

```
@echo off
"D:\你的Anaconda路径\envs\torch_env\python.exe" "D:\program\agent_watchdog\watchdog\hook_logger_v04.py"
```

这里第一段 Python 路径必须使用你自己电脑的真实路径。可以通过：

```
where python
```

查找。

不要照搬示例里的 `D:\你的Anaconda路径`。

为什么不直接把 `evidence.py` 放在 Hook 里运行？

因为 Hook 应该尽快完成。我们希望 Codex 正常执行时，额外开销尽量小。

Hook 只追加一条日志，扫描由独立的 Bridge 负责。

## 五、理解 Bridge：为什么不在每次事件后立即扫描？

假设 Codex 连续完成了五次工具调用：

```
13:00:01  PostToolUse
13:00:02  PostToolUse
13:00:03  PostToolUse
13:00:04  PostToolUse
13:00:05  PostToolUse
```

如果每条事件都触发完整 Git 检查，会产生五次扫描。

我们暂时没有必要这么做。

Bridge 采用了三个参数：

| 参数             | 默认值  | 含义                    |
| -------------- | ---- | --------------------- |
| `debounce`     | 2 秒  | 事件短暂停止后再扫描            |
| `min_interval` | 5 秒  | 两次扫描至少间隔这么久           |
| `max_delay`    | 10 秒 | 事件持续不断时，最多等待约这么久再尝试扫描 |

例如：

```
13:00:01  第一次工具完成
13:00:02  第二次工具完成
13:00:03  第三次工具完成
13:00:04  第四次工具完成
          │
          │ 2 秒没有新事件
          ▼
13:00:06  Git 扫描一次
```

这样能够减少重复工作。

注意：这些参数不代表严格的十秒扫描时限。 如果正在执行的文件扫描本身耗时很长，下一次扫描仍然会延迟。

此外，Bridge 只会响应已记录的：

`PostToolUse`、`Stop` 和 `SessionEnd`

它不会因为收到 `PreToolUse` 就开始扫描。

这是为了优先观察操作完成后的状态。

## 六、启动 Bridge：第一次自动证据检查

打开第一个终端。

执行：

```
conda activate torch_env
cd /d D:\program\agent_watchdog\watchdog
```

先运行一次单独扫描：

```
python bridge.py --repo D:\program\agent_watchdog\hook_demo --once
```

`--once` 的作用是只扫描一次，然后退出。

如果你已经按照第三篇创建基线，可能看到：

```
[Bridge] Watching Git repo: D:\program\agent_watchdog\hook_demo
[Bridge] Reading hook events: ...

[SCAN] ...
changed=2 | protected=1 | tests=STALE
```

这里的数字取决于你之前是否修改了 `GOAL.md`、`hello.py` 等文件。

如果显示：

```
changed=?
```

通常表示尚未建立基线。

此时先按第三篇教程执行一次 `evidence.py ... baseline`。之后不要随意重建基线，否则会覆盖用于比较的初始状态。

接着正式启动持续监听：

```
python bridge.py --repo D:\program\agent_watchdog\hook_demo
```

保持终端打开。

你应该看到：

```
[Bridge] Watching Git repo: ...
[Bridge] Reading hook events: ...
[Bridge] No tests, no auto-intervention.
```

这表示 Bridge 已开始监控新的日志事件。

这一步不会启动 Codex，也不会运行测试命令。

## 七、启动升级后的实时面板

打开第二个 Anaconda Prompt：

```
conda activate torch_env
cd /d D:\program\agent_watchdog\watchdog
```

执行：

```
python monitor04.py --repo D:\program\agent_watchdog\hook_demo
```

此时，你的面板会分成两个区域。

CODEX REAL-TIME EVENTS

Session       demo-v04 Latest event  PostToolUse Latest tool   apply_patch  Tool started  3 Tool ended    3

GIT / TEST EVIDENCE

Baseline      Available Changed files 2 Protected     GOAL.md Test status   STALE Last scan     13:24:06

示意界面，真正的 Python 程序使用 Rich 表格展示，内容以实际扫描为准。

现在你能同时看到：

Codex 最近发生了什么事件，以及当前代码仓库有哪些实际变化。

如果没有事件，面板可能提示没有带 `cwd` 的 Hook 日志。这时不要急着怀疑 Git 检查有问题，因为 Bridge 的初始扫描和实时事件采集是两条不同的数据路径。

## 八、先进行一次不依赖 Codex 的模拟测试

接下来验证真正的自动联动。

保持前面两个终端打开。

打开第三个 Anaconda Prompt：

```
conda activate torch_env
cd /d D:\program\agent_watchdog\hook_demo
```

### 第一步：修改测试文件

我们先模拟 Codex 修改代码。

执行：

```
echo # V04 integration test>>hello.py
```

这会向 `hello.py` 末尾追加一行注释。

现在文件发生了变化，但 Bridge 不一定立即扫描，因为还没有收到新 Hook 事件。

### 第二步：模拟一次 PostToolUse

在同一个终端执行：

```
echo {"hook_event_name":"PostToolUse","tool_name":"Bash","session_id":"demo-v04","cwd":"D:\\program\\agent_watchdog\\hook_demo"} | D:\program\agent_watchdog\watchdog\hook_runner.cmd
```

这里特别注意：

JSON 中的 Windows 路径需要使用双反斜杠 `\\`。

执行完成时，终端可能输出：

```
{}
```

这不是错误。

新版 Hook 使用空 JSON 对象作为不干预的输出，不会要求 Codex 阻止、重试或修改执行过程。官方对 `Stop` 等事件也要求使用合法的 JSON 输出。

[image](https://www.google.com/s2/favicons?domain=https://developers.openai.com\&sz=32)

ChatGPT Learn



### 第三步：检查 Bridge

观察第一个终端。

应该出现新的：

```
[SCAN] ...
changed=...
protected=...
tests=STALE
trigger=PostToolUse
```

如果之前第三篇的测试通过了，但我们现在又修改了 `hello.py`，那么 `tests=STALE` 是合理的。

### 第四步：查看监控面板

切回第二个终端。

你应该能看到最近事件更新为 `PostToolUse`，并看到最新 Git 证据状态。

这就是本篇最核心的一次验收：

文件被修改 → Hook 事件被记录 → Bridge 自动扫描 → 面板更新。

通过标志

当 `bridge.py` 终端出现由 `PostToolUse` 触发的新扫描，并且 `monitor04.py` 显示该仓库的最新结果时，说明模拟端到端链路已打通。

## 九、最后连接真实 Codex

模拟成功后，再用真实 Codex 验证。

第三个终端中执行：

```
cd /d D:\program\agent_watchdog\hook_demo
codex
```

进入 Codex 后，输入：

```
/hooks
```

检查 `PostToolUse`、`Stop` 等 Hook 是否启用，并在需要时审核本地脚本。

Codex 官方说明，项目级 Hook 位于受信任项目的 `.codex/hooks.json` 中；非托管 Hook 还需要审核和信任。不要使用跳过 Hook 信任审查的选项。

[image](https://www.google.com/s2/favicons?domain=https://developers.openai.com\&sz=32)

ChatGPT Learn



如果你前面尚未创建 `.codex/hooks.json`，可以在 `hook_demo` 目录创建如下测试配置：

```
{
  "hooks": {
    "PreToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "cmd.exe /d /c D:\\program\\agent_watchdog\\watchdog\\hook_runner.cmd",
            "timeout": 10
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "cmd.exe /d /c D:\\program\\agent_watchdog\\watchdog\\hook_runner.cmd",
            "timeout": 10
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "cmd.exe /d /c D:\\program\\agent_watchdog\\watchdog\\hook_runner.cmd",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

如果已有配置并且正常工作，不要重复添加同样的 Hook，否则可能产生重复日志。

然后给 Codex 一个简单任务：

测试任务

在当前测试仓库内创建 `feature_v04.py`，编写一个 `add(a, b)` 函数并返回两个参数的和。然后运行一个简单命令验证 `add(2, 3) == 5`。不要修改 `GOAL.md`，也不要访问其他仓库。

&#x20;复制任务

然后观察面板。

如果 Codex 实际调用了支持 Hook 的本地工具，我们应该能看到相应事件和新的文件变化。

需要说明的是，Codex 官方也明确指出：部分托管工具及特殊执行路径不通过普通工具 Hook。因此，Hook 可以提供有用的执行信号，却不能保证捕获所有 Agent 操作。

[image](https://www.google.com/s2/favicons?domain=https://developers.openai.com\&sz=32)

ChatGPT Learn



## 十、理解本篇的工程边界

现在这个系统虽然已经能把三个模块连接起来，但仍有一些限制。

| 能力                | V0.4 情况   |
| ----------------- | --------- |
| 自动接收 Hook 事件      | 支持，需要实际配置 |
| 按仓库过滤事件           | 支持        |
| 连续事件节流扫描          | 支持        |
| 自动检测 Git 可见文件变化   | 支持        |
| 检查受保护文件变化         | 支持        |
| 判断已记录的测试是否过期      | 支持        |
| 自动重新运行测试          | 不执行       |
| 判断是否违反语义性任务目标     | 尚未实现      |
| 判断 Codex 是否真正完成任务 | 尚未实现      |
| 自动暂停或纠正 Codex     | 不执行       |

其中有三条特别重要的安全边界。

首先，它不会自动运行测试。如果需要更新测试证据，仍然使用第三篇的显式命令：

```
python evidence.py --repo D:\program\agent_watchdog\hook_demo test -- python -m unittest discover -p "test_*.py" -v
```

其次，它监控的是你指定 Git 仓库的当前文件状态。即使某次扫描恰好发生在 Codex 工具完成之后，也不能据此断定每处修改都由 Codex 产生。

最后，这不是实时文件系统审计。Bridge 只在收到匹配事件时定期扫描；部分事件可能缺失，Bridge 重启后也不会自动回放所有历史事件。

因此它更适合称为事件驱动的工作区监督器，而不是安全拦截系统。

## 十一、这一篇完成后，我们真正拥有什么？

现在的工程已经开始形成清晰的结构：

```
Agent Watchdog
│
├── 事件层
│   ├── Hook Logger
│   └── JSONL
│
├── 联动层
│   └── Bridge
│
├── 证据层
│   ├── Git Snapshot
│   ├── Protected Paths
│   └── Test Evidence
│
├── 展示层
│   └── Rich Monitor
│
└── 智能监督层
    └── 尚未实现
```

我们已经有一个可以继续扩展的工程骨架，不再只是几个互相独立的测试脚本。

下一篇 · Agent Watchdog（05）

## 任务契约与独立验收：让 Watchdog 知道用户到底要求完成什么

第五篇将开始接近你最初希望实现的 Agent Supervisor：

```
用户原始要求
      │
      ▼
 Task Contract
      │
      ├── 必须完成什么
      ├── 禁止修改什么
      └── 如何证明完成
      │
      ▼
 实际执行证据
      │
      ▼
 逐条验收状态
```

我们会借鉴 IronLaw 的任务契约和证据验收思想，但实现一套适合自己日常 Codex 开发的轻量版本。

本篇的最终验收标准：不是面板能打开，而是一次真实或模拟的工具操作能够自动触发证据更新。 做到这一步，第四篇才算完成。

参考：Codex 官方 Hooks 文档 · Git 官方文档 · Rich 官方文档
