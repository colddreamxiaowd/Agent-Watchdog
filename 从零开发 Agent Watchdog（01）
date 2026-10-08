# 从零开发 Agent Watchdog（01）：让 Codex 的执行过程进入我们自己的监控程序

Python 实战

Windows 11 · Conda · Codex Hooks · JSONL

你已经成功运行了 StepWise 的 ModernBERT 检测模型。但我们的目标并不是复现一篇论文，而是开发一个能长期使用的 AI Agent 智能监督系统。

从这一篇开始，我们正式进入工程开发。

本篇只完成 Agent Watchdog V0.1：真实事件采集。

完成以后，当 Codex 运行命令、修改文件、结束任务时，我们自己写的 Python 程序能够收到相应事件，并把它们保存下来。

本篇要实现的系统

Codex

执行命令、修改代码

官方 Hooks

在操作前后触发事件

我们自己写的 Python 事件采集器

提取事件类型、工具名称、时间

events.jsonl

保存监控数据，供后续分析

## 一、为什么先做事件采集？

你可能想直接上 AI，让 ModernBERT 判断 Codex 有没有卡住。

但有一个问题：如果没有真实的执行记录，AI 就不知道该分析什么。

例如 Codex 执行：

```
读取 auth.py
修改 validate_token()
运行 pytest
再次修改 auth.py
重新运行 pytest
```

我们需要先得到这些事件，才能在下一阶段分析它们是否代表真正的进展。

Codex 官方的 Hooks 就是为这种扩展场景设计的。它支持 `PreToolUse`、`PostToolUse`、`Stop` 等事件，并能在发生事件时调用我们自己编写的脚本。

[image](https://www.google.com/s2/favicons?domain=https://developers.openai.com\&sz=32)

ChatGPT Learn



官方文档：Codex Hooks

我们暂时不采用读取 Codex 内部 SQLite 数据库的方案，因为内部数据库格式可能随版本变化。先走官方扩展接口。

## 二、准备项目目录

你当前的项目目录是：

```
D:\program\agent_watchdog
```

我们继续复用，不重新安装 Conda，也不重新下载 StepWise。

打开 Anaconda Prompt：

```
conda activate torch_env
cd /d D:\program\agent_watchdog\watchdog
```

接下来我们需要建立两个文件：

```
agent_watchdog/
│
├── StepWise/                # 已下载的论文仓库
│
└── watchdog/
    ├── test_stuck.py       # 你已经跑通
    ├── hook_logger.py      # 本篇新建
    ├── hook_runner.cmd     # 本篇新建
    └── logs/
        └── events.jsonl    # 自动生成
```

先执行：

```
mkdir logs
```

然后查询当前 Conda 环境的 Python 路径：

```
where python
```

记住第一条路径，例如：

```
D:\00software\65.Anaconda\envs\torch_env\python.exe
```

这只是示例，你要使用自己电脑的真实路径。

为什么要完整路径？ 因为 Codex 启动的 Hook 不一定继承你在 Anaconda Prompt 中激活的环境。使用绝对路径，可以保证它调用的是正确的 Python。

## 三、编写第一个真正属于我们的模块

创建文件：

```
notepad hook_logger.py
```

粘贴以下代码：

```
import sysimport jsonfrom pathlib import Pathfrom datetime import datetime# 事件数据保存在脚本旁边BASE_DIR = Path(__file__).resolve().parentLOG_FILE = BASE_DIR / "logs" / "events.jsonl"def main():    # Codex 通过标准输入发送一个 JSON 对象    raw = sys.stdin.buffer.read()    event = json.loads(raw.decode("utf-8-sig"))    if not isinstance(event, dict):        return    tool_input = event.get("tool_input")    if not isinstance(tool_input, dict):        tool_input = {}    # V0.1 只保存事件元数据，不保存命令参数、    # 用户消息、工具输出或可能包含密钥的正文。    record = {        "time": datetime.now().astimezone().isoformat(),        "event": event.get("hook_event_name", "UNKNOWN"),        "session_id": event.get("session_id"),        "turn_id": event.get("turn_id"),        "tool": event.get("tool_name"),        "tool_use_id": event.get("tool_use_id"),        "input_keys": list(tool_input.keys()),        "has_response": "tool_response" in event    }
```

保存文件。

### 理解这段代码

最重要的是这一行：

```
raw = sys.stdin.buffer.read()
```

Codex 运行 Hook 时会把事件 JSON 发送给脚本的标准输入 `stdin`。我们的程序接收它，然后提取需要的信息。官方文档明确描述了这种输入方式。

[image](https://www.google.com/s2/favicons?domain=https://developers.openai.com\&sz=32)

ChatGPT Learn



接下来：

```
f.write(json.dumps(record, ensure_ascii=False) + "\n")
```

把每条事件写成独立的一行。

这就是 JSONL 格式。

例如：

```
{"event":"PreToolUse","tool":"Bash","session_id":"demo"}
{"event":"PostToolUse","tool":"Bash","session_id":"demo"}
{"event":"Stop","tool":null,"session_id":"demo"}
```

为什么不用普通 JSON 数组？

因为以后每发生一条事件，我们可以直接在文件末尾追加，不用重新读取或改写整个文件。

现在先使用 JSONL；等项目需要统计、筛选、多会话查询时，再考虑 SQLite。

## 四、创建 Windows 启动脚本

我们需要一个 `.cmd` 文件，让 Codex 正确启动刚才的 Python 程序。

在同一目录执行：

```
notepad hook_runner.cmd
```

填写：

```
@echo off
"你的Python完整路径" "D:\program\agent_watchdog\watchdog\hook_logger.py"
```

例如，如果 `where python` 显示的是：

```
D:\00software\65.Anaconda\envs\torch_env\python.exe
```

那么写成：

```
@echo off
"D:\00software\65.Anaconda\envs\torch_env\python.exe" "D:\program\agent_watchdog\watchdog\hook_logger.py"
```

注意：这里必须替换成你电脑真实的 Python 路径。

保存文件。

## 五、先不连接 Codex，测试我们自己的程序

这是开发中非常重要的习惯。

先验证模块本身，再排查集成。

仍然在 `watchdog` 目录下，执行：

```
echo {"hook_event_name":"PostToolUse","tool_name":"Bash","session_id":"demo-001"} | hook_runner.cmd
```

然后：

```
type logs\events.jsonl
```

如果成功，你会看到一条类似：

```
{
  "time": "2026-10-08T...",
  "event": "PostToolUse",
  "session_id": "demo-001",
  "turn_id": null,
  "tool": "Bash",
  "tool_use_id": null,
  "input_keys": [],
  "has_response": false
}
```

实际保存时，它会占用一行，而不是多行格式。

本地测试通过的标志

`logs\events.jsonl` 被创建，并且能看到 `PostToolUse` 和 `demo-001`。

这时我们已经完成了自己的第一个功能模块：事件接收与持久化。

## 六、把程序接入 Codex

现在开始真正集成。

为了不影响你正在做的研究项目，我们先创建一个单独的测试仓库。

在 Anaconda Prompt 执行：

```
cd /d D:\program\agent_watchdog
mkdir hook_demo
cd hook_demo
git init
mkdir .codex
```

这个目录是专门用于验证的，不要直接在研究项目上安装尚未测试的 Hook。

然后创建：

```
notepad .codex\hooks.json
```

粘贴以下内容：

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

保存。

这里有三个事件：

| 事件            | 什么时候触发         |
| ------------- | -------------- |
| `PreToolUse`  | 工具执行之前         |
| `PostToolUse` | 工具执行之后         |
| `Stop`        | 当前 Agent 回合结束时 |

这里的 `Stop` 不代表整个工程项目已经完成，只表示当前回合结束。

配置方式、事件名称和 Windows 命令 Hook 格式来自官方文档。

[image](https://www.google.com/s2/favicons?domain=https://developers.openai.com\&sz=32)

ChatGPT Learn



### 为什么只安装到测试仓库？

Codex 会读取项目 `.codex/hooks.json` 或用户级 `~/.codex/hooks.json`。项目配置只在相应项目被信任时加载。

[image](https://www.google.com/s2/favicons?domain=https://developers.openai.com\&sz=32)

ChatGPT Learn



我们现在选择前者，防止影响所有 Codex 会话。

## 七、真正运行一次 Codex

在测试目录中，执行：

```
codex
```

进入 Codex 后，先输入：

```
/hooks
```

检查刚才配置的三个 Hook 是否被加载。

当前 Codex 对非托管命令 Hook 需要单独审核和信任；如果出现待信任提示，检查命令确实指向我们自己的 `hook_runner.cmd` 后，再按照界面操作。不要使用跳过信任审查的参数。

[image](https://www.google.com/s2/favicons?domain=https://developers.openai.com\&sz=32)

ChatGPT Learn



随后给 Codex 一个很简单的测试任务：

在当前目录创建 `hello_watchdog.txt`，内容为 `Hello Watchdog`。然后通过终端读取它，确认内容正确。不要访问或修改其他目录。

&#x20;复制测试任务

如果 Hooks 正常，你的程序就应该收到事件。

例如：

```
PreToolUse   apply_patch
PostToolUse  apply_patch
PreToolUse   Bash
PostToolUse  Bash
Stop
```

实际数量与工具名称以 Codex 真实执行情况为准。某些工具路径可能不触发这些 Hook，因此不能把它当成完整无遗漏的执行审计。

[image](https://www.google.com/s2/favicons?domain=https://developers.openai.com\&sz=32)

ChatGPT Learn



## 八、查看我们采集到的真实数据

打开第二个终端窗口。

进入：

```
cd /d D:\program\agent_watchdog\watchdog
```

执行：

```
type logs\events.jsonl
```

现在文件中应该出现真实的 Codex 事件，而不只是先前的 `demo-001`。

你可以检查 `session_id` 是否已出现真正的会话 ID。

还可以使用 PowerShell 实时查看新增的日志：

```
Get-Content "D:\program\agent_watchdog\watchdog\logs\events.jsonl" -Tail 10 -Wait
```

这里的 `-Wait` 会持续等待新内容追加。

以后 Codex 再调用受支持的工具，你就能看到新增事件。

这已经是我们自己的一个最小可用监控程序了。

## 九、如果没有收到事件，怎么排查？

| 现象               | 排查方法                               |
| ---------------- | ---------------------------------- |
| 找不到 `codex` 命令   | 确认 Codex CLI 已安装并在 PATH 中          |
| `/hooks` 看不到配置   | 检查是否从 `hook_demo` 项目启动，JSON 格式是否有效 |
| Hook 显示需要信任      | 在 `/hooks` 审核并信任本地脚本               |
| 配置已加载但没有日志       | 检查 `hook_runner.cmd` 中 Python 路径   |
| 只有 `Stop`，没有工具事件 | 检查 Codex 是否真的使用了本地受支持的工具           |
| 执行卡顿或报 Hook 错误   | 检查采集程序能否快速退出，必要时先移除测试配置            |

如果需要取消本次试验，只需在 `hook_demo` 里删除 `.codex\hooks.json`，并重新启动对应会话；不要去改全局 Codex 配置。

## 十、我们现在离真正的 Agent Watchdog 还有多远？

完成本篇后，工程进度会是：

Agent Watchdog 开发进度

1/8

运行 StepWise 官方检测模型

接收和保存 Codex 执行事件

实时展示 Codex 正在执行的操作

读取 Git 与测试结果

建立任务目标与验收条件

检测目标偏离和无效循环

建立独立验收系统

完成实时监督界面

这里可以手动记录学习进度，不会自动检查电脑上的安装状态。

请注意：本篇只完成事件采集，还没有实现任务是否成功、是否偏离目标的判断，也没有接入 StepWise。我们先把基础数据链打通。

## 十一、下一篇会做什么？

下一篇暂定：

《从零开发 Agent Watchdog（02）：实时显示 Codex 在做什么》

我们会把当前的 JSONL 事件记录进一步变成统一事件模型和终端监控器。

那时终端可以展示：

```
AGENT WATCHDOG v0.2

Agent      : Codex
Session    : 8f21...
Status     : RUNNING

Last event : PostToolUse
Tool       : Bash

Events     : 37
Tool calls : 14

Monitoring : ACTIVE
```

再往后才加入 Git 分析、真实测试结果、任务进度判断，以及 IronLaw 和 StepWise 的可复用模块。

## 参考资料

- Codex Hooks 官方文档 —— 本篇最重要的参考，包括事件与配置格式。
- Codex 基础配置 —— 用户级与项目级配置的区别。
- IronLaw GitHub —— 后续任务约束与独立验收的架构参考。
- StepWise GitHub —— 后续智能卡住检测模型。

本篇最终验收标准只有一个：你在 Codex 里执行一次真实工具操作，`events.jsonl` 就能记录到对应的 `PreToolUse` / `PostToolUse` 事件。

先做到这里。这样我们的下一步才不是继续讨论概念，而是在已经能运行的代码上逐步增加功能。
