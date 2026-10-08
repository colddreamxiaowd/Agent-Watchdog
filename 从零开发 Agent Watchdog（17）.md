# 从零开发 Agent Watchdog（17）：让异常监督先拿出证据——从重复操作到可解释风险

系列教程 · 第 17 篇｜Windows 11 · Python · Git · SQLite · 可解释规则

> **本篇定位**：我们仍在开发自己的 Agent 独立监督器，不是在训练一篇新的 Stuck Detector 论文。第 16 篇能检查文件范围，但还不能回答“什么情况该提醒我”。本篇将这种能力整理成**有证据、有解释、不会擅自行动**的监督报告。本文提供的代码属于教学参考实现，所有示例的“通过”均不等于你电脑上的真实 Codex 已被验证。

## 一、先判断一个看起来很吓人的场景

假设你把一个 Python 项目交给 Codex。打开 Watchdog，看到了下面六条事件：

```text
19:00:01  PostToolUse   Bash
19:00:03  PostToolUse   Bash
19:00:07  PostToolUse   Bash
19:00:11  PostToolUse   Bash
19:00:16  PostToolUse   Bash
19:00:22  PostToolUse   Bash
```

你的第一反应也许是：“六次 Bash？Codex 是不是又卡住了？”但换一种情况：它依次运行了 `git status`、三个单元测试、`python -m compileall` 和 `git diff`。六次 Bash 恰好是一次合理的修复流程。

再换一种情况：它六次执行的是同一个失败命令，且每次得到同样的报错。这时才更接近我们希望识别的无效循环。

**问题在于：目前安全日志里只有工具类别，不包含命令正文和退出码。** 两种情况在日志上可能完全一样。模型不能替我们凭空补出缺失的事实。因此，本篇先做出严格的区分：

- **事实（Fact）**：已批准的验收 A1 状态为 `FAILED`；Git 可见的 `GOAL.md` 与保存的基线不同。可以指向检查方式。
- **启发式信号（Heuristic）**：同一会话的最近六条脱敏事件工具类别相同。只能提示“值得回看”，不是“已经死循环”。
- **无法判断（Unknown）**：是否连续运行了同一条命令、是否尝试不同修复方案、Agent 当前是否仍在思考，以及自然语言目标有没有偏离。

你真正需要的 Watchdog，不是做一个红得吓人的“风险 97%”按钮，而是说清楚：“**我观察到了什么、怎么知道的、还不知道什么、建议你做什么。**”

## 二、接续第 16 篇：我们已经拥有哪些事实来源？

前面的章节并不是白做。第 03–04 篇的 `evidence.py` 和 `bridge.py` 可以读取 Git 变更与测试证据；第 05–06 篇的 `task_contract.py` 锁定人类批准的任务要求；第 09 篇的 `journal.py` 把脱敏事件存进 SQLite；第 15–16 篇的 `progress.py` 和 `scope_guard.py` 分别计算逐项验收覆盖情况和文件路径范围提示。

```text
                       原始任务契约
                       (用户批准)
                            │
       ┌────────────────────┼──────────────────────┐
       │                    │                      │
       ▼                    ▼                      ▼
  Acceptance            Git 变更              脱敏事件账本
  PASSED/STALE          路径越界               session/tool
       │                    │                      │
       └────────────────────┼──────────────────────┘
                            ▼
                  supervision.py
                   /          \
               facts        hypotheses
                 │              │
                 └──────┬───────┘
                        ▼
                  给用户可解释提醒
                  不自动 kill/retry
```

为何把事实和猜测分成两个列表？因为它们以后要走不同的处理流程。对于受保护文件变更，我们需要检查差异；对于疑似重复工具，我们应先查看上下文。把两者混在一个总分里，会使用户不知道先做什么。

## 三、先把“证据等级”设计清楚

为了不让提示显得神神叨叨，我们先不使用虚构的概率。一个提醒可以是：

```json
{
  "code": "ACCEPTANCE_STALE",
  "severity": "medium",
  "evidence": {"id": "A1", "status": "STALE"},
  "next_step": "人工检查并显式运行已批准的验收项"
}
```

为什么这个结构比单纯 `risk_score=0.8` 有用？第一，`code` 让程序能稳定做筛选；第二，`evidence` 表明结论来自哪里；第三，`next_step` 给出可执行动作，而不是要求你相信模型；第四，它没有在 JSON 中假装“80% 概率失败”。

再看一条启发式提示：

```json
{
  "code": "POSSIBLE_REPETITION",
  "severity": "low",
  "kind": "heuristic",
  "confidence": "NOT_CALIBRATED",
  "evidence": {
    "tool_category": "Bash",
    "count": 6,
    "session_id": "demo-17",
    "source": "codex_hook"
  },
  "next_step": "查看允许查阅的执行上下文；不能据此认定死循环"
}
```

注意 `NOT_CALIBRATED`：我们没有真实人工标注的 Codex 轨迹和误报统计，就不能把阈值六当作“科学验证的最佳检测阈值”。它只是可复现、可修改的演示阈值。

## 四、本篇新增文件：supervision.py

延续之前的目录，不覆盖旧版 `risk.py`：

```text
D:\program\agent_watchdog\watchdog\
├── evidence.py
├── task_contract.py
├── journal.py
├── scope_guard.py
├── risk.py                 # 第 07/11 篇保留
└── supervision.py          # 本篇新增
```

完整源码：[examples/v04/watchdog/supervision.py](examples/v04/watchdog/supervision.py)。以下只提取关键机制。其余导入、CLI 和错误处理均在同一个完整文件内。

### 关键设计一：只读取已存在的事件数据库

```python
if not Path(db).is_file():
    return []

with sqlite3.connect(str(db), timeout=2) as con:
    rows = con.execute(
        "SELECT payload FROM events ORDER BY rowid DESC LIMIT ?",
        (max(1, min(int(limit), 500)),),
    ).fetchall()
```

前面 `journal.connect()` 是写入侧接口，会在缺少数据库时创建它。监督器只是查询历史，**不应该因为打开面板，就悄悄创建一个空数据库再宣称监控正常**。所以这里先判断存在性，然后用 SQLite 原生只读取数。上限 500 条防止界面误调用时无限制抓取。

### 关键设计二：先处理独立证据，再处理弱信号

```python
contract = task_contract.acceptance_status(repo)
for name, status in contract["acceptance"].items():
    if status in ("STALE", "FAILED", "INCONCLUSIVE"):
        facts.append({
            "code": "ACCEPTANCE_" + status,
            "severity": "medium",
            "evidence": {"id": name, "status": status},
            "next_step": "人工检查并显式运行已批准的验收项",
        })
```

注意 `NOT_TESTED` 不等于通过：它在逐项状态里仍然是未测试，但为了避免刷屏，本示例只把明确失败、过期、运行期间发生变更放入显式事实告警。读者不能据此推出“没有事实告警，所有验收都已通过”。最终是否完成仍必须看 `task_contract.acceptance_status()` 的完整状态。

### 关键设计三：不同会话绝不混算

```python
last = rows[-6:]
if (
    len(last) == 6
    and all(x.get("tool") and x.get("session_id") and x.get("source") for x in last)
    and len({(x.get("session_id"), x.get("source"), x.get("tool")) for x in last}) == 1
):
    # 仅产生 POSSIBLE_REPETITION 弱提示
    ...
```

假设你同时监控三个 Codex，每个都调用两次 Bash。如果把所有日志直接计数成“六次连续 Bash”，就产生了非常典型的跨会话误报。因此规则要求六条事件具有完全相同的 `session_id`、`source` 和 `tool`。

但即使三者都一样，依然**不能证明**命令内容一样、更不能证明失败。这里设计得刻意保守，因为以后接入 StepWise、结构化工具 outcome 或人工标注时，我们需要能够解释新增模型和当前规则到底提供了哪些新信息。

## 五、实验 A：什么都还没有发生，能显示“低风险”吗？

先从 GitHub 下载/更新本轮 `examples/v04/watchdog/supervision.py`，不要直接复制过去覆盖整个旧 `watchdog` 文件夹。

打开 **Anaconda Prompt（cmd，不是 PowerShell）**：

```bat
conda activate torch_env
cd /d D:\program\agent_watchdog\watchdog
python supervision.py --repo "D:\program\agent_watchdog\hook_demo"
```

如果你尚未建立任务契约，`state` 可能出现 `UNKNOWN`。如果没导入日志，最近事件数可能是 0。这是正常的“没有可用证据”。不应该出现“Agent 一切正常”或“真实 Codex 接入成功”的断言。

练习：假设数据库不存在。读取时是应该报错停止、创建一份空数据、还是返回空事件并明确限制？本项目选择第三种，但仍让第 19 篇的运行状况诊断把缺失数据库当成需要处理的事实。

## 六、实验 B：六条相同类别的工具调用

本实验不要写入你的真实 Codex 日志。先从源码包的测试文件理解它：

```python
rows = [
    {"session_id": "demo-17", "source": "codex_hook", "tool": "Bash"}
    for _ in range(6)
]
result = supervision.diagnose(repo, events=rows)
```

预期在 `hypotheses` 中出现 `POSSIBLE_REPETITION`，而不会出现“confirmed stuck”。我们还可以进行一个更有教育意义的反例：

```python
rows = [
    {"session_id": str(i % 2), "source": "codex_hook", "tool": "Bash"}
    for i in range(6)
]
```

这时不应触发“同一会话重复类别”的规则。这种测试意义很大——监督器最容易在**多 Agent / 多会话**环境中把不同对象的证据拼成一个看似惊人的风险结论。

你可以直接运行本轮的自动化测试，不需要手工复制模拟数据：

```bat
cd /d D:\program\agent_watchdog
python -m unittest discover -s examples\v04\tests -v
```

上述命令的前提是你已经把 GitHub 仓库克隆或解压到 `D:\program\agent_watchdog`。如果你只复制了 `.py` 文件，则应改成对应的真实目录。运行时**不会启动真实 Codex**，测试使用临时 Git 仓库。

## 七、实验 C：受保护文件变了，为什么不能说“Codex 违规”？

第 16 篇已经提醒过：Git 快照只能发现内容差异，不能确认修改者是谁。即便发现 `GOAL.md` 变了，也可能是你自己编辑的。因此本篇的事实仅表述为 `PROTECTED_CHANGE`（保护文件发生变化），并要求人工核对修改来源和授权情况。

为了复现这一场景，可以在**隔离测试仓库**里：先保存 Git 基线，再修改 `GOAL.md`，再调用 `supervision.py`。结果应该有路径证据，但不会包含未经验证的“Codex 修改了它”的归因。

进一步的问题：如果用户原来授权“仅修改 src/**”，Agent 在 `docs/` 下加了说明文档，这是任务偏离还是合理的辅助结果？仅靠路径规则无法得到普适答案。第 16 篇的 `OUTSIDE_DECLARED_PATH_SCOPE` 仍然只代表“需要复核”。

## 八、什么时候才值得引入小模型？

你曾经成功在 RTX 5060 8GB 上加载 StepWise 的 Stuck Detector。但当时的手工 Coding Agent 测试即使对明显重复示例，也输出了 `NOT_STUCK≈1`。这不能断定模型坏了，却足以提醒我们：**不能在不核对轨迹输入分布、标签定义和错误代价之前，把模型接进正式告警。**

今后如果引入模型，至少要有真实、经过许可且脱敏的 Codex 轨迹；带有人工定义的“无进展/重复失败”标签；按会话或项目隔离的数据划分；误报、漏报和告警延迟指标；以及一条“关闭模型后仍能使用确定性监督器”的降级通道。模型输出只能加入 hypotheses，不得静默覆盖验收事实。

第 17 篇故意不直接加 StepWise API 调用，这是工程上的有意识延后，不是放弃智能监督目标。

## 九、出现问题时，应该查哪里？

| 看到的现象 | 可能的原因 | 更合理的检查 |
|---|---|---|
| 六条 Bash 没有提示 | `source` 或 `session_id` 缺失；或跨多个会话 | 检查脱敏事件字段和实际窗口 |
| 测试明明执行过却显示 STALE | 文件快照发生变化 | 查看第 06/15 篇的证据指纹策略 |
| 明明没有错误却没有“正常”标签 | 系统不会用没有触发的规则证明正常 | 查看完整合同状态，不要只看告警 |
| 运行时提示 Git 仓库不可用 | `--repo` 指错路径 | `git -C "路径" rev-parse --show-toplevel` |
| 想知道是否真的死循环 | 现有日志没有足够数据 | 在有授权前提下扩展工具 outcome/人工审查 |

安全提醒：不要为了“让智能识别更准”，直接把完整终端输出、私人提示词或 API Key 写入 GitHub 或公开训练数据。

## 十、本篇如何验收？

- [ ] 看到代码将 `facts` 和 `hypotheses` 分开，而不是混成一个神秘总分。
- [ ] 同一会话同类工具六次时，只会产生低可信度提示，不会宣布死循环。
- [ ] 不同会话的六次工具调用**不会**被错误拼成同一个循环。
- [ ] 测试证据 `STALE` 可以触发事实提示，但系统不会自动运行 pytest。
- [ ] 受保护文件的变更只记录路径，不断言修改者身份。
- [ ] 本机真实 Codex 轨迹尚未验证时，不把模拟事件当成生产结论。

**小结**：你现在有了一个懂得自己证据边界的监督器。它未必说得多，却开始值得信任。下一篇要解决的是：这些事实怎样让你在一个网页里随时查看，而不必盯着多个终端窗口？

### 参考与源码

- [本篇完整源码：supervision.py](examples/v04/watchdog/supervision.py)
- [第 16 篇范围检查](从零开发%20Agent%20Watchdog（16）.md)
- [Python sqlite3](https://docs.python.org/3/library/sqlite3.html)
- [StepWise 开源仓库](https://github.com/yale-nlp/StepWise)

> **当前验证边界**：本篇的规则有隔离自动化测试，但不代表已在你的 Windows + 真实 Codex 轨迹上测出可泛化的检测效果。
