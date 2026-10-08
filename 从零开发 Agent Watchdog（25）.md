# 从零开发 Agent Watchdog（25）：连续失败也不一定在死循环——把“失败聚集”变成可复核证据

> 第 25 篇 · Agent Watchdog V2 第二轮｜Python · 脱敏事件 · 失败序列 · Windows 11  
> 研究与工程状态：**规则源码及合成测试可验证；尚无经过独立标注的真实 Codex 轨迹效果证明。**

## 一、回到你最初想解决的实际痛点

你把一个修复 Bug 的任务交给 Codex，它反复执行命令，终端看上去像在原地打转。你希望独立监督器主动提醒：“这条路线可能不奏效，建议检查测试报错。”第 23 篇已经能在有明确数值失败结果时输出 `FAILED` 或 `FAILURE_CLUSTER_REVIEW`。问题是：**重复失败不一定是无效循环；反过来，真正无效循环也可能没有非零退出码。**

想象 Codex 按顺序运行三个测试：

```text
Bash: 测试数据库连接 → FAILED
Bash: 测试 token 校验  → FAILED
Bash: 测试登录重定向 → FAILED
```

它们同属于 Bash，而且失败了三次，但分别发现三个缺陷，不该被指控为死循环。再想象另一种情况，Codex 连续三次执行同一条测试，三次都失败，中间没有代码改变。两段轨迹在第 21–22 篇的**默认脱敏字段**里可能长得一模一样：三个不同 `tool_use_id`，工具类别 Bash，结果 FAILED。

这不是用更复杂的 `if` 就能解决的问题。这是“数据里没有足够信息”的问题。如果你从未批准 Watchdog 保留命令本身，我们不能在输出里假装知道三次执行的命令是否相同。

本篇因此不做“自动证明死循环”这个不可能的承诺，而是建立一个有证据分级的**失败尝试审查器**。

## 二、到底哪些事实能从当前事件中拿到？

第 22 篇建立了共同格式。一个只读且脱敏的终态事件示例如下：

```json
{
  "source": "fixture_only",
  "session_id": "synthetic-session",
  "turn_id": "synthetic-turn",
  "tool_use_id": "call-003",
  "tool": "Bash",
  "phase": "FINISHED",
  "outcome": "FAILED",
  "linkable": true
}
```

这里仅能确认：**这份未经认证的测试事件记录声称有一项调用失败**。不能确认命令文本、失败原因、是否有新的代码变更，更不能知道用户任务是否正确推进。真实 Hook 字段还可能缺失，这时 `outcome=UNKNOWN` 才是正确答案。

新的 [failure_review_v25.py](examples/v04/watchdog/failure_review_v25.py) 坚持三个条件：必须是具有稳定调用 ID 的终态；必须记录明确 `FAILED` 才纳入失败计数；来源和会话必须严格分开。同一 `tool_use_id` 重复收到终态不能算两次失败，而互相矛盾的终态需要单独隔离。

可以把它想成一个医院分诊台：先确认是同一个人、这份检查报告确实写着异常，再通知医生复核；它不会仅凭三次检查都是血常规，就判断医生在做没有意义的治疗。

## 三、先复用现有能力，不重新发明数据采集器

这次我们没有更改 `hook_runner_v21.cmd`，也没有重写 `journal.py`。第 25 篇的输入直接来自 `execution_v2.read_projected()`，也就是第 22 篇保留下来的安全字段。你已经理解的仓库结构没有变：

```text
examples/v04/watchdog/
├── execution_v2.py           # 第22篇：字段来源与结果
├── runtime_v2.py             # 第23篇：运行状态
├── step_links_v2.py          # 第24篇：步骤与事件人工关联
├── failure_review_v25.py     # 本篇：失败序列的可解释复核
└── failure_groups.example.json
examples/v04/tests/
└── test_round2.py            # 本轮正反例
```

核心投影函数只看完成事件：

```python
if row.get("phase") != "FINISHED":
    continue
key = (
    row["source"],
    row["session_id"],
    row.get("turn_id"),
    row["tool_use_id"],
)
```

这个键说明“何为同一次调用”。千万别删掉 `session_id`，因为两个会话各自的第一次 Bash 很可能都叫 `call-1`。如果只按工具名称 `Bash` 聚合，两个互不相干的项目就会互相污染。

不同操作的失败结果合起来，才允许给出：

```text
FAILURE_CLUSTER_REVIEW
distinct_failed_calls: 3
confidence: NOT_CALIBRATED
interpretation: NOT_SAME_COMMAND_OR_NO_PROGRESS_PROOF
```

这里每一行都需要读懂。`distinct_failed_calls` 是不同调用身份的数量，不是不同命令数量。`NOT_CALIBRATED` 表明我们没有测得真实误报率，不能说“高置信度”。最后一行明确拒绝把失败聚集升级为同命令、无进展或真正卡死的事实。

## 四、怎样进一步调查“重复尝试同一种修复”？

真正有帮助的记录还需要知道：这些失败是否属于**同一个人类理解的尝试意图**。有两种做法：默认保存命令或输出，或经授权由用户/审核者标注。前者有明显的隐私代价；命令可能包含密钥、私人目录、研究工作。我们在第一个版本选择后者。

[人工映射示例](examples/v04/watchdog/failure_groups.example.json) 中，审核者只输入精确的 `source / session_id / turn_id / tool_use_id`，把两个操作归入同一个 `groups[].id`。**不输入命令正文，不放入公开仓库中的真实会话 ID。**

```json
{
  "schema_version": 1,
  "groups": [{
    "id": "review-A",
    "calls": [
      {"source":"fixture_only","session_id":"s","turn_id":"t","tool_use_id":"1"},
      {"source":"fixture_only","session_id":"s","turn_id":"t","tool_use_id":"2"}
    ]
  }]
}
```

如果两次同意图尝试先失败后成功，报告会标 `POSSIBLE_RECOVERY`。这是一个很重要的负面例子：Agent 可能通过修改代码有效解决问题，“失败后成功”不应继续被当作纯粹的无效循环。即便人工归组仍可能有误，结果也不会称为 `VERIFIED_LOOP`。

而且脚本遇到以下输入会拒绝：找不到的调用标识、跨来源、跨会话、重复把同一调用放进两个组。为什么拒绝而不是“尽力匹配”？因为本项目做监督，不是做聊天摘要；错误的审计归因比少一条提醒更危险。

## 五、Windows 动手实验：先测代码，再看你的真实日志

在 **Anaconda Prompt（CMD）** 中使用本轮分支的新克隆；不要覆盖旧的 `D:\program\agent_watchdog\watchdog`：

```bat
conda activate torch_env
cd /d D:\program\agent_watchdog\Agent-Watchdog-v2-round2-eval
python -m unittest discover -s examples\v04\tests -p test_round2.py -v
```

第一次实验不需要启动 Codex，不需要 StepWise，也不需要网络服务。它的事件是脚本构造的 `fixture_only`，所以正确结论只能是“这些逻辑在模拟场景下符合预期”。

若第 21 篇已经接通你**真实、私有且脱敏的** `events.jsonl`：

```bat
cd examples\v04\watchdog
python failure_review_v25.py --events logs\events.jsonl --min-failures 3
```

命令不会运行 Agent 工具，也不会自动改文件。结果包含 `calls`、`unknown_outcomes`、`conflicts`、`signals`。如果缺少可关联工具结果，`calls=0` 是可能且诚实的结果，不应为了让界面看起来繁忙而填上虚构失败。

确实要复核同一意图时，先从**私有、已获许可的资料**人工确认调用关系，写在仓库外的 `D:\private\failure_groups.json`，再加：

```bat
python failure_review_v25.py --events logs\events.jsonl --manual-groups "D:\private\failure_groups.json"
```

这些私人记录不要提交到 GitHub，也不要发到公开 Issue。

## 六、一定要做的四个反例

**反例 A：六次 Bash 全成功。** 六次都是同一种工具，但各自的 `outcome=SUCCEEDED`。预期没有失败聚集提示；它们可能代表高效率推进，而不是异常。

**反例 B：两个会话各两次失败。** 设门槛为三次，不能把两组失败合并成四次然后触发全局告警。这是最容易在真实多会话使用中出现的假阳性来源。

**反例 C：同一个调用被导入两次。** JSONL 重新导入、日志重放都可能导致重复事件。依照调用身份去重后，失败次数不能增加；同一调用同时报告 FAILED 与 SUCCEEDED，应生成 `CONFLICTING_TERMINAL`，而非“选择最后一条”。

**反例 D：三次不同调用全部失败，但命令并不相同。** 这时候允许出现 `FAILURE_CLUSTER_REVIEW`，但不得出现“确认是同命令死循环”。该反例会迫使我们把**可复核的弱提示**和**强制事实结论**分开。

上述测试都在 [test_round2.py](examples/v04/tests/test_round2.py) 有独立断言。第 25 篇只有在这些反例可以稳定通过的前提下，才有资格作为可运行参考工程交付。

## 七、我们为什么暂时不直接让 StepWise 裁决？

你以前运行过 StepWise 的 ModernBERT 模型，但 StepWise 官方框架主要针对 GUI Agent 的动作/解释窗口和任务里程碑。现有 Watchdog 默认收集的只有脱敏元数据，两者输入不一致。直接把一段 `Bash Bash Bash` 送进原有模型，即使模型产生概率，也不能当作论文意义上的 Stuck 预测。

另外模型如果不具备“第三次失败后具体变了什么”的信息，精细分类也可能无从做起。与其在用户私人轨迹上急着训练，不如先把标签定义、能观察什么以及哪些输出永远是 UNKNOWN 写清楚。

## 八、本篇的完成标准与下一章

已经完成的是：可运行的失败聚集审查接口、稳定操作身份隔离、冲突与重放反例、可选人工同意图映射，以及对误报的工程性约束。

没有完成的是：在你真实 Codex 长任务上的**精确率、召回率、无效循环识别率**。G1、G3 仍等待真实数据和人工标注。没有授权的命令正文不会被偷偷采集，模型也不会自动杀掉、重试或接管 Agent。

下一篇将正面回答：“既然有一个 ModernBERT Stuck Monitor，可以用它让 Watchdog 变得更聪明吗？”我们不会靠演示分数回答，而是先让两个检测方案在同一批样本、同一目标上公平比较。

源码：[failure_review_v25.py](examples/v04/watchdog/failure_review_v25.py) · [验证工作单](docs/ROUND2_WINDOWS_RUNBOOK.md) · [真实评价门槛](docs/ROUND2_EVIDENCE_PROTOCOL.md)。
