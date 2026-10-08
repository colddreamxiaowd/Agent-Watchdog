# 从零开发 Agent Watchdog（24）：把 Codex 的操作关联到任务步骤，但绝不让“做过”冒充“做成”

> 系列教程 · 第 24 篇｜Task Contract · 会话与回合关联 · event_id · 独立验收  
> **本篇核心：事件关系是线索，验收状态必须来自用户批准的独立证据。**

## 一、Codex 改了十个文件，任务就完成了十成吗？

你让 Agent 完成一项明确任务：“修复登录接口；不能改动数据库迁移；所有约定测试必须通过。”它在 Git 中新增了十几个文件，运行了二十次 Bash，最后说：

> 已经完成啦，所有测试通过！

若 Watchdog 只根据事件数量或文件数量算进度，就会出现荒谬结果：文件改得越多，完成率越高；一次失败后的反复重试，甚至让数字不断上涨。更严重的是 Agent 可能先测试通过，然后又修改代码，此时旧结果其实已经过期。

我们的工程在第 05–06 篇已经埋下正确的基础：`task_contract.py` 要求人类批准任务合同，`acceptance` 列出允许运行的验证命令。第 15 篇的 `progress.py` 把验收项映射成里程碑，而不是从工具调用次数计算一个假进度。

但是缺了关键的一环：**每一步到底能用哪些可追溯的观察记录帮助解释？**

## 二、先把三种不同层级的“证据”分开

假设 Codex 正在处理 `A1: 修复 add() 函数`：

```text
用户批准的 Task Contract
    └─ A1: 对 add() 的测试应通过
          │
          ├─ 执行线索：session=S / turn=T / call=K
          │      └─ Bash 发生过、报告过退出码
          │
          ├─ 文件证据：Git 中 add.py 的指纹改变
          │      └─ 证明变更存在，不证明谁改的
          │
          └─ 独立验收：用户授权运行 A1 的测试
                 └─ PASSED / FAILED / STALE / INCONCLUSIVE
```

这三层不能画成一个“Bash 成功 -> A1 完成”的箭头。调用记录只是执行轨迹线索，Git 是文件状态，真正对应用户验收标准的，是第 06 篇保留下来的 `acceptance_results.json` 与当前快照。

你可以人工判断“这个 Bash 大概率是 Codex 在调试 A1”，但它仍然只是一个**人工关联**，不能越权修改 `task_contract.py` 的验收状态。

## 三、为什么需要 event_id，而不是只存一串自然语言？

记录中带着 `session_id`、`turn_id`、`tool_use_id` 时，我们可以根据这些字段与事件阶段生成 `event_id`。它是脱敏记录的稳定引用，方便检索和建立关系。

例如：

```json
{
  "source": "hook_input_unverified",
  "session_id": "session-demo",
  "turn_id": "turn-demo",
  "tool_use_id": "call-demo",
  "phase": "FINISHED",
  "outcome": "UNKNOWN",
  "event_id": "由程序生成的固定长度引用"
}
```

这里有一个容易忽略的区别：**哈希不等于签名**。知道算法的人可以构造另一份事件来得到某个自己的哈希；日志的本地操作者也可以修改它。因此 `event_id` 只是查找引用，不负责确认是不是 Codex 真正发来的。G1 的真实接入验收必须单独完成。

如果缺少稳定 `tool_use_id`，脚本的 `linkable` 会是 `false`；我们拒绝按“差不多同一时间的 Bash”自动配对。主动承认不清楚，远比错误地关联进度可靠。

## 四、我们没有重写你已批准的 Task Contract

请打开旧 [task_contract.py](examples/v04/watchdog/task_contract.py)。你会看到四条最关键的事实：

1. `contract_hash()` 把批准过的合同固定成 SHA-256。
2. `load()` 核查当前合同内容是否仍与已批准摘要一致。
3. `run_one()` 只运行该合同中列出的命令，要求人**显式发起**；Hook 不自动跑测试。
4. `acceptance_status()` 会比较测试前、测试后、当前 Git 可见快照。改动后旧通过结果会变成 `STALE`。

这些能力是我们应该复用的，没必要为了新章节重新写一个“超级智能任务调度器”。

本篇新增 [step_links_v2.py](examples/v04/watchdog/step_links_v2.py)，只负责**读取**已经批准的合同、已脱敏的事件及人工写好的绑定文件。它不运行任何测试、不覆盖合同、不编辑项目源码。

## 五、人工关联文件该怎么写？

我们把 `links.json` 放在被监控仓库外的私人目录，格式很简单：

```json
{
  "schema_version": 1,
  "contract_sha256": "这里填当前被批准的合同 SHA256",
  "links": [
    {
      "step_id": "A1",
      "event_id": "这里填已核对的脱敏 event_id",
      "acceptance_id": "A1"
    }
  ]
}
```

程序会检查合同哈希仍匹配当前批准版本、`step_id` 存在、`acceptance_id` 存在，以及 `event_id` 能否在给定的脱敏事件流里找到、该事件是否具备稳定调用标识。

一条合法关系最终只会得到：

```text
association: LINKED_MANUALLY
acceptance_status: PASSED | FAILED | STALE | INCONCLUSIVE | NOT_TESTED
meaning: Event association is not proof of task completion
```

如果指定的事件根本不在当前文件里，`association=UNLINKED`。它不会“为了方便”给用户补上一条伪造的工具记录。`acceptance_id` 省略时只说明没有绑定独立验收，而不是显示 `PASSED`。

## 六、Windows 实战：先理解前置条件

本章接续第 21 篇的独立 Git 练习仓库。你应已经在这个仓库中用旧 `task_contract.py init`、`approve` 创建了经审核的任务合同；还用 `execution_v2.py` 生成了脱敏 `events.jsonl`。如果没有这些输入，应该先停留在 `NOT_TESTED/UNLINKED`，而不是跳过安全门。

参考合同可从仓库 [task_contract.example.json](examples/v04/watchdog/task_contract.example.json) 复制到私人目录，在不覆盖已存在文件的情况下编辑成自己的练习项目、审核指定测试命令，再运行：

```bat
cd /d D:\program\agent_watchdog\Agent-Watchdog-v2-eval\examples\v04\watchdog
python task_contract.py --repo "D:\program\agent_watchdog\hook_demo_v2" init --contract "D:\private\demo_contract.json"
python task_contract.py --repo "D:\program\agent_watchdog\hook_demo_v2" approve
python task_contract.py --repo "D:\program\agent_watchdog\hook_demo_v2" status
```

`approve` 是明确的人类决策，不是让 Agent 默默自动批准自己制定的测试。若你此前已经有合同，不应再次执行 `init`，先读现有合同与批准信息。

将批准状态输出中的 `contract_sha256`、脱敏日志里相应的 `event_id` 填入你自己的 `D:\private\links.json`（目录自行选择，勿放在被监控仓库）。然后执行：

```bat
python step_links_v2.py --repo "D:\program\agent_watchdog\hook_demo_v2" --events "logs\events.jsonl" --links "D:\private\links.json"
```

成功运行后你会看到合同阶段、人工绑定的事件类型、会话/回合、是否有对应验收项。它不把工具输出正文暴露出来，也不会通过绑定操作修改 `acceptance_results.json`。

## 七、这一章最关键的正常与反例实验

**正常实验：** 在有批准合同的前提下，你人为绑定一条确实存在的脱敏事件；它显示 `LINKED_MANUALLY`。若 A1 的独立测试在当前快照上通过，则 `acceptance_status=PASSED`。这里的 PASSED 是**之前真正执行过那个已批准的测试**的结果，不是本章凭空产生。

**反例 1（证据过期）：** 测试通过后修改 `add.py`，再运行关联程序。`LINKED_MANUALLY` 可以保持不变，因为事件关系仍存在；但旧测试的状态应是 `STALE`。这正是我们想守住的边界：**操作历史不会抹掉验收过期事实**。

**反例 2（错误事件 ID）：** 把 `event_id` 改为不存在的值，必须显示 `UNLINKED`，不能就近匹配另一个操作。

**反例 3（合同被偷换）：** 修改并重新保存合同，但仍使用旧 `contract_sha256` 的绑定记录。程序应拒绝这个关联；不能把不同任务的证据账本拼起来。

**反例 4（未经批准）：** 有 `task_contract.json` 却没执行人工 `approve`。程序直接拒绝作为权威合同；一个 Agent 自己编造的步骤 ID 不能进入验收。

**反例 5（多会话）：** 两个不同会话各执行一次 Bash。`event_id` 不应自动指向另一个会话，即使 `tool` 完全相同。

这些场景已纳入 [test_round1.py](examples/v04/tests/test_round1.py)，可以在 Windows 托管 Runner 与 Linux 上运行；但你电脑上的真实验收仍要按 G1 工作单另外保留。

## 八、我们离真正的“自动追踪任务进度”还有什么距离？

本篇只能建立**结构化、可被人工复核的关联层**。它不能自动理解 Codex 的每一步自然语言思考；没有可信的原始计划文本和授权上下文，也不能推断某次 `Bash` 就是为了 A1；它更不能测定任意需求的真实完成百分比。

对于跨仓库修改、浏览器交互、外部服务状态等非 Git 结果，单靠本章的文件快照仍然不够。第 28 篇应当建立独立于测试的产物、浏览器/API 等验收来源，并记录证明范围、有效期、谁审核过。第 27 篇再讨论自然语言目标偏离，不能把这个关联层冒充语义裁判。

本轮我们保留一个重要优点：没有引入新 GPU 模型，没有侵入 Codex 内部数据库，不要求安装另一个大型服务。代码在用户已有的 `task_contract.py`、`progress.py`、`evidence.py`、`journal.py` 上增量生长。

## 九、四章之后的现实进度

| 本轮可交付 | 仍需人工/真实环境 |
|---|---|
| 受控 Hook 配置与本机诊断代码 | 用户 Windows 上真实 Codex G1 |
| 三来源显式脱敏适配与 `UNKNOWN` 结果 | 对用户使用的 Codex 版本核对字段覆盖 |
| 有区分度的保守故障信号 | 真案例 G3 的误报、漏报与不可判定统计 |
| 合同哈希、会话与步骤的人工关联 | 自动语义进度与更广的独立验收 |
| Linux/Windows CI 与发布候选门槛 | 休眠、轮转、长期恢复、原生提醒 G4 |

**第 24 篇验收标准**：有效绑定能说明来源、会话、事件与验收状态；无事件时 `UNLINKED`；未批准合同或摘要不匹配必须拒绝；`STALE` 不因绑定而转成 `PASSED`；所有记录仅在受信任的私人环境读取。至此完成一轮有边界的工程增量，**不是原始 Agent Watchdog 产品完成**。

下一轮第 25–28 篇的任务将更接近你的真正理想：在已获授权、确实包含结果的执行轨迹上区分重复失败与有效调试，评估 StepWise 是否有增益，尝试有人工可复核证据的目标偏离提醒，并支持非测试类验收。前提仍是：真实来源、结果和用户批准合同要先有证据。

详见 [Windows E2E Runbook](docs/REAL_CODEX_E2E_RUNBOOK.md) · [Product Requirements v2](docs/PRODUCT_REQUIREMENTS_V2.md) · [step_links_v2.py](examples/v04/watchdog/step_links_v2.py)。

