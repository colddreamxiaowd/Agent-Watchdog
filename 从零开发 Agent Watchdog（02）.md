# 从零开发 Agent Watchdog（02）：用 Python 实时监控 Codex 的执行状态

系列教程 · 第 2 篇

Windows 11 / Python / Rich / Codex Hooks

上一节，我们编写了 `hook_logger.py`，尝试让 Codex 的执行事件进入自己的日志文件。

这一节，我们要完成一个更直观的功能：

打开一个独立终端，就能看到 Codex 最近执行了哪些工具操作、目前处于哪个阶段，以及是否有新的事件发生。

Agent Watchdog v0.2 — 预期界面

设计预览

AGENT WATCHDOG

MONITORING

Agent

Codex

Last event

PostToolUse

Latest tool

Bash

Observed events

24

RECENT EVENTS

12:31:02   PreToolUse    Bash 12:31:04   PostToolUse   Bash 12:31:10   PreToolUse    apply_patch 12:31:11   PostToolUse   apply_patch 12:31:25   Stop          —

示意数据，不是你的真实 Codex 会话。

## 一、先理解我们要实现的原理

上篇的系统负责写入：

```
Codex → Hook → events.jsonl
```

这次新增一个读取器：

```
                    Codex
                      │
                      ▼
                  Hook 事件
                      │
                      ▼
                 events.jsonl
                      │
                      ▼
                 monitor.py
                      │
                      ▼
               实时终端监控面板
```

这里有一个非常重要的工程设计：监控面板与 Codex 分开运行。

即使你关闭监控面板，也不会要求 Codex 停止工作；重新打开面板，仍能读取此前保存的事件。

我们暂时不接入数据库，也不调用大模型。

原因很简单：先确保真实监控数据可靠，再增加智能分析。

官方 Codex Hooks 已支持 `PreToolUse`、`PostToolUse` 等事件，但它不覆盖所有可能的内部行为，因此我们的系统必须明确区分“最近收到的事件”和“Agent 的完整状态”。

[image](https://www.google.com/s2/favicons?domain=https://developers.openai.com\&sz=32)

ChatGPT Learn



## 二、这一节的开发环境

沿用你已建立的项目：

```
D:\program\agent_watchdog\
│
├── StepWise\
├── hook_demo\
└── watchdog\
    ├── test_stuck.py
    ├── hook_logger.py
    ├── hook_runner.cmd
    └── logs\
        └── events.jsonl
```

我们今天只添加：

```
watchdog\
    └── monitor.py
```

使用的工具：

- Python：处理日志、统计事件。
- Rich：绘制终端表格和动态面板。
- JSONL：上一节已经建立的事件存储格式。

本篇无需重新安装 PyTorch，也无需运行 ModernBERT。

## 三、安装终端界面库 Rich

我们不需要自己编写终端表格刷新、颜色和布局逻辑，因为 Python 已经有一个成熟的开源库：Rich。

打开 Anaconda Prompt：

```
conda activate torch_env
cd /d D:\program\agent_watchdog\watchdog
```

安装：

```
python -m pip install rich
```

测试安装：

```
python -c "from rich.console import Console; Console().print('[green]Rich OK[/green]')"
```

如果出现绿色的 `Rich OK`，就可以继续。

## 四、编写监控程序 monitor.py

这次我已经为你准备了一份完整 Python 文件，不需要手动复制一百多行代码。

monitor.py

Agent Watchdog v0.2 · Python 源文件

&#x20;下载完整 monitor.py

这份代码已经通过本地的空日志、未写完 JSON 行、事件统计以及 Rich 界面渲染测试。



下载后放到：

```
D:\program\agent_watchdog\watchdog\monitor.py
```

注意不要误放进 `StepWise` 文件夹。

### 认识程序的三个核心部分

第一部分：读取事件日志。

```
LOG_FILE = (    Path(__file__).resolve().parent    / "logs"    / "events.jsonl")
```

它自动定位与 `monitor.py` 同目录下的 `logs\events.jsonl`。

其中 `Path(__file__).resolve().parent` 是 Python 获取当前脚本所在文件夹的一种写法。

第二部分：统计事件。

```
counts = Counter(    str(item.get("event") or "UNKNOWN")    for item in selected)
```

假设记录是：

```
PreToolUse
PostToolUse
PreToolUse
PostToolUse
Stop
```

统计结果就相当于：

```
工具开始：2
工具完成：2
Stop：1
```

这不是任务成功率，只是我们观察到的事件数量。

第三部分：自动刷新终端。

```
with Live(    build_screen(),    console=console,    refresh_per_second=2) as live:    while True:        time.sleep(1)        live.update(build_screen())
```

这里的 `Live` 是 Rich 提供的动态界面功能。

程序每秒重新读取日志并更新面板，不需要你反复运行命令。

为了避免日志越积越大导致每次刷新都很慢，当前代码只读取日志文件末尾最多 512 KiB 的内容，展示最近一个会话的部分记录。因此屏幕上的计数是最近读取窗口内的计数，不是会话的完整历史总数。

## 五、正式启动 Agent Watchdog

确保文件已经放好，然后运行：

```
cd /d D:\program\agent_watchdog\watchdog
python monitor.py
```

如果之前还没有收到任何事件，可能看到：

```
╭──────────── Agent Watchdog v0.2 ────────────╮
│                                            │
│ 正在等待 Hook 事件……                       │
│                                            │
│ 日志位置：                                 │
│ D:\program\agent_watchdog\watchdog\        │
│ logs\events.jsonl                          │
│                                            │
╰────────────────────────────────────────────╯
```

这表示监控程序已启动，不代表 Codex 已经连接成功。

先保持这个终端窗口打开。

## 六、测试监控面板能否实时刷新

先不启动 Codex。我们先模拟几条 Hook 事件，验证整个链路。

打开第二个 Anaconda Prompt：

```
conda activate torch_env
cd /d D:\program\agent_watchdog\watchdog
```

执行第一条模拟事件：

```
echo {"hook_event_name":"PreToolUse","tool_name":"Bash","session_id":"demo-v02"} | hook_runner.cmd
```

回到第一个监控窗口。

应该出现：

```
会话 ID      demo-v02
最新事件     PreToolUse
最近工具     Bash
工具开始     1
工具完成     0
```

接着在第二个终端执行：

```
echo {"hook_event_name":"PostToolUse","tool_name":"Bash","session_id":"demo-v02"} | hook_runner.cmd
```

监控面板应该更新为：

```
最新事件     PostToolUse
最近工具     Bash
工具开始     1
工具完成     1
```

这两条命令只是测试我们自己的采集器，没有真的运行 Codex 工具。

如果界面能变化，就说明以下链路已经可用：

模拟事件

hook_logger.py

monitor.py

## 七、修正上一课 Hook 脚本的一个细节

这里有一个值得修正的地方。

我重新核对了官方文档：`Stop` Hook 正常退出时应该向标准输出返回合法的 JSON；仅保持沉默并不是我们应该依赖的输出契约。普通 Hook 返回空 JSON 对象 `{}`，不会主动要求阻止或改变 Codex 的操作。

[image](https://www.google.com/s2/favicons?domain=https://developers.openai.com\&sz=32)

ChatGPT Learn



打开原来的脚本：

```
notepad hook_logger.py
```

找到最底部：

```
if __name__ == "__main__":    try:        main()    except Exception:        pass
```

替换为：

```
if __name__ == "__main__":    try:        main()    except Exception as exc:        print(            f"Watchdog logger error: {type(exc).__name__}",            file=sys.stderr        )    print("{}")
```

保存即可。

这个修改有两个作用：即使采集器异常，也尽量不阻碍 Codex 正常运行；同时提供合法的 Hook JSON 输出。

## 八、接入真实 Codex

现在我们进行真正的端到端测试。

按照上一篇的操作，我们已经为测试仓库准备了：

```
D:\program\agent_watchdog\hook_demo\
    └── .codex\
        └── hooks.json
```

Codex 支持从受信任项目的 `.codex/hooks.json` 加载 Hook，但本地 Hook 仍需要经过信任审核；可以通过 CLI 的 `/hooks` 查看加载状态。

[image](https://www.google.com/s2/favicons?domain=https://developers.openai.com\&sz=32)

ChatGPT Learn



打开第三个终端：

```
cd /d D:\program\agent_watchdog\hook_demo
codex
```

先输入：

```
/hooks
```

确保事件采集 Hook 已经启用并获得信任。

然后让 Codex 执行这个简单任务：

Codex 测试任务

在当前测试仓库内创建一个 `hello.py`，使它能够打印 `Hello Agent Watchdog`。然后使用 Python 运行这个文件，验证输出。不要修改当前仓库以外的任何文件。

&#x20;复制任务

现在观察第一个终端中的 Agent Watchdog。

如果一切正常，你会看到来自真实会话的工具调用事件，例如：

```
PreToolUse     apply_patch
PostToolUse    apply_patch
PreToolUse     Bash
PostToolUse    Bash
Stop           —
```

这些事件名称和工具覆盖范围由 Codex 官方 Hooks 定义。部分专用或托管工具不会通过这条 Hook 路径，因此不能假设日志捕获了每一次操作。

[image](https://www.google.com/s2/favicons?domain=https://developers.openai.com\&sz=32)

ChatGPT Learn



这一节真正通过验收的条件是：

启动 `monitor.py` 后，出现正常监控界面。

模拟 `PreToolUse` 和 `PostToolUse` 时，界面自动更新。

Codex 真正使用工具时，界面出现真实会话的事件。

按 `Ctrl+C` 关闭面板，不会因此要求 Codex 停止工作。

## 九、它现在能做什么？还不能做什么？

这一步特别重要，因为我们不应该把一个事件显示器误认为完整的智能监督系统。

| 能力                | V0.2 |
| ----------------- | ---- |
| 读取本地 Hook 日志      |      |
| 动态显示事件            |      |
| 区分工具调用开始、完成       |      |
| 显示最近观察到的会话        |      |
| 显示具体命令和修改文件       | 尚未实现 |
| 可靠判断 Agent 当前是否存活 | 尚未实现 |
| 判断任务实际进度          | 尚未实现 |
| 检测目标偏离            | 尚未实现 |
| 独立核验任务完成          | 尚未实现 |

特别注意：两分钟没有新 Hook 事件，不等于 Agent 已经卡住。

Codex 可能还在推理，也可能在运行无法产生对应 Hook 的操作。我们目前只显示“近期无新事件”，不据此触发异常。

另外，上一课为了安全，`hook_logger.py` 只记录工具名称、时间和部分元数据，不保存命令参数。因此我们当前能够看到 使用了 Bash，但暂时看不到 Bash 具体执行了什么。这是刻意保留的隐私边界。

## 十、下一篇：开始让 Watchdog 理解实际执行情况

下一篇 · Agent Watchdog 03

## 监控 Git、文件变更和测试结果，让 AI 的真实进度有证据

下一阶段会参考 `codex-watchdog` 和 IronLaw 的设计，但优先实现自己的轻量适配层。

例如，Codex 声称修好了 Bug，我们的监督系统可以显示：

```
TASK: 修复登录 Bug

Agent 声称：已完成

独立检查：
├─ 修改文件：auth.py
├─ 测试记录：8 passed / 2 failed
├─ 保护文件：未发现修改
└─ 验收状态：未通过

结论：仍有 2 项测试失败，不能标记完成
```

这个方向才开始真正接近我们最初设想的 AI Agent 智能监督系统。

目前先完成第 2 篇的验证。如果模拟事件能实时刷新，但真实 Codex 事件没有出现，优先检查 `/hooks` 中的配置、信任状态和 CLI 版本，而不是继续安装新的 AI 模型。

本篇参考： Codex 官方 Hooks 文档 · Rich Live 文档 · codex-watchdog 源码
