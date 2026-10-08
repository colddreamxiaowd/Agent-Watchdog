# 从零开发 Agent Watchdog（09）：SQLite 事件账本——Bridge 重启后还记得什么？

> **系列教程 · 第 9 篇** · SQLite · JSONL · 游标 · 事务 · Crash Recovery  
> 本篇不是要抛弃第一篇的 JSONL，而是学习如何在已有日志之上建立可查询的持久事件账本。

假设你晚上让 Codex 持续做一个复杂任务，Bridge 在第 40 分钟崩了，五分钟后你才重新启动。第 04 篇的 Bridge 为了轻量，启动时默认从日志末尾读新事件，它确实能工作，但中间五分钟的事件可能根本没有进入监控统计。又或者你从头读取整个 JSONL，重复导入会让工具调用次数翻倍。

一个可以日常使用的监督系统，必须认真解决“崩溃后的记忆”问题。

## 一、理解三种不同的数据

我们先把容易混淆的东西拆开：

- **原始采集日志（JSONL）**：每一行是经过脱敏的事件元数据，方便追加、人工检查。
- **持久事件账本（SQLite）**：按事件来源、偏移量保存每条已导入记录，支持查询和去重。
- **当前证据报告（bridge_report.json）**：对某个项目最近一次 Git 扫描的结果，属于可重新生成的快照。

后两项不能互相替代。事件账本告诉你“观察到了哪些事件”，证据快照告诉你“当前 Git 可见文件和测试证据是什么状态”。即使事件库十分完整，也无法从“PostToolUse 出现过”推导“文件是 Codex 改的”或“用户目标完成”。

## 二、为什么不用 JSONL 单独承担全部功能？

JSONL 非常适合追加：

```jsonl
{"event":"PreToolUse","tool":"Bash","session_id":"abc"}
{"event":"PostToolUse","tool":"Bash","session_id":"abc"}
{"event":"Stop","tool":null,"session_id":"abc"}
```

但它天然缺少我们这次需要的可靠查询和去重语义。比如“某个会话在上周产生了多少条事件？”、“这条文件偏移上的事件之前导入过吗？”、“事件已经入库，但游标没更新怎么办？”

SQLite 是合适的工程选择：单机数据库、Python 标准库自带 `sqlite3`、无需另开服务。对你这类个人 Windows 工程，先用 SQLite 比启动大型数据库更节省维护成本。

## 三、真正重要的不是表，而是事件与游标同事务

假设导入程序做了两件事：

```text
A. INSERT event
B. UPDATE cursor
```

如果 A 成功但在 B 之前程序崩溃，重启后又读到同一条；如果先 B 后 A，则可能永久跳过某条事件。

我们的设计把两件操作放在**同一个 SQLite 事务**中。对应实现见 [`journal.py`](examples/v04/watchdog/journal.py)：

```python
with con:
    # 读取已经提交的游标
    # INSERT OR IGNORE 当前批次完整日志行
    # UPDATE 已经消费到的字节 offset
    # 退出事务块统一 commit，异常则 rollback
```

需要强调两点。第一，这个实现提供的是本地文件导入的事务一致性，不是跨电脑分布式消息队列的 exactly-once 保证。第二，重复导入去重使用 `(source_path, file_generation, byte_offset)`，所以它的可靠性依赖文件代际与偏移量的判断；遇到复杂日志轮转、文件原地重写等情况，需要进一步改进。

## 四、什么叫 byte offset？为什么不只记住行数？

字节偏移是当前文件已经读到哪个**字节位置**。例如第一行用 UTF-8 编码占 123 字节，第二行占 151 字节，那么读完两行后 offset 可能是 274。

这与文本字符数不一样。中文可能占多个 UTF-8 字节，因此不能用 Python 字符串的 `len()` 充当原文件字节偏移。我们直接以 `rb` 模式打开日志，根据读到的原始 bytes 推进偏移量。

另外还有一个非常重要的细节：写入文件时如果程序刚好读到半条 JSON，不能把它当成完整事件。

```text
已写入：{"event":"PostToolUse"}\n
正在写：{"event":"Stop","tool":
```

导入器只消费**最后一个完整换行之前的内容**。后面的半行留到下一次再读，避免把一次正常的并发写入误判为永久损坏。

## 五、打开真实源码：它如何保证重复运行不重复计数？

[`journal.py`](examples/v04/watchdog/journal.py) 建立两个表：

```sql
CREATE TABLE events (
  source_path TEXT NOT NULL,
  file_generation TEXT NOT NULL,
  byte_offset INTEGER NOT NULL,
  payload TEXT NOT NULL,
  PRIMARY KEY(source_path, file_generation, byte_offset)
);
```

```sql
CREATE TABLE cursors (
  source_path TEXT PRIMARY KEY,
  generation TEXT NOT NULL,
  offset INTEGER NOT NULL
);
```

主键允许 `INSERT OR IGNORE` 对已经导入过的同一日志位置去重。游标表保存下一次从哪里继续。

本篇还启用了 SQLite 的 WAL 模式，适合一个进程写入、另一个进程查询的本机使用方式。但 WAL 不是“永不损坏”，不能把数据库直接当成随意复制的单文件备份。备份必须使用 SQLite 的 Backup API，后面第 12 篇会演示。

## 六、动手实验：首次导入、重复导入、数据库检查

仍然使用 `D:\program\agent_watchdog\watchdog`。首先完成第四篇的模拟或真实事件采集，让 `logs/events.jsonl` 中至少有几行记录。

然后打开 CMD：

```bat
conda activate torch_env
cd /d D:\program\agent_watchdog\watchdog
python journal.py sync
python journal.py summary
```

首次导入会显示类似：

```text
Imported: 12
```

重新运行**同一条导入命令**：

```bat
python journal.py sync
```

如果日志没有增长，应该得到：

```text
Imported: 0
```

这才是验证“重复导入不增加记录”的正确实验。别通过清空数据库来证明去重，也别用测试时随意增长的日志与预期数字硬比较。

接着执行：

```bat
python journal.py summary
```

报告包含 `events`、`distinct_sessions` 和 SQLite `integrity_check`。请记住，会话个数只是**记录中有多少不同的 session_id**；它不能证明所有会话都被完整采集。

## 七、动手实验：测试未写完的 JSON 行

你可以在单独的临时 JSONL 中手工写入：

```text
{"event":"PostToolUse","tool":"Bash"}
{"event":
```

导入后只应增加第一条。随后继续补全第二行：

```text
"Stop"}
```

下一次导入才应增加第二条。仓库提供的单元测试 `test_journal_dedup_and_partial` 直接模拟了这个过程。

不要在你的正式事件日志里做这个破坏性实验；另外新建临时文件即可。

## 八、当前版本还不能保证什么？

这是本篇必须保留的工程边界：

1. JSONL 本身不是安全审计系统：相同账户下的其他进程可能修改或删除它。
2. inode/路径与偏移量不能完美识别所有 Windows 文件轮转与原地重写；这属于后续要改进的恢复场景。
3. 工具 Hook 覆盖不了所有 Agent 内部动作；数据库完整不等于实际执行轨迹完整。
4. 本篇事件入库与第四篇 Bridge 并行存在；我们还没有让 Bridge 的每一次扫描都使用 SQLite 游标驱动，也没有跨进程状态一致性证明。
5. 日志有隐私限制；只存工具名称无法分析命令语义，这是主动牺牲的信息能力。

本篇通过标准：重复 `sync` 不重复增加事件；不消费半行；数据库 `integrity_check` 是 `ok`；手工更改文件后不会错误地将历史事件当成验收证据；能明确说出持久性与完整性的区别。

下一篇我们将接入**更真实的 Codex 结构化执行输出**，但仍坚持默认不保存原始用户提示词与工具输出。

参考：[SQLite Transactions](https://sqlite.org/lang_transaction.html) · [SQLite WAL](https://sqlite.org/wal.html) · [Python sqlite3](https://docs.python.org/3/library/sqlite3.html)。
