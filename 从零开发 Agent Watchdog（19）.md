# 从零开发 Agent Watchdog（19）：让监督器经得起重启——日志、备份、断线恢复与长期运行

系列教程 · 第 19 篇｜Python · SQLite WAL · Windows 11 · 可靠性工程

> 本篇新增 `operations.py`，并以第 09 篇的 `journal.py`、第 12 篇的交接报告为基础，学习如何检查监督数据是否可读、如何安全备份、如何发现过期的快照。它不会启动 Codex，不会偷偷自动重试失败任务，也不会删除原始日志。

## 一、一种更隐蔽的失败：面板还开着，数据却停在昨天

想象这样一个场景。你晚上启动 Codex 完成一项长任务，Watchdog Web 面板也正常打开。第二天早上，你看到“验收项 2/3 已通过、零条新警报”，于是认为系统还在工作。但事实上，Bridge 在昨天 23:40 就退出了，页面一直显示最后一次保存的报告。

这比直接弹出错误更危险。因为“报告能打开”和“报告足够新”是两件事。

另一个场景：你的 `events.jsonl` 已经保存了几万条事件，SQLite 也建好了。Windows 意外重启后，你重新执行同步命令。如果游标没有正确恢复，可能重复计数；如果只看最新事件，则可能漏掉事故发生前的证据。

所以第 19 篇要回答：

**Watchdog 自己现在是否健康？历史是不是还在？我们又凭什么相信它显示的是当前状态？**

这回我们先解决三项可验证的基本能力，而不是直接承诺 24 小时无人值守：

1. `doctor`：明确检查数据库可读性、Git 快照新鲜度；缺失就提示需要处理。
2. `backup`：显式创建可校验的 SQLite 备份，不覆盖已有文件、不写入受监控仓库。
3. 恢复流程：按照顺序检查持久化、游标、Bridge、页面和最新合同，不依赖“记得昨天运行到哪里了”。

## 二、把“软件运行正常”拆成三个不同问题

我们通常会把健康检查（Health Check）理解成进程还在不在。但对 Watchdog 来说，这远远不够。

**进程级健康**：`python bridge.py` 是否还在运行？Streamlit 页面是否能打开？这需要操作系统、任务管理器或进程监测协助。

**数据级健康**：SQLite 文件能否读取？`PRAGMA integrity_check` 是否返回 `ok`？最近的 `bridge_report.json` 是否具有可解析时间？

**业务级健康**：有没有接收到来自真实 Codex 的事件？合同是否对应原始要求？测试证据是否仍有效？这需要额外的现场验收，不是仅靠数据库检查就能证明的。

我们本篇实现的是**部分数据级健康检查**。医生脚本显示 `CHECKS_OK`，也只表示两类检查通过，绝不等于整个系统健康，更不等于 Codex 已被真实接入。

## 三、再次理解 SQLite：为什么不能直接复制 WAL 文件？

第 09 篇使用 SQLite 记录事件，启用了 WAL（Write-Ahead Logging，预写日志）模式。它有助于读写并发，但这意味着运行中的 SQLite 状态可能同时涉及主数据库和 `-wal` 等旁文件。

如果你只是简单执行：

```bat
copy journal.sqlite3 backup.sqlite3
```

你未必拿到了事务一致的在线备份。对于正在写入的数据库，应该使用 SQLite 提供的在线备份接口。Python 自带的 `sqlite3.Connection.backup()` 就是我们这次的复用对象。

示意：

```text
持续写入的一端                 人工执行的备份端
┌────────────────┐            ┌────────────────┐
│ events.sqlite3 │ ──backup──▶│ backup.sqlite3 │
│ WAL / cursors  │            │ 可独立打开     │
└────────────────┘            └────────────────┘
                                          │
                                          ▼
                                  PRAGMA integrity_check
```

这里说的“完整性”是 SQLite 文件内部结构层面的基本检查，不代表历史事件都真实、所有外部文件都备份了，也不保证数据库从来没有被人为篡改。

## 四、你以前已经有 journal.backup()，为什么还需要 operations.py？

第 09 篇已经实现：

```python
source.backup(target)
```

那为什么不直接沿用？因为**可用的底层 API ≠ 安全的日常操作工作流**。你还需要确定目标文件是否已经存在、是否错误地落入被监督仓库、备份后是否可读、命令失败时怎样清理不完整结果。

本篇的 `operations.archive()` 是底层 `journal.backup()` 的一个保护性包装：

```python
if not source.is_file():
    raise FileNotFoundError('No existing database to back up')
if target.exists():
    raise FileExistsError('Refusing to overwrite existing backup')
if target.is_relative_to(repo):
    raise ValueError('Backups must be outside the monitored repository')
```

这里做的是三道很有必要的门槛：没有源数据就不造假；已有备份就不覆盖；备份输出留在被监控仓库外面，避免它自己使测试证据过期。

完整代码见 [examples/v04/watchdog/operations.py](examples/v04/watchdog/operations.py)。如果 Python 环境低于 3.9，`Path.is_relative_to()` 不可用；本系列已要求 Python 3.9+。

## 五、doctor：到底检查了什么？

先认识输出结构：

```json
{
  "database": "MISSING",
  "git_report": "MISSING",
  "alerts": [
    "事件账本不可用；不能声称完整的历史记录",
    "Git 状态快照缺失或不新鲜；人工启动 Bridge 排查"
  ],
  "status": "ACTION_REQUIRED"
}
```

这是缺少文件时的**示例输出**。实际字段还包括受监控仓库路径等信息。

当 Git 报告存在时，脚本读取其中的 `scanned_at` 时间戳，转换为带时区的 UTC，再计算它与当前时间的差。超过 120 秒的报告会标记为 `STALE`；早于当前时间太多或含非法时间格式也不被当作新鲜。

```python
seconds = (
    datetime.now(timezone.utc)
    - stamp.astimezone(timezone.utc)
).total_seconds()

status = 'FRESH' if -30 <= seconds <= report_age_seconds else 'STALE'
```

两个值得思考的边界：第一，**120 秒是当前课程的工作假设**，并非监控软件通用标准；第二，操作系统时间异常、进程暂停、Bridge 扫描期间卡住等情况仍可能影响判断。真正的长期运行系统可能需要专用 heartbeat、单调计时、Windows 事件日志和更严谨的延迟统计。

`database` 检查则使用 SQLite 自带的 `PRAGMA integrity_check` 并读取事件行数：数据库缺失、读取失败、完整性失败被明确区分。

注意，即便 `event_rows=0` 且 `integrity_check=ok`，它也不能说明真实 Codex 连接成功。数据库完整性与数据来源可靠性属于两个问题。

## 六、实验 A：先看一个失败的健康检查

请打开 **Anaconda Prompt**：

```bat
conda activate torch_env
cd /d D:\program\agent_watchdog\watchdog
python operations.py --repo "D:\program\agent_watchdog\hook_demo" doctor
```

如果你的 SQLite 或 Bridge 状态尚未创建，应该得到 `ACTION_REQUIRED`，并说明原因。我们的目标不是把每次启动都变成绿色，而是让缺失情况具有可操作解释。

现在手工运行一次旧版 Bridge 扫描：

```bat
python bridge.py --repo "D:\program\agent_watchdog\hook_demo" --once
```

然后再次执行 `doctor`。如果数据库仍未创建，Git 报告即使已经新鲜，整体也仍可能是 `ACTION_REQUIRED`。这非常合理，因为状态扫描并不会自动把事件写入 SQLite。

手动同步已有的脱敏 Hook 日志：

```bat
python journal.py sync
python journal.py summary
```

如果这时数据库存在且完整性检查成功，doctor 才可能显示 `CHECKS_OK`。但仍必须再读第 13 篇的真实接入验收工作单，不能把它误写成 `CODEx_CONNECTED`。

## 七、实验 B：做一份在线备份

**备份位置要在被监控仓库之外**，例如：

```text
D:\program\agent_watchdog\watchdog_backup\20261008_events.sqlite3
```

这个文件名只是示例。如果文件已存在，脚本会拒绝覆盖，请换用新的名字。执行：

```bat
python operations.py --repo "D:\program\agent_watchdog\hook_demo" backup --out "D:\program\agent_watchdog\watchdog_backup\events_backup_001.sqlite3"
```

默认从 `watchdog/data/journal.sqlite3` 读取。假如你以前自己改过数据库位置，增加 `--db` 参数：

```bat
python operations.py --repo "D:\program\agent_watchdog\hook_demo" --db "D:\program\agent_watchdog\watchdog\data\journal.sqlite3" backup --out "D:\program\agent_watchdog\watchdog_backup\events_backup_002.sqlite3"
```

成功时返回 `VERIFIED_BACKUP` 和文件路径及大小。然后尝试再执行一次**相同**的命令，预期得到 `FileExistsError`，它证明程序没有默认覆盖你先前的备份。

另一个反例是把备份目标指到 `hook_demo` 内，脚本应拒绝它，因为这样会污染被监控仓库的 Git 可见范围，可能使刚刚通过的测试变成 `STALE`。

这种“故意做错，确认保护生效”的实验，比单纯看见备份文件存在更有教育意义。

## 八、实验 C：真的从备份恢复一份副本

备份成功后，你可以先**复制到一个全新的、不在真实项目里的恢复目录**，然后执行：

```bat
python journal.py summary --db "D:\program\agent_watchdog\watchdog_backup\events_backup_001.sqlite3"
```

确认 `integrity` 显示 `ok`、事件数符合你的预期。这一步只在备份副本上读数据，不触碰原始 SQLite。

正式恢复到工作路径应该由你在确认停机、确认最新备份、核对存储空间并保存原始文件副本之后手动完成。**本篇代码没有自动覆盖工作数据库的 restore 命令。** 这是刻意保留的人工保护门槛。

为什么不做自动恢复？因为真实历史可能部分落在未同步的 JSONL 文件里，或者备份比现有工作数据库旧。直接自动用旧备份覆盖，可能比数据库损坏本身造成更多证据损失。

## 九、长期运行：我建议分三个层次推进

### 第一层：可靠的手工启动与关闭

建议建立一份自己的《日常使用清单》：启动 Codex 前先明确监控仓库，运行 Bridge、事件同步、Web；停止工作时生成交接报告和备份。每次启动都检查 `doctor` 的结果。这种方式不够自动化，但容易定位问题。

### 第二层：Windows 任务计划程序定时诊断

Windows 任务计划程序可以按用户配置定时执行脚本。但初学阶段**不建议马上把运行未知测试命令或自动恢复过程放进去**。如果你自己要配置计划任务，只让它运行 `operations.py doctor` 或 `journal.py sync` 这种边界明确的操作，并将输出保存在你控制的私人目录。

本轮并没有通过真实 Windows 任务计划程序做长时间测试，所以文章不会给出“每天早上一定准时提醒”的承诺。脚本也没有系统通知推送功能，`doctor` 目前只向终端输出 JSON。

### 第三层：真正的长期运行验收

到了要给软件贴 V1.0 标签之前，至少要有以下观测：电脑休眠和恢复后日志是否继续、意外终止 Bridge 后能否发现缺口、重复同步不会重复计数、磁盘空间不足时是否给出错误、数据库备份是否能还原、不同仓库之间是否隔离，以及 24–72 小时左右的运行记录（具体观察周期由你决定）。

不要以“脚本跑了两分钟没报错”推导长期稳定性。

## 十、为什么没有“自动 kill / retry / rollback”按钮？

自动控制 Agent 的诱惑非常大。看见异常就给 Codex 发送一条“重新规划”的提示，听起来很智能，但它又引入了新的风险：监督器自己可能误判；反复重试会造成额外费用；回滚可能删除用户未提交的工作；终止进程可能损坏部分写入中的工作文件。

本系列 V1.0 的一条底线是：**Watchdog 默认提供观察、核验和建议；是否改变执行策略仍由用户批准。** 这也与第 17 篇的设计呼应——模型或启发式的弱信号不能直接变成高风险控制动作。

## 十一、长期交接报告应该保留什么？

第 12 篇的 `watchdog_cli.py handoff` 已经可以生成一份 Markdown 快照：仓库、Git 指纹、合同阶段、验收项和风险提示。

你可以执行：

```bat
python watchdog_cli.py --repo "D:\program\agent_watchdog\hook_demo" handoff --out "D:\program\agent_watchdog\watchdog_backup\handoff_latest.md"
```

它不是完整审计日志，更不能自动保证这些状态都来自真实 Codex。写完后应与合同原文、Git diff、测试输出及当前系统版本一起保存。不要把内部工作路径、敏感会话数据或未脱敏文件直接公开到 GitHub。

## 十二、常见故障排查表

| 症状 | 首先检查 | 不应采取的动作 |
|---|---|---|
| doctor 报 `MISSING` | 相关数据库/报告是否存在，路径是否相同 | 不要为了变绿就伪造空事件 |
| `git_report=STALE` | Bridge 是否还在运行、路径与时钟是否正确 | 不要直接声明 Agent 已经卡住 |
| 备份拒绝覆盖 | 目标文件已存在 | 不要删除老备份后反复试 |
| 数据库损坏或读取失败 | 保存原始文件和 WAL，核对备份 | 不要自动覆写当前数据库 |
| 事件越来越多 | 日志轮换、存储空间、保留策略 | 不要直接删除未备份的事件源 |
| Windows 唤醒后看不到事件 | Hook、Bridge、Codex 是否仍存活 | 不要从空白面板推断工作成功 |

本篇诊断脚本也有局限：没有进程心跳，没有跨机器容错，没有严格的磁盘压力测试，不能自动检测所有意外退出。它是为后续可靠性工程打下的一块可以测量的基础，而不是一套已经完成的生产级监控平台。

## 十三、本篇验收清单

- [ ] `doctor` 能将数据库缺失、扫描报告过期明确标成 `ACTION_REQUIRED`。
- [ ] 可以显式创建不覆盖旧文件的 SQLite 备份。
- [ ] 备份目标落在受监控仓库内时会被拒绝。
- [ ] 能从独立备份文件读取事件数和 `integrity_check` 结果。
- [ ] 关闭 Streamlit 不会要求 Codex 停止，备份操作不触发 Agent 自动恢复。
- [ ] 能解释数据级健康、进程级健康和业务级健康为什么不能混在一起。
- [ ] 在真实 Windows 长期运行验证尚未完成时，绝不宣称系统已经 24 小时可靠。

**小结**：到这里，Agent Watchdog 的核心功能、Web 观察界面和基本数据维护流程已经有了原型。最后的问题不是“还要加什么功能”，而是“这些功能是否真的足以发布一个可信的 V1.0”。第 20 篇要严格回答这个问题。

### 官方参考与源码

- [本篇完整源码 operations.py](examples/v04/watchdog/operations.py)
- [现有 SQLite 账本 journal.py](examples/v04/watchdog/journal.py)
- [交接命令 watchdog_cli.py](examples/v04/watchdog/watchdog_cli.py)
- [SQLite Online Backup API](https://www.sqlite.org/backup.html)
- [Python sqlite3 Connection.backup](https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup)
- [第 09 篇：事件账本](从零开发%20Agent%20Watchdog（09）.md)

> 课堂参考实现的自动化测试只覆盖了部分缺失状态、拒绝覆盖与备份完整性；你本机 Windows 休眠/恢复、异常断电和长时运行仍是独立的验收任务。
