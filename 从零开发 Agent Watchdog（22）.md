# 从零开发 Agent Watchdog（22）：工具结束不等于成功——给每个 Codex 操作建立可追溯的结果状态

> 系列教程 · 第 22 篇｜事件规范化 · Codex Hooks · JSONL · App Server · Python  
> 本篇验证的是结构化状态适配与数据最小化。**离线导出和模拟输入不等于实时 Codex 身份认证。**

## 一、从一个容易把人骗过去的“成功日志”说起

假设 Codex 连续执行三个操作：

```text
工具 A 开始
工具 A 产生输出：AssertionError
工具 B 开始
工具 B 产生输出：OK
Codex Stop
```

第 01–04 篇的日志采集器只会记住两个 `PostToolUse`。粗糙的监控器往往统计“调用 2 次、完成 2 次”，于是给用户画出两个绿色的对勾。但你已经能看出至少三个问题：

第一，工具“产生输出”不代表成功，报错也可能作为正常的工具响应送回来。第二，`Stop` 只代表回合结束，不是任务验收通过。第三，即使知道某个脚本退出码为 0，测试代码本身仍可能完全没有覆盖用户要求。

这篇要把问题收窄到一件可实现的事情：**只在来源实际提供明确可解释的结果字段时判成功/失败，否则承认 UNKNOWN。**

## 二、我们怎样给各种来源设计共同语言？

真实项目会遇到三条线。Hook 有 `PreToolUse`、`PostToolUse`；`codex exec --json` 使用 `item.started`、`item.completed`；App Server 的结构化通知使用 `item/started`、`item/completed`。它们的名称不同、字段也不同，不能简单地把所有“完成”事件归一为 `SUCCEEDED`。

我们在 [execution_v2.py](examples/v04/watchdog/execution_v2.py) 中统一成：

```json
{
  "source": "hook_input_unverified",
  "received_at": "2026-10-08T12:00:00+00:00",
  "event": "PostToolUse",
  "session_id": "example-session",
  "turn_id": "example-turn",
  "tool": "Bash",
  "cwd": "D:\\example",
  "tool_use_id": "example-call",
  "phase": "FINISHED",
  "outcome": "UNKNOWN",
  "exit_code": null,
  "result_basis": "not_observed",
  "linkable": true,
  "event_id": "示意：真实值由程序生成"
}
```

**这是格式示意，不是当前用户的真实事件。** `source` 明确是“收到了一份自称 Hook 的 JSON”，不是谁签发的凭证。`received_at` 是我们的接受时间，不是操作真正开始的高精度时间戳。`cwd` 可以帮助把事件路由到一个仓库，但单凭它不能做文件作者归因。

值得注意的是字段的细分：

| 字段 | 回答的问题 | 不应该回答的问题 |
|---|---|---|
| `phase` | 这个来源报告了启动、更新、结束还是回合结束？ | 执行是否成功？ |
| `outcome` | 是否有足够直接证据判断进程成功/失败/取消？ | 用户整个任务是否完成？ |
| `exit_code` | 是否明确报告了整数退出码？ | 失败原因、测试覆盖度 |
| `result_basis` | 是哪个规则允许作此判断？ | 来源真实性 |
| `tool_use_id` | 哪次操作的 ID？ | ID 缺失时靠时间猜的一对 |
| `event_id` | 本地引用这一条脱敏记录的标识 | 外部签名或不可伪造性 |

## 三、为什么我们宁可保留 UNKNOWN？

想象修复脚本输出了：

```text
FAILED: 2 tests
```

文本确实像测试失败。但是不同工具的输出格式不一致；含有“failed”的日志也可能出现在已通过的负例测试、测试计划说明或错误重试的历史输出中。为了这个词而保存整段 stdout，还可能把用户代码、密钥和私人路径写入公共样例仓库。

所以我们的策略非常严格：

```python
def number_code(value):
    return value if type(value) is int and -999999 <= value <= 999999 else None
```

注意不是 `int(value)`！Python 中 `bool` 属于 `int` 的子类，`True` 隐式转换会变为 1，字符串 `"0"` 也能转成数字。这样的方便转换会让数据语义变形。

真正的结果判定是：

```python
outcome = (
    "SUCCEEDED" if code == 0 else
    "FAILED" if code is not None else
    "CANCELLED" if status in ("declined", "interrupted", "cancelled") else
    "FAILED" if status == "failed" else
    "UNKNOWN"
)
```

这里的成功严格是**该工具进程退出码为 0**。如果 `PostToolUse` 只带着没有结构化退出码的 `tool_response`，即使 JSON 中有一百行看起来像成功的信息，`outcome` 仍然为 `UNKNOWN`。这就是我们有意选择的保守性。

在 App Server 中，`status=failed/declined` 可用于明确标记终态；但一个普通的 `completed` 只表示这条 item 已到终态，不足以证明业务成功。官方文档展示了命令的 `exitCode` 和一些明确终态，具体字段需由你安装的客户端版本现场核实。

## 四、事件并不是一排孤立的行：如何配对开始与结束？

第 21 篇的原始日志大致这样：

```text
12:00:00  PreToolUse   session=S  call=A  Bash
12:00:01  PreToolUse   session=S  call=B  Bash
12:00:03  PostToolUse  session=S  call=B  Bash
12:00:05  PostToolUse  session=S  call=A  Bash
```

如果按先入先出配对，第一个结束会错误地配给 A。现实中 Codex 可以并行调用工具；MCP 或异步命令的回执还可能交错。

因此配对键至少包含：

```python
key = (source, session_id, turn_id, tool_use_id)
```

缺 `tool_use_id` 就不配，`linkable=false`。同一键的完成记录如果声称两个互相矛盾的终态，会提示 `CONFLICTING_TERMINAL`，而不是挑一个最绿色的。只看见结束而没看到开始，记录 `ORPHAN_TERMINAL`，可能是录制中断、日志滚动或历史导入缺口。

**这也解释了为什么我们不使用“连续六次 Bash = 同一操作的循环”。** Bash 是工具类别，而不是调用身份；六次不同的 Bash 可能是在进行有效的编译、运行和调试。

## 五、把三种输入映射到新 schema，复用旧 JSONL 与 SQLite

我们没有新建一套数据库 schema。旧 `journal.py` 已经做了流式导入、按文件位置去重及 SQLite 持久化。这一轮只扩大 `FIELDS` 白名单，使 `phase`、`outcome`、`exit_code`、`result_basis`、`event_id`、`linkable` 能保留下来；以前八个字段照样兼容。旧记录的新增字段为空，不能反推历史结果。

三个适配入口：

- `from_hook()`：处理信任后 Codex 调用 Runner 的 stdin；没有从 `tool_input` 记录命令。
- `from_exec()`：仅处理用户明确提供的 `codex exec --json` 文件。它不是从 Desktop 悄悄抓的实时事件。
- `from_appserver()`：仅处理用户明确提供的 App Server 导出流；不启动服务器，不回应审批。

完整代码与实际支持的事件清单见 [execution_v2.py](examples/v04/watchdog/execution_v2.py) 和 [来源覆盖矩阵](docs/EVENT_SOURCE_MATRIX.md)。

## 六、先在隔离目录里验证代码，再考虑真实接入

在 Anaconda Prompt 的**新克隆项目根目录**运行：

```bat
python -m unittest discover -s examples\v04\tests -p test_round1.py -v
```

测试应涵盖：只有 `PostToolUse` 没有退出码；`exit_code=0`；`exit_code=1`；`exit_code="0"`；`True`；包含秘密命令与秘密输出的嵌套对象；App Server 显式 `declined`；离线 JSONL 半写完一行；同一调用重复导入。这些都是真正执行的 Python 逻辑测试，fixture 来源仍然是**人为构造**。

如果你已有**明确授权的、本机导出的** `codex exec --json` 文件，允许离线试验：

```bat
cd /d D:\program\agent_watchdog\Agent-Watchdog-v2-eval\examples\v04\watchdog
python execution_v2.py import --format exec --input "D:\private\codex_exec.jsonl" --out "logs\exec_safe.jsonl"
python journal.py sync --log "logs\exec_safe.jsonl"
python journal.py summary
```

这段命令不运行 `codex exec`、不消耗模型调用费用，只读取你自己指定的文件。**原导出文件可能含提示词和完整命令，请保存在私有路径；`logs\exec_safe.jsonl` 也属于个人日志，不提交 GitHub。**

若有 App Server 的已授权导出，`--format appserver` 才对应那条适配路径。不要为了做一个示例去私自抓取 Codex 的内部 SQLite。

## 七、做三次反例实验

**反例 1：把工具结束当成功。** 准备一条 `PostToolUse` 但不加数值退出码，断言 `UNKNOWN`。如果输出 `SUCCEEDED`，说明投影器偷偷进行了乐观推断，本章失败。

**反例 2：字符串“0”当退出码。** 准备 `{"exit_code":"0"}`，必须仍是 `UNKNOWN`；只有明确的 JSON 数字 0 可以触发对应判断。

**反例 3：两个会话都叫 Bash。** 让 A、B 会话各有三次调用，`runtime_v2.py` 的分组结果不能把它们合并成一个失败序列，也不能通过顺序臆测同一 `tool_use_id`。

再加一个安全反例：给输入 `tool_input.command`、`tool_response.stdout` 放两个特征字符串。在本机输出的**脱敏记录**中搜索，必须找不到；不能为了日志“更详细”就重新打开原文持久化。

## 八、Windows 上的常见坑

`Get-Content` 是 PowerShell 命令，不是 CMD；`python -m unittest` 与 `git` 两者都可在 Conda Prompt 执行。Windows 本地时间与 UTC 可以同时存在，程序内部使用时区感知的 `received_at`，别把两个不同时区显示的小时数字直接相减。某些工具完成但缺少 ID，程序拒绝关联是预期现象，不应为了“覆盖率”制造随机 ID 再冒充稳定调用身份。

**本章验收标准**：结构化成功/失败/取消/未知均有对照测试；不能把命令正文保存到持久日志；稳定 ID 才能配对；重复、半行、丢字段、跨会话不乐观修复；托管 CI 与本机真实事件保留两套状态。

现在我们终于能回答“哪些操作有明确失败证据”。下一篇继续问：**有一个工具很久不返回，或者突然再也没有任何 Hook，我们应不应该喊‘卡死了’？** 答案不能只靠一个计时器。

延伸：[Codex Hooks](https://developers.openai.com/codex/hooks) · [Codex App Server](https://developers.openai.com/codex/app-server) · [事件矩阵](docs/EVENT_SOURCE_MATRIX.md)。

