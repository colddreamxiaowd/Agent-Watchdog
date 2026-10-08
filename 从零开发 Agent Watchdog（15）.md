# 从零开发 Agent Watchdog（15）：把执行证据对应到任务要求——为什么“完成 80%”不能靠猜？

系列教程 · 第 15 篇 | Task Contract · Milestone · 验收映射 · 证据过期 · 进度追踪

前一篇，我们已经能把 Codex 的 `thread / turn / item` 等元数据安全地收集进自己的事件账本。可是打开面板，你可能会发现另一个问题：

```text
最近观察到：62 条事件
最近工具：commandExecution
本次有文件修改：4 个
Agent 回复：修复完成
```

这些信息看起来很丰富，却还缺少最关键的一行：**原始任务到底完成了什么？**

如果用户最初要求“修复登录接口、保持数据库结构不变、全部回归测试通过”，那么 62 条事件不是 62% 进度，四个修改文件不是“四个步骤完成”，Agent 自称完成也不是验收证据。这种把活动量当进度的错误，在 Agent 长任务监控里尤其容易发生。

第 05–06 篇曾经建立了任务合同 `Task Contract`，能够固定用户批准的目标与验收命令，并记录 `NOT_TESTED / PASSED / FAILED / STALE / INCONCLUSIVE`。现在我们要把它们组织为读者能够理解的**任务进度面板**，但不能伪造“语义完成率”。

本篇新增 [`progress.py`](examples/v04/watchdog/progress.py)。它不启动任何测试，不接受 Agent 自己修改的最新任务总结，只读取已经获批的合同以及当前 Git 快照对应的验收结果。

## 一、先理解：工作进度与可验证覆盖率不是一回事

假设合同只有四个验收条件：

```text
A1：登录接口正向测试
A2：错误密码拒绝测试
A3：数据库结构无改动
A4：完整回归测试
```

现在 A1 和 A2 都通过了，A3 尚未检查，A4 测试结果过期。

我们可以无歧义地说：**已配置的四项验收中，两项当前有通过证据**。

但是否能说“项目已经完成 50%”？不能。这四项可能工作量和难度不同，甚至合同里可能漏掉了用户原本很重视的安全约束、部署或兼容性要求。这个 2/4 只是**验收覆盖数**，不是“已经花掉的工作比例”或“用户需求实现比例”。

所以本篇代码使用两个明确的字段：

```json
{
  "verified_checks": 2,
  "total_checks": 4,
  "scope": "Number of contract acceptance checks verified, NOT percentage of task work"
}
```

这里的第三行看似啰嗦，实则是反止损措施。假如后来你把报告给另一位同学或另一个 Agent，第三行可以防止他们把 `2/4` 误读成“AI 项目完成了一半”。

## 二、我们为什么需要 Milestone，而不只用 Acceptance？

`Acceptance` 是“怎样证明某项要求满足”；`Milestone` 是“哪些验收项共同组成一个读者能理解的阶段”。

例如：

```text
任务：修复登录系统
├── M1：登录行为正确
│   ├── A1：正确密码能登录
│   └── A2：错误密码被拒绝
├── M2：旧功能不回归
│   └── A3：完整单元测试通过
└── M3：部署前验证
    ├── A4：配置一致性检查
    └── A5：人工确认环境准备
```

你可能会想，“何不直接让 LLM 从最近日志推断 M1 已完成？” 问题是，LLM 能给出**解释或建议**，却不能把自己生成的解释变成 A1 的真实退出码。我们先设计一个可审计的映射：每个里程碑引用明确的验收 ID；状态只能由这些验收 ID 推导。

这个映射一旦属于任务合同，就应该受到第 05 篇的合同摘要保护。Agent 不能因为 A3 一直失败，就悄悄把 M2 的验收内容改成“无须回归测试”。

## 三、新增里程碑，不改动旧状态机

我们不会推翻 `task_contract.py`。它已经提供了三项关键能力：

- `load(repo)`：读取合同和批准状态。
- `acceptance_status(repo)`：根据当前 Git 文件快照重新判断各项验收状态。
- `run_one(repo, id)`：用户明确调用时执行批准过的测试，并保存退出码和执行前后快照。

新文件 `progress.py` 只调用前两项进行**只读的进度计算**。它不自动运行 `run_one()`，也不修改合同或结果。

假设合同含有下面的可选字段：

```json
{
  "schema_version": 1,
  "goal": "修复 hello.py，保留原始任务约束",
  "protected_paths": ["GOAL.md"],
  "acceptance": [
    {
      "id": "A1",
      "description": "hello.py 返回正确问候语",
      "command": ["python", "-m", "unittest", "test_hello.py", "-v"]
    },
    {
      "id": "A2",
      "description": "全部回归测试",
      "command": ["python", "-m", "unittest", "discover", "-p", "test_*.py", "-v"]
    }
  ],
  "milestones": [
    {"id": "M1", "title": "功能行为验证", "acceptance_ids": ["A1"]},
    {"id": "M2", "title": "回归验证", "acceptance_ids": ["A2"]}
  ]
}
```

`milestones` 是**我们这篇增加的可选合同结构**；前面第 05–12 篇已有的合同没有这个字段也能继续使用：`progress.py` 会把每个验收 ID 自动显示为一个默认里程碑，因此不会强迫你一次性迁移所有旧合同。

但如果你决定给现有合同增加 `milestones`，合同内容就变了。之前的 SHA-256 批准摘要必须失效，并由你重新确认。**不能为了获得漂亮的进度树就把新字段悄悄塞进已批准的合同**，否则你等于允许用户目标被程序私下篡改。

本篇完整代码：[`progress.py`](examples/v04/watchdog/progress.py)。

## 四、从已批准合同推导进度：核心机制

我们把数据流写成简单的伪代码：

```text
读取任务合同
    ↓
合同摘要是否仍与人工批准一致？
    ├── 否：UNTRUSTED_CONTRACT，不产生完成率
    └── 是
         ↓
对照当前 Git 指纹，取得每个验收项的状态
         ↓
根据里程碑映射汇总
         ↓
全部 PASSED → VERIFIED
存在 STALE / INCONCLUSIVE → NEEDS_RECHECK
存在 FAILED → FAILED
其他 → PENDING
```

这里的顺序是一个重要的设计取舍。为什么 `STALE` 会先于 `FAILED`？因为某个里程碑可能包含多个验收项，其中一个在旧文件版本失败，另一个在新版本根本没运行。把它简单贴上“FAILED”会忽略“当前快照证据已经不完整”这个更直接的行动线索。我们目前采用保守的优先级；以后可以同时显示多种原因，而不是用一个单标签抹平复杂情况。

真实代码中的核心逻辑：

```python
status = task_contract.acceptance_status(repo)
checks = status["acceptance"]

values = {check_id: checks[check_id] for check_id in acceptance_ids}

if all(x == "PASSED" for x in values.values()):
    stage = "VERIFIED"
elif any(x in {"STALE", "INCONCLUSIVE"} for x in values.values()):
    stage = "NEEDS_RECHECK"
elif any(x == "FAILED" for x in values.values()):
    stage = "FAILED"
else:
    stage = "PENDING"
```

这段代码看着不“AI”，但是可解释、可单元测试，而且最重要的是：**它不会把不确定事实转写为乐观猜测**。

## 五、动手准备：在新实验仓库批准你的合同

继续使用 `D:\program\agent_watchdog\hook_demo`。如果之前已经批准过一个合同，**不要直接覆盖旧的合同状态文件**。本节你可以先对当前状态执行：

```bat
conda activate torch_env
cd /d D:\program\agent_watchdog\watchdog
python task_contract.py --repo "D:\program\agent_watchdog\hook_demo" status
```

如果显示已有合同，建议先完成后面的**只读进度报告实验**，暂时沿用旧合同，不必添加 `milestones`。如果这是全新、安全的演示仓库，且还没有合同，才创建一份用户审核后的 JSON，并运行：

```bat
python task_contract.py --repo "D:\program\agent_watchdog\hook_demo" init --contract "D:\program\agent_watchdog\my_demo_contract.json"
python task_contract.py --repo "D:\program\agent_watchdog\hook_demo" approve
```

为什么 `my_demo_contract.json` 建议放到仓库外？因为它不是当前被监督的应用源码。如果你把它放在 Git 仓库内，作为新文件参与工作树扫描，会额外改变文件指纹，让你难以区分“项目代码变了”还是“合同实验文件变了”。同时，合同应由人审核后固定，而不是由执行 Agent 在项目目录里随手修改。

再次强调：`approve` 是一项有权限意义的动作。真正的使用场景应该由你先审核完整合同，再批准；**不是 Codex 自己写完合同就替你 approve**。

## 六、实验 A：什么都没测试，能不能显示已完成？

直接运行：

```bat
python progress.py --repo "D:\program\agent_watchdog\hook_demo"
```

假设合同只有 A1/A2，且此前没有验收记录，你应该得到与以下逻辑相符的结果：

```json
{
  "state": "IN_PROGRESS",
  "verified_checks": 0,
  "total_checks": 2,
  "milestones": [
    {"id":"M1", "state":"PENDING", "evidence":{"A1":"NOT_TESTED"}},
    {"id":"M2", "state":"PENDING", "evidence":{"A2":"NOT_TESTED"}}
  ]
}
```

这是**结构示意**，完整报告还会包含合同摘要对应的 Git 指纹等字段。你得到的实际输出以当前仓库状态为准。它真正证明的是“我们还没有看到这两项独立验收证据”，而不是“Agent 什么也没做”。

接着思考：Codex 在这期间可能已经修改了十个文件，为什么里程碑仍然没有通过？因为我们目前定义的是**证据支持的验收进度**，不是活动进度。若你想要“已尝试、正在修改、待验证”这些状态，需要在后续增加事件与每个验收项的关联，而不能自动把文件变动归入任意任务。

## 七、实验 B：通过一项验收，观察进度变化

首先确认 A1 的 `command` 是你愿意主动执行的测试命令，然后运行：

```bat
python task_contract.py --repo "D:\program\agent_watchdog\hook_demo" verify A1
python progress.py --repo "D:\program\agent_watchdog\hook_demo"
```

当测试返回退出码 0、且执行前后的 Git 指纹保持一致时，A1 才可能变成 `PASSED`。报告中的 `verified_checks` 将由 0 变为 1。注意：这并不意味着 `state` 必然是 `VERIFIED_COMPLETE`，因为 A2 可能尚未测试，或者存在保护文件变化。

这时候最值得做的不是截图一个 50% 进度条，而是去验证**为什么**这个数字变化了：新增了哪项验收证据？它对应哪个命令？是对哪一版文件快照运行的？这些问题可以从 `task_contract.py` 的状态和本地结果记录中复查。

## 八、实验 C：修改代码，观察进度“后退”

这是一项比“进度一直增加”更有价值的实验。假设 A1 刚刚通过，现在在 `hello.py` 末尾追加：

```python
# changed after acceptance
```

重新运行：

```bat
python progress.py --repo "D:\program\agent_watchdog\hook_demo"
```

预期 A1 从 `PASSED` 变成 `STALE`，对应的里程碑从 `VERIFIED` 变为 `NEEDS_RECHECK`，`verified_checks` 不再计算它。这不是程序出 bug，而是我们终于拥有了一个**可以撤销过期信任的进度系统**。

想象一个反面设计：某个 Web 面板把所有曾经通过的测试永久记作绿色。Codex 可以先跑通所有测试，然后再改代码，面板依然说 100%。这恰恰是我们最初开发 Watchdog 要避免的问题。

这里的回退不会自动重新执行测试。恢复 `PASSED` 需要再次明确运行已批准的验收命令，并且取得针对当前文件快照的结果。

## 九、实验 D：未经批准的合同修改必须让进度失效

为了保护正式状态，只在隔离演示中进行以下反例实验：人为修改监督器保存的 `task_contract.json` 中的目标或验收内容，但**不要**调用 `approve`。此时 `progress.py` 应返回 `UNTRUSTED_CONTRACT`，不继续宣布里程碑 `VERIFIED`。

这很重要。未来如果 Codex 想利用“更新任务列表”掩盖失败项，我们必须让监督者保留原始的、经过人类批准的目标。否则它就没有真正独立的监督意义。

## 十、我们还没有实现什么？

**第一，不是自然语言的完整任务拆解。** 当前里程碑由人类批准的合同定义，程序只能忠实地汇总配置好的验收项。

**第二，不是自动推断每条工具调用属于哪个子任务。** 同一次 Bash 可能为多个验收项服务，仅凭“使用 Bash”无法知道它属于 M1 还是 M2。需要额外的语义上下文、人工标签或经过验证的模型辅助。

**第三，不能用里程碑数量衡量开发效率。** 两个里程碑完成不等于比一个复杂里程碑多完成一倍的工作。

**第四，未覆盖的目标不能被自动验收。** 例如“界面体验自然”“服务上线后可稳定使用”，如果合同只有两个 `unittest` 命令，那么两个测试通过也不能证明这些额外要求已经实现。

这四点不是这章的缺陷说明书，而是我们设计下一轮智能进度关联时必须严肃面对的限制。

## 十一、故障排查、练习与验收

| 现象 | 优先检查 | 不要做什么 |
|---|---|---|
| `NO_CONTRACT` | 是否执行过 `init` | 编造默认用户目标 |
| `UNTRUSTED_CONTRACT` | 批准摘要是否与现有合同一致 | 自动重新 `approve` |
| `STALE` | Git 快照是否在验收后改变 | 把旧 PASSED 硬改为通过 |
| `FAILED` | 测试退出码与测试覆盖范围 | 用 Agent 自述覆盖结果 |
| 进度没有变化 | 是否真正执行了对应验收项 | 按 Hook 数量增加进度 |
| 报“未知验收 ID” | 里程碑引用是否存在于合同 | 静默创建虚构 A3 |

读者练习：如果 M1 包含 A1=PASSED 与 A2=STALE，M1 应当是什么状态？如果合同中 A1、A2 都 PASSED，但保护文件被修改，为什么总任务不应 `VERIFIED_COMPLETE`？如果 Agent 用非常流畅的自然语言说“全部工作完成”，是否会改变这份报告？

本篇完成后，Watchdog 终于有了基于**人工批准的目标与当前可复核证据**生成的进度报告。它仍然不等于通用的自然语言项目理解器，但比纯事件计数可靠得多。

下一篇，我们继续处理另一个更符合你最初需求的问题：Codex 可能一边完成正确的验收项，一边擅自修改无关模块。怎样让系统区分“可确认的受保护文件变化”和“需要人审的任务范围扩大”？

参考：[任务合同源码](examples/v04/watchdog/task_contract.py) · [进度模块](examples/v04/watchdog/progress.py) · [自动化测试](examples/v04/tests/test_next.py) · [Git 官方文档](https://git-scm.com/docs/git-ls-files)。
