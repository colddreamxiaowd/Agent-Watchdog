# 从零开发 Agent Watchdog（14）：读懂 Codex 的 Thread、Turn 和 Item——给监督器接入更丰富的执行事件

系列教程 · 第 14 篇 | Codex App Server · JSON-RPC · 结构化事件 · 脱敏适配

在第 13 篇里，我们给真实 Codex 联调设计了完整的证据流程。但即使 Hook 已经连通，面板上可能只有这样的记录：

```text
16:12:01  PostToolUse   Bash
16:12:05  PostToolUse   Bash
16:12:09  Stop          —
```

你很容易追问：“为什么只能看到 Bash？Codex 刚才是在运行测试，还是执行 Git，还是搜索文件？最后为什么停止？”

问题并不在 Rich 面板，而在我们的**观察接口与记录策略**。第 01 篇刻意不保存工具输入和输出，这是一项正确的隐私保护决策；但它也限制了后续能推导的内容。若为了显示更多信息直接把整个 `tool_response` 写进数据库，我们虽然获得了细节，却可能顺手把 Token、源码、个人文件和终端环境变量也长期保存了下来。

本篇讨论的不是“怎么把所有信息偷出来”，而是：**在遵守最小采集原则的前提下，怎样更准确地区分 Codex 的会话、回合和具体工作项？**

## 一、先用一个现实例子区分三层对象

假设你给 Codex 发送：“修改登录逻辑，并运行测试。”随后又补充：“再检查一下异常路径。”

从用户角度看，这是一个持续的聊天会话。Codex App Server 文档把它抽象成多层：

```text
Thread（会话）
└── Turn 1（用户第一轮指令的执行）
    ├── Item A：模型消息
    ├── Item B：命令执行
    ├── Item C：文件改动
    └── Item D：测试执行
└── Turn 2（用户补充要求后的执行）
    ├── Item E：模型消息
    └── Item F：命令执行
```

- `thread` 可以理解为一条持久的交互线索。它不是“某条 Bash”。
- `turn` 是某次输入触发的一轮工作。不要把 `turn/completed` 理解成整个项目全部完成。
- `item` 是回合内的某项工作或输出，例如命令执行、文件修改、消息等。

这么区分以后，监督器才有机会回答：“哪个回合用了哪些工具？哪一次输出对应哪一个会话？一条失败信号影响的是整项任务还是当前的一次操作？”

不过，**丰富的数据结构并不自动等于可靠语义判断**。`item/completed` 仍然只能说明某项执行单元结束，无法证明登录功能被正确修复。

## 二、为什么选择 App Server，而不是去解析 Codex 的内部数据库？

过去我们已经多次讨论过这个问题：Codex 的内部数据文件可能包含私有实现细节，而且结构可能随更新改变。直接读取或修改它们，会让个人项目在升级时变得脆弱，还容易误碰本不应该公开的数据。

官方 [Codex App Server 文档](https://developers.openai.com/codex/app-server) 描述了应用与 Codex 交互的 JSON-RPC 接口，以及 `thread/start`、`thread/resume`、`turn/start` 等生命周期操作。对于准备制作监控面板、IDE 扩展或自定义客户端的人来说，这是更合适的方向。<details><summary>技术旁注：JSON-RPC 到底是什么？</summary>

你可以把 JSON-RPC 理解成“用 JSON 传输带方法名的消息”。有的消息包含 `id`，意味着发送者希望对方返回一个结果；有的消息只有 `method` 和 `params`，相当于单向通知。Codex 的服务端还可能向客户端发起需要回应的请求，例如审批。不能把每一行 JSON 都当作普通日志，也不能随意吞掉需要处理的请求。

</details>

本篇不直接启动一个会干预 Codex 审批流程的 App Server 客户端。原因是：如果你自己接管了 App Server 会话，就必须正确处理协议初始化、事件接收、审批请求、断线恢复与版本兼容。我们当前的监督器默认只读，不应为了多几个监控字段就变成执行控制器。

所以本篇采用一个**有意分层的方案**：

1. 由你明确导出/提供一份合法来源的 App Server NDJSON 事件流。
2. Watchdog 只读取该文件，不接管 App Server，也不发送审批响应。
3. 将事件投影成少量允许保存的元数据字段。
4. 通过旧版 `journal.py` 入库，让 Rich 或后续监督逻辑使用。

这是可运行的**离线导入器**，而不是已经完成“全自动实时 App Server 接入”。真正的实时连接需要额外的协议客户端及现场验收，不能在教程里偷换概念。

## 三、认识我们这次实际要保留的字段

假设 App Server 发来一条工作项完成通知，里面除了 ID、类型和状态，还包含执行命令、参数和输出。监督器最初真正需要的只有：

| 字段 | 含义 | 处理方式 |
|---|---|---|
| `method` | 发生了什么生命周期事件 | 白名单允许 |
| `params.threadId` | 属于哪个会话 | 截断并保留 |
| `params.turnId` | 属于哪个回合 | 截断并保留 |
| `params.item.id` | 哪个执行单元 | 截断并保留 |
| `params.item.type` | 工作项粗粒度类别 | 仅允许已识别类别 |
| 原始命令、工具输出、用户输入 | 可能包含敏感数据 | 丢弃 |

我们最终存入 JSONL 的一条记录类似：

```json
{
  "source": "app_server_export_unverified",
  "received_at": "2026-10-08T...",
  "event": "item/completed",
  "session_id": "thread-demo",
  "turn_id": "turn-demo",
  "tool": "commandExecution",
  "cwd": null,
  "tool_use_id": "item-1"
}
```

为什么 `cwd` 是 `null`？因为我们不能仅凭“导入文件位于 D 盘某项目下”，就断言这个事件只影响该仓库。如果未来需要把事件精确关联到 Git 仓库，应增加经过核实的来源关系或可信的运行时工作目录，不要用导入命令位置冒充事实。

另外，`source=app_server_export_unverified` 表示**这是你明确提供的导出数据**，并不验证它一定由某个官方进程产生。第 13 篇教会我们的来源边界，在这里仍然适用。

## 四、新模块：appserver_adapter.py

完整源码位于 [`examples/v04/watchdog/appserver_adapter.py`](examples/v04/watchdog/appserver_adapter.py)。我们沿用前面四个基本字段（`source`、`event`、`session_id`、`tool`），保证新事件能进入原来的 SQLite 账本而不需要拆掉旧表。

把流程翻译成伪代码，大致如下：

```text
打开用户明确提供的 NDJSON 文件
  ↓
逐行读取，并限制单行最大字节数
  ↓
JSON 解析成功？不是对象？不是白名单事件？ → 跳过
  ↓
只提取 thread / turn / item 的 ID 与粗类别
  ↓
丢弃命令、输出、提示和其它字段
  ↓
追加到脱敏事件日志
  ↓
报告导入数量与跳过数量（不回显敏感原文）
```

注意这里的“跳过”不等于自动判定输入具有恶意。我们只是在执行最小存储原则，其他事件类型可能是未来真正有价值但当前尚未识别的合法事件。因此应记录**数量与类型边界**，不能记录原始内容来方便以后“再看看”。

你可以先读源码中的 `METHODS`、`CATEGORIES` 与 `project()`：`METHODS` 限定我们能理解的事件，`CATEGORIES` 限定保留的工作项类别，`project()` 才负责把多层嵌套字典转换成统一的扁平事件对象。

### 思考：为什么不用 `row.get("params")["item"]`？

因为输入并不保证存在所有键；`params` 可能为 `null`，`item` 甚至可能是字符串。直接下标访问会让单条异常记录把整个导入过程打断。我们的代码逐层检查数据类型，遇到不合法输入选择跳过，保持导入器本身可预测。

## 五、实验 A：手动制作一份最小事件流

本篇使用 PowerShell 编写实验文件，以避免大量转义。先进入：

```powershell
Set-Location D:\program\agent_watchdog\watchdog
@'
{"method":"thread/started","params":{"thread":{"id":"thread-demo"}}}
{"method":"turn/started","params":{"threadId":"thread-demo","turn":{"id":"turn-1"}}}
{"method":"item/completed","params":{"threadId":"thread-demo","turnId":"turn-1","item":{"id":"item-1","type":"commandExecution","command":"DO_NOT_SAVE_THIS_COMMAND"}}}
{"method":"turn/completed","params":{"threadId":"thread-demo","turn":{"id":"turn-1"}}}
'@ | Set-Content -Encoding utf8 .\appserver_demo.ndjson
```

这段内容是我们人工构造的**结构形状示例**，不是某次真实 Codex 运行的日志。事件结构可能随 Codex 版本有所变化，真实日志要与当时的官方协议进行核对。

然后运行：

```powershell
python appserver_adapter.py .\appserver_demo.ndjson --out .\logs\appserver_safe.jsonl
Get-Content .\logs\appserver_safe.jsonl
```

**目标效果**：输出四条安全记录，包含 `thread/started`、`turn/started`、`item/completed` 和 `turn/completed`。请搜索输出文件中的 `DO_NOT_SAVE_THIS_COMMAND`：应该不存在；如果你看到原始命令出现在输出日志，就意味着脱敏链路不合格，不能上传或继续使用这份日志。

验证方式：

```powershell
Select-String -Path .\logs\appserver_safe.jsonl -Pattern "DO_NOT_SAVE_THIS_COMMAND"
```

没有匹配结果才符合本篇的预期。

## 六、实验 B：把脱敏数据导入现有 SQLite

现在可以复用第 09 篇的 `journal.py`：

```powershell
python journal.py sync --log .\logs\appserver_safe.jsonl --db .\data\appserver_demo.sqlite3
python journal.py summary --db .\data\appserver_demo.sqlite3
```

这里有两个需要理解的细节。

第一，`journal.py` 将导入的每条记录投影到它自己的字段白名单中，因此原本未进入白名单的字段仍然不会被意外保存。第二，`journal.py` 的游标机制只针对它读取过的 JSONL 字节；重复执行 `sync` 不应在文件没有改变时重复插入相同的记录。但**重新运行离线适配器，会再次向输出 JSONL 追加记录**，这是一项需要未来通过源位置去重改善的限制。

所以最简单的教学实验是：每次开始前使用一个新的空输出文件，不要反复把同一输入不断导入同一条输出流，再拿数量推断真实事件次数。

## 七、实验 C：故意喂给它不应该保存的内容

构造一个事件：

```json
{
  "method": "item/completed",
  "params": {
    "threadId": "demo",
    "item": {
      "type": "commandExecution",
      "command": "SECRET_VALUE",
      "output": "PRIVATE_TOKEN"
    }
  }
}
```

经过适配器之后，允许出现 `commandExecution`，不允许出现 `SECRET_VALUE` 和 `PRIVATE_TOKEN`。与其只检查“脚本没有崩溃”，我们更应该验证“不该保存的内容确实没有保存”。仓库里的 [`test_next.py`](examples/v04/tests/test_next.py) 已经为这种脱敏行为设置了自动化断言。

同样，未知事件、不完整 JSON、超过大小上限的单行数据应当安全跳过，不能因此使用户的完整原始命令被写入错误日志。对于高级监控系统来说，这类**失败时仍然保持隐私边界**的行为，往往比多支持一种新事件更加重要。

## 八、可以立刻接到实时 App Server 吗？

先回答边界：**本篇没有这样做，也不应声称做到了。**

真实 App Server 客户端不仅要解析 JSONL，还必须初始化连接、处理双向请求和生命周期、正确管理权限与审批请求。我们当前的示例只负责对已导出的通知做只读投影。这样做可以保留原来“监督系统与执行 Agent 分离”的工程原则；对于个人第一版而言，先把协议数据模型和存储边界验证清楚，是合理的分阶段步骤。

未来需要实时接入时，可以增加一个单独的客户端模块，但要确保运行时审批仍由明确授权的客户端处理，Watchdog 不应该凭借监控的名义自动批准命令，也不要为了抓取完整内容而绕过 Codex 的权限机制。

相关官方文档：[Codex App Server](https://developers.openai.com/codex/app-server)，[Codex Hooks](https://developers.openai.com/codex/hooks)。

## 九、常见问题与边界

**导入结果为 0。** 先确认文件确实是一行一个 JSON 对象；检查 `method` 是否在 `METHODS` 白名单；再检查真实工具事件是不是使用当前支持的命名。不要让适配器静默把陌生方法映射为成功。

**`journal.py` 显示事件数大于预期。** 检查是否多次运行了导出适配器，导致脱敏输出被重复追加。SQLite 防止相同文件位置的重复导入，但不能证明两个不同位置的内容是同一次真实执行。

**我想知道 Codex 具体执行了哪一条命令。** 当前安全设计没有存储命令正文。你可以在受信任的原始工具界面人工查看，或在未来按用户授权增加受限、脱敏的局部诊断功能；不能因为监控需要就默认把密码和源码写进长期日志。

**App Server 的事件序列中包含缺失回合。** 可能是导出范围不全，也可能因为部分方法不在白名单。监督器应当说明观测覆盖不完整，而不是补出不存在的 `turn/started`。

## 十、本篇验收与下一篇

本篇验收包括：一份明确来源的离线 NDJSON；成功导出安全事件；人工检查敏感命令和输出均未出现；SQLite 可导入；重新导入无新增字节时不重复入库；面对不支持的事件能如实报告跳过数量。

做完以后，你能把**较丰富的会话执行单位**放进自己的账本。但你仍然无法回答一个更重要的问题：“这些操作究竟在推进哪一项原始任务要求？”这就是第 15 篇要解决的：从事件数量走向**任务目标与独立验收的关联**。

延伸阅读：[官方 App Server 文档](https://developers.openai.com/codex/app-server) · [本篇适配器](examples/v04/watchdog/appserver_adapter.py) · [SQLite 模块](examples/v04/watchdog/journal.py) · [相关测试](examples/v04/tests/test_next.py)。
