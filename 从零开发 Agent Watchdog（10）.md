# 从零开发 Agent Watchdog（10）：Hook 之外的 Codex 执行轨迹——我们究竟观察到了什么？

> **系列教程 · 第 10 篇** · Codex CLI · JSONL · 事件适配器 · 隐私分级  
> 本篇处理事件覆盖面与来源问题，不修改 Codex 的会话数据库，也不试图接管它的进程。

到现在你可能已经注意到一个麻烦：Hook 事件可以告诉我们某些工具调用前后发生了什么，却不能保证看到所有 Agent 行为。比如一些托管工具或特殊路径可能不经过相同 Hook。于是我们自然会想到：能不能把 Codex 更丰富的结构化事件接进自己的 Watchdog？

可以，但首先必须回答：**哪个数据源是官方支持的？信息里包含什么？我们打算保留什么？**

## 一、三种接入路线，先不混在一起

| 路线 | 主要用途 | 此时采用情况 |
|---|---|---|
| 项目级 Hooks | 在本地支持的生命周期事件发生时通知脚本 | 第 01–04 篇的主要入口 |
| `codex exec --json` | 执行非交互任务时输出结构化 JSONL 事件 | 本篇支持**用户显式导出的文件** |
| Codex App Server | 持续接收更丰富的线程、回合、项目操作协议 | 作为后续完整适配路线，目前不实现其生命周期客户端 |

我们不直接读取、编辑 Codex 内部数据库来模拟 App Server。这样做可能受内部 Schema 变化影响，还会模糊控制权限。

官方入口文档：[Codex Hooks](https://developers.openai.com/codex/hooks) · [Codex App Server](https://developers.openai.com/codex/app-server)。

## 二、先给所有事件加“来源标签”

两个形状相似的 JSON 不一定有相同的可信度。

手工输入：

```powershell
'{"hook_event_name":"PostToolUse","tool_name":"Bash"}' | & .\hook_runner_v04.cmd
```

与真实 Codex 经过受信任项目 Hook 调用的事件，在我们的 Logger 中可能具有相同的内容。如果仅因为日志里写着 `source=codex_hook` 就认为它一定来自 Codex，那是犯了“**拿消息自述当身份认证**”的错误。

因此第 04 篇已将来源标记为 `hook_input_unverified`。本篇从用户明确提供的 `codex exec --json` 导出文件提取元数据，记录来源为 `codex_exec_export`。即使如此，这也只是**导入通道声明**，不是一份经过数字签名验证的真实性证明。

## 三、事件数据为什么不能直接全部保存？

一个执行 Agent 的原始轨迹里很可能含有：用户提示词、目录路径、代码片段、终端环境、报错输出、HTTP 请求，甚至偶尔出现的密钥。

你最初就强调过，希望 Watchdog 默认本地、少收集。为了实现这个目标，我们只提取白名单字段：

```python
{
    "source": "codex_exec_export",
    "received_at": "...",
    "event": "item.completed",
    "session_id": "...",
    "turn_id": None,
    "tool": "command_execution",
    "cwd": None,
    "tool_use_id": "...",
}
```

原始 `command`、`output`、用户消息正文都不保存。我们也没有把导出文件本身提交 GitHub。

代码在 [`agent_adapter.py`](examples/v04/watchdog/agent_adapter.py)，其中 `project()` 函数只处理一小部分已经明确列入 `KINDS` 的事件类型；未知事件直接跳过。

## 四、一次可以复现的最小实验

在你自己信任的测试项目中，如果本机 Codex CLI 支持 `exec --json`，可以按其当前帮助文档执行非交互任务，并将 JSONL 输出重定向到位于工作仓库之外的文件。

```bat
codex exec --help
```

请先核对 CLI 版本与 JSON 输出选项；不要照搬任何会向公网发送用户源码的命令。本篇仅说明本地已获得 JSONL 文件后的导入方法，不以教程代替真实运行许可。

假设测试文件保存在：

```text
D:\program\agent_watchdog\exports\codex_exec_test.jsonl
```

执行：

```bat
cd /d D:\program\agent_watchdog\watchdog
python agent_adapter.py "D:\program\agent_watchdog\exports\codex_exec_test.jsonl" --out "D:\program\agent_watchdog\exports\redacted_events.jsonl"
```

然后用记事本打开 `redacted_events.jsonl`。对照原导出文件，确认 `item.command`、工具输出和用户文字没有被复制进去。任何 `event` 只代表投影后的元数据，不保证整个任务的全部细节。

最后可将脱敏结果单独送入第 09 篇 SQLite 导入器：

```bat
python journal.py sync --log "D:\program\agent_watchdog\exports\redacted_events.jsonl"
```

注意：这条路线目前是**手工导入导出的工作流**；没有实现 App Server 的实时订阅和 thread/resume。

## 五、如何正确处理两个数据源？

你可能同时拥有 Hook 和 exec JSONL。千万不要简单把所有事件相加就说“Agent 实际调用了 30 次工具”。两个通道可能观察到同一个动作。如果没有可靠的统一 `tool_use_id` 或映射规则，就不能证明它们不是重复观察。

较稳妥的做法是：每条事件保留来源；展示时按来源计数；需要统一统计时做关联评估。我们目前**没有实现跨来源的可信去重**，所以不对两个来源给出未经验证的总数。

同样，如果 `cwd` 为空，我们也不能凭文件名猜这条事件属于哪个仓库。它可以进入通用历史库，但不能直接驱动某个 Git 仓库的受保护文件验收。

## 六、为什么这一步仍然不能检测语义偏离？

即使我们能看到所有工具名称与事件时间，也不知道它们是否符合“仅修复登录，不要重构整个系统”这一原始目标。要做到那一点，需要：

- 原始用户指令与批准的任务合同；
- 允许修改范围与相关文件上下文；
- Agent 每一步行动与某个验收项的可解释关联；
- 关键文件 diff、测试结果和其他独立执行证据。

而我们为了隐私暂时没有收集完整命令参数。这意味着 Watchdog 能做的仍以**确定性证据**为主。不要把缺失数据用模型想象补齐。

## 七、学习检查与下一篇

本篇验收：能够从显式提供的 JSONL 导出文件产生脱敏记录；原始敏感文字未被复制；未知类型被跳过；不同来源不会自动合并成“完整真实轨迹”；本篇不读取或修改 Codex 内部数据库。

思考题：如果同一命令经两个通道都被观察到，你凭什么判断它们是同一件事？如果某条事件没有 `cwd`，你有资格说它修改了哪个仓库吗？

下一篇：在已有事实与风险信号之上，建立一个更加解释性的监督报告。不是让它“更会猜”，而是让它“更能说明自己不知道什么”。
