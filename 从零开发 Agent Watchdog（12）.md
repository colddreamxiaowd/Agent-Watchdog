# 从零开发 Agent Watchdog（12）：项目长期运行与交接——让明天的你不必重新猜昨天发生了什么

> **系列教程 · 第 12 篇** · SQLite Backup · 恢复验证 · 状态摘要 · 长期迭代  
> 这一篇是第 04–12 篇的阶段性收束：我们不再增加新模型，而是让已有模块经得起停止、重启和交接。

今天晚上你让 Codex 研究一个复杂 Bug。它修改代码、执行多次测试，并在最后告诉你“还差一步”。你关机睡觉。第二天打开 Agent Watchdog，最重要的问题不是“界面还有没有颜色”，而是：**我能不能根据可靠的记录恢复昨天的任务状态，知道哪些证据仍然有效，哪些决定必须重新确认？**

## 一、长期运行不等于永远不关闭

真正可靠的软件不能只在一个从不关闭的终端里工作。我们希望它至少可以：

```text
第一次启动：创建/读取已批准合同
       ↓
观察 Codex Hook 元数据
       ↓
触发 Git 独立检查
       ↓
按需保存测试验收
       ↓
导入 SQLite 事件账本
       ↓
关闭 / 崩溃 / 重启
       ↓
重新打开：按已保存数据恢复
       ↓
核对当前 Git 指纹与旧证据的有效性
       ↓
生成新一次交接摘要
```

不要把“读回 JSON 和 SQLite”误认为“自动恢复 Codex 进程”。我们的 V1.0 目标始终是一个**独立监督者**，不是私自替用户重启和控制 Agent 的执行引擎。

## 二、区分哪些数据必须保存，哪些应该重新计算

| 数据 | 是否持久保存 | 为什么 |
|---|---|---|
| 原始脱敏 JSONL | 是 | 采集阶段的可复查来源 |
| SQLite 事件账本 | 是 | 支持去重导入、会话历史查询 |
| 人工批准的合同摘要 | 是 | 防止任务规则悄悄变化 |
| 测试结果与文件快照 | 是 | 判断测试是否仍适用于当前代码 |
| 当前 Git 工作树扫描 | 每次恢复时重新计算 | 工作目录可能在 Watchdog 关闭时变化 |
| 监控面板当前窗口 | 不需要 | 可由事件与状态重新构建 |
| 未授权的自动恢复命令 | 不保存、不执行 | 没有人工同意的控制行为不应存在 |

你应该特别理解第 5 行。**昨晚的 `PASSED` 不等于今天仍然 `PASSED`。** 即使 Watchdog 关闭时有人手动修改过文件，今天重新扫描也必须重新比较指纹。

## 三、第一次做真正的数据库备份

SQLite 在 WAL 模式下可能存在数据库主文件之外的辅助文件。因此不要把“复制 `.sqlite3` 文件”当作完整、始终一致的在线备份方法。

我们使用 Python 标准库 `sqlite3.Connection.backup()`：

```python
source = sqlite3.connect("journal.sqlite3")
target = sqlite3.connect("journal.backup.sqlite3")
source.backup(target)
```

仓库里的 [`journal.py`](examples/v04/watchdog/journal.py) 已经提供了对应 CLI：

```bat
conda activate torch_env
cd /d D:\program\agent_watchdog\watchdog
python journal.py backup --dest "D:\program\agent_watchdog\backup\journal_20261008.sqlite3"
```

目标目录需要已存在；你可以先执行：

```bat
mkdir D:\program\agent_watchdog\backup
```

备份后不要只看文件是否出现。我们还需要用 `journal.py summary --db ...` 对备份执行 `integrity_check`，确认它至少是一份 SQLite 能读的数据库。

```bat
python journal.py summary --db "D:\program\agent_watchdog\backup\journal_20261008.sqlite3"
```

如果出现 `integrity: ok`，说明 SQLite 的基本结构检查通过；这仍不意味着每条 Codex 操作都被采集了。

## 四、生成一份不依赖聊天记忆的项目交接摘要

执行：

```bat
python bridge.py --repo "D:\program\agent_watchdog\hook_demo" --once
python watchdog_cli.py --repo "D:\program\agent_watchdog\hook_demo" handoff --out "D:\program\agent_watchdog\handoff_latest.md"
```

打开 `handoff_latest.md`，应该能够看到：

```text
# Agent Watchdog — 交接快照

仓库：...
当前文件指纹：...
最近扫描：...
测试 A1：PASSED
测试 A2：STALE
保护文件变化：...

下次继续前：
- 先核对合同
- 审核 Git diff
- 调查未验证测试
```

这些内容不是 Agent 自己编出来的“总结”，而是从合同、Git、测试状态和已实现的风险规则派生出来的**可追溯摘要**。但不要忘记：如果上游观测范围有限，交接摘要也只能忠实表达那个范围。

比如摘要写“未观察到保护文件变化”，指的只是 Git 可见范围内的比较。它不等于“没有任何敏感文件被访问”。

## 五、做一次有意义的恢复实验

请不要仅仅执行 `backup` 并截图。我们真正要验证的是恢复前后判断一致。

**实验 A：没有新改动。**

在某项测试通过后保存合同与证据，运行 `journal.py sync`，关闭 Bridge、Monitor，再次启动。重新执行 `bridge.py --once` 和 `task_contract.py status`。如果文件没有变，原有证据仍可能有效。

**实验 B：监督器关闭期间发生改动。**

关闭 Bridge，在 IDE 中改变 `hello.py` 一行注释，再重新运行 `bridge.py --once` 和合同 `status`。旧测试应变成 `STALE`，即使期间没有任何 Hook 事件。

**实验 C：JSONL 重复导入。**

连续执行两次 `journal.py sync`，第二次在没有新增日志的情况下不应重复插入已读事件。

**实验 D：关键验收合同被修改。**

对监督器保存的合同做一处可见修改，再执行 `status`。之前的人类批准应该失效，不能用旧记录自动宣布 VERIFIED_COMPLETE。

四项都能区分“普通重启”和“恢复后状态仍可信”。

## 六、长期使用时应当保护哪些文件？

你很可能会把这个项目放到 GitHub。但是以下文件不应该默认提交：

```gitignore
examples/v04/watchdog/logs/
examples/v04/watchdog/state/
examples/v04/watchdog/data/
*.sqlite3
*.sqlite3-shm
*.sqlite3-wal
```

原因不是它们“代码质量差”，而是它们属于用户本地的观测历史，可能包含会话编号、路径和项目状态。即使 Logger 已经做了脱敏，**也不代表日志可以无审核地公开上传**。

对于长期运行还应该考虑磁盘空间上限、日志轮转、并发写入和备份保留策略。当前 V0.9 的 `journal.py` 对日志轮转的处理仍有明确局限，这些应列在项目 Issues，而不是伪装成“企业级可靠性”。

## 七、这条工程路线究竟实现了什么？

到了这一步，我们的系统已经具有几个相互独立的原型模块：

```text
Agent Watchdog
├── Hook Logger       事件元数据采集
├── Bridge            事件驱动 Git 扫描
├── Evidence          独立文件与测试证据
├── Task Contract     人工批准的目标与验收
├── Risk              保守的事实与启发式提示
├── Rich Monitor      终端查看
├── SQLite Journal    持久事件账本
└── Handoff           可交接的状态摘要
```

它仍**不是**：完整的所有 Codex 行为审计；能精确理解任何用户自然语言意图的评审 Agent；自动修复不良行为的安全控制器；准确率经过真实轨迹校准的卡住分类器；已经在你电脑上 24 小时无人值守验证的成熟软件。

这些缺口是真实存在的，不需要隐藏。它们反而给下一阶段的实战提供了明确目标。

## 八、下一阶段路线：先做真实验收，再谈产品化

你最需要的下一步不是继续追加 30 篇没有实测的教程，而是把**本机真实运行**作为第 13 篇：

1. 检查当前 Windows Codex 版本、Hooks 信任状态和 Runner 绝对路径。
2. 在 `hook_demo` 上完成一次真实工具操作，保存现场观测的脱敏元数据。
3. 让 Bridge 确认 Git 变化来自独立扫描，防止以工具日志代替实际证据。
4. 把 Task Contract 的 A1/A2 跑通，验证改代码后 STALE。
5. 用 SQLite 与 Handoff 执行一次关机/重启恢复实验。
6. 对误报和缺失事件单独记录，不美化结果。

如果未来需要更完整的会话事件，就进一步评估 Codex App Server 官方协议；如果需要语义目标偏离判断，再考虑引入一个经过评测的小模型模块。**不要为了看起来“智能”而牺牲监督器的可信度。**

本篇最终验收：数据库备份可通过 `integrity_check`；重启后的文件变化会使旧证据过期；交接报告来自实际状态而不是模型自述；任何需要执行测试或更改文件的动作仍由用户明确决定。

参考：[Codex App Server](https://developers.openai.com/codex/app-server) · [SQLite Backup API](https://sqlite.org/backup.html) · [完整源码与测试](examples/v04/)。
