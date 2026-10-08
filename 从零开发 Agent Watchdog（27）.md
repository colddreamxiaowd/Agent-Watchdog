# 从零开发 Agent Watchdog（27）：AI 可能很忙却忙错方向——如何审查任务目标偏离而不冤枉 Codex

> 第 27 篇 · 原始任务锚定 · Git 范围事实 · AI 候选建议 · 人工复核  
> 本篇是**审查线索管理**，不是已经训练好且验证准确的“语义越权检测器”。

## 一、一个比“工具失败”更麻烦的实际场景

你让 Codex 只修复 `login.py` 的一个参数错误，明确要求不要改数据库。它认真阅读代码、运行测试，终端没有异常，最后告诉你：“问题修好了！”但回头检查 Git，发现它还修改了 `schema.sql`、`GOAL.md`，甚至顺手重构了整个认证模块。

这种情况只看工具退出码完全发现不了。三十次工具调用都成功，也可能偏离目标。第 16 篇已经实现过 `scope_guard.py`：基于用户批准的 `protected_paths`、`allowed_paths` 检查 Git 可见文件差异。它能说明“哪些路径变了”，却不能知道“谁改的、为什么改、改动是否被新需求允许”。

而真实的目标偏离比路径更隐蔽。Agent 也可能只修改了允许的文件，却把“修复性能问题”改写成“关闭数据校验”；所有工具返回 0，也不代表用户目标达成。因此我们不能把确定性范围检查器冒充任意自然语言的语义裁判。

第 27 篇要在前两轮证据基础上形成三层关系：

```text
你批准的 Task Contract
          │
          ├── Git / 测试可观察事实
          │     └── Protected / Allowed Paths 差异
          │
          ├── 脱敏的执行事件
          │     └── 可关联 session / turn / event_id
          │
          └── 待审查的语义候选
                ├─ 对应合同 acceptance_id
                ├─ 具体 event_id
                └─ HUMAN_REVIEW_REQUIRED
```

这样 Watchdog 至少可以回答：**这个疑似偏离提示指向合同哪一项，以及支持它的哪一条执行线索？** 若没有这些锚点，它应拒绝给用户一个自信的红色警告。

## 二、我们怎样区分“范围事实”和“语义推测”？

想象你自己通过 VS Code 修改了 `GOAL.md`，Codex 在另一个窗口忙着运行单元测试。Git 差异会显示 `GOAL.md` 改了。这个事实很清楚；但没有操作系统级写入审计或其他可确认来源，我们不能说“Codex 擅自改了任务目标”。

新的 [drift_review_v27.py](examples/v04/watchdog/drift_review_v27.py) 明确输出两种不同信息：

**第一层 facts：** 沿用 `scope_guard.check(repo)` 检测到的受保护/范围外路径差异。输出标记 `basis=git_snapshot_difference` 和 `attribution=UNKNOWN`。即使确实发现了保护文件变化，也只是*文件快照差异*，不是责任归因。

**第二层 candidates：** 外部的可选建议（可能由人填写，或由用户在受控流程中使用 LLM 生成）。输入必须携带当前 Task Contract 的摘要、有效 `acceptance_id` 和已经出现在脱敏日志的 `event_id`。它最多得到 `verdict=HUMAN_REVIEW_REQUIRED`，不会输出“模型已经证实越权”。

这两层区别非常重要。真实监督软件的价值不只是少漏报，还包括在用户回来看报告时不说谎。第 27 篇没有默认启动大模型，也不允许候选建议修改批准合同。

## 三、先保护人类最重要的一项权力：决定任务原本是什么

你在第 05 篇建立了 `task_contract.py`。人类通过 `init` 写入一份目标合同，审查其中的 `goal`、`protected_paths`、`acceptance`，再通过 `approve` 明确接受。系统用 SHA-256 保存批准的版本。

这不是形式主义。假设 Codex 自己把 `goal` 从“修好登录校验”改成“简化登录流程”，又用新目标说自己完成了。若 Watchdog 自动跟随最后出现的目标，它就不再是在监督 Agent，而是在帮助 Agent 修改验收标准。

因此本篇检查：

```python
contract, approved, _, _ = task_contract.load(repo)
if not approved:
    return {"status": "BLOCKED_UNAPPROVED_CONTRACT", ...}
```

已有合同如果被修改却没有重新批准，程序直接阻断审查工作，避免把从未被用户认可的目标当成事实。

语义偏离候选也必须带上该批准版本的 `contract_sha256`。这意味着同一条建议不能悄悄借给另一个项目、另一个任务合同使用。哈希不是来源认证，但能为版本一致性提供稳定检查。

## 四、为什么建议也必须绑定真实存在的事件？

第 24 篇的 `step_links_v2.py` 已经处理人工任务关联；本篇沿用 `execution_v2.py` 中的 `event_id`。没有稳定 ID 的事件，`linkable=false`，不能让审查器根据“差不多那个时间”猜想应该挂在哪一步。

一个结构化的建议可以这么写：

```json
{
  "schema_version": 1,
  "contract_sha256": "这里必须填人类已批准的合同摘要",
  "items": [{
    "code": "POSSIBLE_GOAL_DEVIATION",
    "acceptance_id": "A1",
    "event_ids": ["来自已授权脱敏记录的真实 event_id"]
  }]
}
```

示例文件放在 [drift_candidates.example.json](examples/v04/watchdog/drift_candidates.example.json)。请注意：这是**待审查线索**，不是内容本身就真实的审计报告。

目前只接受三个候选码：`POSSIBLE_REQUIREMENT_MISREAD`、`POSSIBLE_SCOPE_EXPANSION`、`POSSIBLE_GOAL_DEVIATION`。这些码表明要人工核对的方向，不会替你做“目的或意图判断”。

为什么不用一个自由文本大字段记录“AI 认为 Codex 干了什么”？因为那很容易把用户原始提示、私人代码、工具输出原封不动地写进日志，还会导致模型生成的冗长建议在没有来源时被误当成事实。现在先只持久化必要的类别与 ID。

## 五、本次工程怎样延续旧文件而不另起炉灶？

你不需要安装一个语义判断服务，也不需要修改 Codex 的 Hook 配置。`drift_review_v27.py` 只导入三个已有模块：

```python
import evidence
import scope_guard
import task_contract
```

另一个输入来自 `execution_v2.read_projected()`。因此它可以在你先前的教学参考工程里独立运行，使用第三篇的 Git 快照、第 05 篇的人类批准合同、第 16 篇的范围规则和第 24 篇的稳定事件引用。

这也是软件工程的一项能力：将安全边界沉淀为可复用接口，而不是每四篇博客发明一套从零开始的监督系统。

工作流程没有任何会修改被监控仓库的默认步骤：

```text
读取当前合同与批准 hash
             ↓
读取 Git 可见差异
             ↓
从脱敏日志提取允许的事件 ID
             ↓
校验候选的合同版本与关联证据
             ↓
分开输出 facts / candidates / limits
```

**即使候选建议在 JSON 里写了 `"review_status":"CONFIRMED"`，程序也会忽略这个不被信任的结论，强制输出 `HUMAN_REVIEW_REQUIRED`。** 这项反例很重要：一个 Agent 自己准备的 JSON 不能自动宣布自己发现的偏离已被人认证。

## 六、Windows 操作：不需要启动 StepWise 或连接网络

从第 21 篇开始你使用的是单独克隆出来的验证目录。继续在 Anaconda Prompt（CMD）输入：

```bat
conda activate torch_env
cd /d D:\program\agent_watchdog\Agent-Watchdog-v2-round2-eval\examples\v04\watchdog
python drift_review_v27.py --repo "D:\program\agent_watchdog\hook_demo_v2"
```

这里有一个**明确前提**：`hook_demo_v2` 已经有用户自己批准的 Task Contract 和 Git 基线。若你的测试仓库尚未完成第 05–06 篇的 `init/approve`，程序会阻断或报告缺失，不应该照着截图把错误改成“无风险”。

正常且没有观察到范围差异时，可能出现：

```text
status: NO_FINDINGS_IN_OBSERVED_SCOPE
facts: []
candidates: []
```

以上是**预期情境**，不是你的真实机器输出。请牢牢记住完整含义：*目前可见的、受这些规则覆盖的 Git 文件中，没有发现与保护/允许路径规则相冲突的差异*。这并不等于证明 Codex 没有语义跑偏。

如果你已经准备好了经许可的脱敏事件和私有的候选文件：

```bat
python drift_review_v27.py --repo "D:\program\agent_watchdog\hook_demo_v2" --events "logs\events.jsonl" --candidates "D:\private\drift_candidates.json"
```

这会检验候选 ID 是否都能找到、是否具备稳定操作身份。与源文件不符就抛错，不会无声地“取最像的一条”。

## 七、三个反例最能说明它是否适合被信任

**反例一：保护文件是我手动改的。** 用记事本修改练习仓库 `GOAL.md`，再运行脚本。预期 `facts` 有 `PROTECTED_CHANGE`，但 `attribution=UNKNOWN`。如果脚本说“Codex 擅自修改”，说明它把发现差异和归因混成了一回事，验收失败。

**反例二：模型想给自己签字。** 在私有候选 JSON 里填 `"review_status":"CONFIRMED"`。脚本仍应该输出 `HUMAN_REVIEW_REQUIRED`。如果可以靠一个字段让它变成“已确认违规”，说明监督机制已被未可信来源接管。

**反例三：把 A 项目的事件挂到 B 项目的验收。** 修改 `contract_sha256` 或填写不在事件文件中的 `event_id`，应该直接拒绝。不能用工具类别匹配、模糊摘要、时间邻近代替真实引用。

另外，你还可以在另一个与当前工程无关的 Git 仓库重复检查：即便文件名同样叫 `GOAL.md`，它们也不能被拼成一条审计证据。仓库上下文隔离是后续多 Agent 产品化必须继续检验的边界。

## 八、为什么还不宣布已完成语义偏离检测？

一个真正可验证的自然语言偏离检测器至少需要：明确的人类原始任务与授权边界、实际变更/行为所对应的完整语境、人工审查标签、对无关任务的负例、模型不知道真值的前瞻测试，以及误报代价的明确评估。

当前我们没有这些数据。即使接入某个非常强的 LLM，让它阅读经过人工许可的摘要，也只是增加一个**风险候选生成器**，不能替代事实和人类同意，更不能让模型重写合同。本篇源码因此没有“调用 API 自动裁决”的隐蔽步骤。

保守不是拒绝智能化，而是在智能化之前确保可解释的失败边界。当一个模型说“可能偏离任务”，你至少应能追问：它对应原合同哪项约束？哪条执行记录？有没有真正的 Git 或独立验证证据？证据缺失时应该显示什么？

## 九、本章验收与下一步

可交付：只读的 Git 范围事实、批准合同版本约束、可追踪的事件引用、来源未认证的候选和拒绝自动确认的反例。全部正常的合成测试只证明这些接口行为，不构成真实 Codex 语义检测准确率。

当前还不能交付：自动从任意语言任务可靠判断语义偏离、操作系统级文件作者归因、无用户监督的越权制裁。

下一篇将从另一面完善“目标监督”：当 Agent 声称完成任务时，不仅是单元测试，报告文件、产物摘要等**非测试类结果**也需要独立验收。我们会先实现最保守的一种：人类预先批准的文件字节哈希检查，同时保持“字节一致不等于业务完成”的边界。

源码：[drift_review_v27.py](examples/v04/watchdog/drift_review_v27.py) · [Source / Gate 说明](docs/ROUND2_EVIDENCE_PROTOCOL.md) · [Windows 工作单](docs/ROUND2_WINDOWS_RUNBOOK.md)。
