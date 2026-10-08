# 从零开发 Agent Watchdog（07）：第一次做“异常监督”——六次 Bash 到底是不是死循环？

> **系列教程 · 第 7 篇** · Python · 风险规则 · 证据等级 · 告警去误报  
> 本篇不运行 StepWise，也不要求训练分类器。先建立可以解释、可以复查、不会胡乱喊“卡死”的异常规则。

现在我们的 Watchdog 能看见事件，也能检查 Git、保护文件和测试证据，还知道人类批准的任务合同。但你最初想做的功能远不止这些：你希望它发现 Agent 偏离任务、不断失败、重复操作、无效消耗，必要时提醒你介入。

听起来应该轮到“大模型判断”了吧？先等一下。我们先讨论一个看似简单、实际非常容易被误判的问题。

## 一、观察到六次 Bash，能证明什么？

考虑这两段轨迹：

```text
轨迹 A：
Bash: python -m unittest test_auth.py
Bash: python -m unittest test_payment.py
Bash: python -m unittest test_profile.py
Bash: git status
Bash: git diff
Bash: git log -1

轨迹 B：
Bash: python test.py   -> failed
Bash: python test.py   -> failed
Bash: python test.py   -> failed
Bash: python test.py   -> failed
Bash: python test.py   -> failed
Bash: python test.py   -> failed
```

如果事件日志为了隐私只保存工具名称，这两段都会变成：

```text
Bash, Bash, Bash, Bash, Bash, Bash
```

但显然 A 可能是正常检查不同文件，B 才更像重复失败。**只有工具名称时，任何“已陷入死循环”的判断都属于过度推断。**

因此本篇会给出三个等级：

- **事实（fact）**：例如 Git 指纹发现受保护文件变化、合同 A2 显示 `STALE`。
- **启发式风险（heuristic）**：例如连续六条事件都来自同一种工具，值得回看上下文。
- **无法判断（unknown）**：例如没有命令内容，也没有真实失败次数，就不能断言重复失败。

我们不采用一个没依据的“风险值 98%”。这样的数字看似高级，却容易比直接说明证据更误导人。

## 二、构造一个“事实—解释—建议”的风险对象

我们的风险记录采用简单 JSON 字段：

```json
{
  "severity":"low",
  "code":"REPEATED_TOOL_CATEGORY",
  "kind":"heuristic",
  "evidence":{"tool":"Bash","count":6},
  "action":"Review context; six same-named tools do not prove a loop"
}
```

这里有两个刻意做出的决定。

第一，代码 `REPEATED_TOOL_CATEGORY` 不叫 `STUCK`。名字不应该比证据承载的含义更强。

第二，给出 **action**，告诉使用者“下一步怎样调查”，而不是只让你焦虑地看到一个红点。

完整实现位于 [`risk.py`](examples/v04/watchdog/risk.py)。

## 三、先实现确定性告警

这一篇最实用的两条规则其实不需要模型。

### 规则 A：保护文件被修改

如果从 Git 基线到现在，`GOAL.md` 发生变化：

```python
if report.get("protected"):
    alerts.append({
        "severity": "high",
        "code": "PROTECTED_CHANGE",
        "kind": "fact",
        "evidence": report["protected"],
        "action": "Inspect changed protected files",
    })
```

为什么是高优先级？因为这是明确的约束冲突信号。但它不是“已确认 Codex 恶意修改”，更不是“需要立即回滚”。你或者编辑器也可能写过文件。**我们知道的是文件变化，不是行为动机。**

### 规则 B：验收证据失败或过期

如果 `test_status` 是 `FAILED`、`STALE`、`INCONCLUSIVE`，系统提示要检查或重新运行被批准的测试。这一条的价值在于能直接指向可执行的下一步。

我们还读取第 05–06 篇的合同验收结果，把 A1/A2 各自未通过的状态单独列出来。因为 A1 已通过、A2 未测试，与 A1 测试失败、A2 已过期，是完全不同的工作计划。

## 四、再增加一条低优先级启发式规则

```python
last = (recent_events or [])[-6:]
if len(last) == 6 and len({x.get("tool") for x in last}) == 1:
    alerts.append({
        "severity": "low",
        "code": "REPEATED_TOOL_CATEGORY",
        "kind": "heuristic",
        "evidence": {"count": 6, "tool": last[0].get("tool")},
        "action": "Review context; six same-named tools do not prove a loop",
    })
```

它做的事情非常有限，只检查最近六条事件使用的工具名称是否一致。

更完整的重复失败检测以后至少需要“同一操作的稳定标识、是否真正失败、失败原因是否相同、重复前后状态是否变化”等信息。我们第一篇因为隐私默认不保存命令参数，所以目前**没有足够证据识别同一命令的重复运行**。不要偷用一句“相似度很高”来填补这块证据缺口。

## 五、手把手实验：让它提醒，但不失控

本篇源码已经集成到 `watchdog_cli.py` 中。在你运行过第四篇 `bridge.py --once`、并建立过第五篇合同后，执行：

```bat
conda activate torch_env
cd /d D:\program\agent_watchdog\watchdog
python watchdog_cli.py --repo "D:\program\agent_watchdog\hook_demo" alerts
```

你可能观察到：

```json
[
  {"code":"UNVERIFIED_A2","kind":"fact","evidence":"STALE"},
  {"code":"PROTECTED_CHANGE","kind":"fact","evidence":["GOAL.md"]}
]
```

输出只是一种**示例**，你本机如果没有修改 `GOAL.md`，自然不该凭空出现保护文件告警。

### 专门制造一个反例

手动在 `hook_demo` 的 `GOAL.md` 添加一行，再执行 `bridge.py --once` 和上面的 `alerts`。应该看到对应的事实告警；把文件恢复后再扫描，告警应随着证据变化而变化。

同时，在没有工具事件的情况下，程序不应只因为“十分钟没有 Hook”就断言 Codex 卡住。你可以关闭 Codex，再运行 `alerts`，观察它是否保持克制。

## 六、为什么暂时不用 StepWise 做主引擎？

你已经在本机成功加载 StepWise ModernBERT，但两条手写样例都显示 `NOT_STUCK≈1`。这说明本地推理链路已经通了，**不能证明对 Coding Agent 轨迹的预测质量**。

下一阶段可以采样真实 Codex 执行轨迹、建立人工确认的正常/异常标签，再测试检测器误报和漏报。如果 StepWise 或别的开源模型真正有增量价值，就把它作为“提示来源”，而不是覆盖 Git 与测试事实。

还有一个更现实的理由：当前监督器对真实任务目标偏离的判断仍然不够。判断“Agent 有没有擅自扩张原任务”，需要原始要求、当前计划、已观测行为和证据之间的关联，仅靠卡住检测器并不解决。

## 七、一次完整的设计复盘

你现在可以把系统看成两部分：

```text
确定性监督：
Git file hash / approved contract / test exit code
    ↓
   能明确说明依据的事实

启发式监督：
事件窗口 / 重复工具类别 / 未来的小模型
    ↓
   提示进一步调查，不冒充确定事实
```

这种区分保证即使以后模型误报，事实账本也不会被它篡改。

本篇验收标准：修改受保护文件能触发事实告警；`STALE` 不会被误写成 `FAILED`；同类工具的重复只得到启发式提示；无新事件不等于 stuck；整个模块不会调用 `kill`、`retry`、`rollback` 或修改 Codex 运行状态。

下一篇：让这些事实与提示通过统一面板和交接摘要进入日常使用，而不是分散在几个命令输出里。

延伸阅读：[StepWise](https://github.com/yale-nlp/StepWise) · [Codex Hooks](https://developers.openai.com/codex/hooks) · [完整风险规则](examples/v04/watchdog/risk.py)。
