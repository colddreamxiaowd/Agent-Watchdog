# 从零开发 Agent Watchdog（16）：AI 有没有擅自跑偏？先建立可信的任务范围检查

系列教程 · 第 16 篇 | Scope Guard · 受保护文件 · Git 快照 · 目标偏离 · 可解释风险

你让 Codex 修复登录接口，并明确交代：“只修改登录相关代码，不要碰支付模块，也不要改变项目目标文件。”

半小时后，Codex 回答：“登录修复完成，测试通过。”然而打开 Git，你发现它还改了 `payment/billing.py`。这正是你最初想让 Agent Watchdog 自动提醒的情况——**Agent 会不会一边干活，一边擅自扩大任务范围？**

问题听起来像一道大模型判断题：“这项修改是否符合用户意图？”但我们先不要把它全部交给另一个 Agent。因为这里其实混杂了三个层次完全不同的问题：

1. 事实问题：某个文件相对于基线是否真的变了？
2. 范围问题：这个文件是否位于**人类批准**的可修改路径范围内？
3. 语义问题：这个变更的目的、原因与原始用户任务是否一致？

前两项在限定条件下可以用代码重复验证，第三项可能需要上下文、差异内容、项目架构知识，以及人工或经过评估的模型判断。**如果把三个问题混成一句“检测到 Codex 跑偏”，监督器就会比被监督的 Agent 更不可靠。**

本篇先把前两层落实为可验证的软件，再给第三层留下严格限定的接口与证据要求。新模块位于 [`scope_guard.py`](examples/v04/watchdog/scope_guard.py)。

## 一、同一个文件修改，为什么不能马上给 Agent 定罪？

设想以下三种情况：

**情况 A：** Codex 正在修复登录 Bug，却修改了 `GOAL.md`，而原始任务明确禁止修改该文件。Watchdog 可以确定地说：“受保护文件相对于基线发生了变化。”

**情况 B：** Codex 正在修复登录 Bug，却修改了 `payment/billing.py`；但项目中的登录流程实际上与支付认证共享一个安全组件。这个修改可能有关，也可能多余。系统应当说“超出已声明修改路径，需要复核”，而不是直接宣布“违反任务语义”。

**情况 C：** 你在 VS Code 里自己改了 `payment/billing.py`，Codex 根本没碰它。Git 扫描仍然会看到变化。如果 Watchdog 说“Codex 擅自修改支付模块”，这属于**错误归因**。

我们能确定的是文件内容差异、批准范围以及验收状态；不能仅通过 `git status` 确定修改者或修改意图。

这也是为什么第 03 篇已经把 Git 事实检查与 Agent 事件观察分开。从本篇开始，你能看到这个设计终于服务于更高层的目标监督。

## 二、设计一份可审计的“修改范围”

第 05 篇的合同已经支持：

```json
"protected_paths": ["GOAL.md", ".github/workflows/*"]
```

这表达的是**明确禁止变动**的路径。现在我们再给合同增加一个可选字段：

```json
"allowed_paths": [
  "auth/*",
  "tests/test_auth*.py",
  "README.md"
]
```

它描述的是用户**允许本轮任务涉及的路径范围**。两类字段不是同义词。

- `protected_paths` 被检测到变化，是针对该路径约束的明确冲突信号。
- `allowed_paths` 之外的文件变化，是**超出声明范围的待复核信号**；有时它可能是必要的依赖修复，但需要解释和确认。

为什么不直接拿“Git 项目目录外的所有文件”当禁止修改范围？因为那会错把一切正常的间接改动标为越权：例如测试生成的新快照、已经商定的文档更新或构建配置变更。我们需要让人把任务边界写清楚，而不是模型偷偷决定哪些文件重要。

**最关键的原则：这个范围必须与合同一起审核和批准。** 如果 Agent 能自行添加 `"allowed_paths": ["*"]`，所谓范围监督就完全失去意义。

## 三、可选字段不会破坏你之前的合同

`scope_guard.py` 不要求所有旧合同立刻升级。若合同没有 `allowed_paths`，它会显示：

```json
{
  "status": "NOT_CONFIGURED",
  "allowed_paths_configured": false
}
```

注意，`NOT_CONFIGURED` 不是 `NO_FINDINGS_IN_SCOPE`，更不是 `SAFE`。没有约束，就没有足够的依据判断某次修改是否超出了允许范围。

同样，若监督器找不到之前创建的 Git baseline，它不会拿当前文件状态当作安全的初始参照，而是返回 `NO_BASELINE`。如果合同 SHA-256 校验失败，返回 `UNTRUSTED_CONTRACT`，不继续利用已被修改的范围规则。正是这些“不做乐观猜测”的分支，保护了监督者的独立性。

本篇为 `allowed_paths` 采用 Git 风格相近但不完全等价的 `fnmatch` 路径模式匹配。对于简单模式 `auth/*`、`tests/test_auth*.py` 足够演示；它**不是**完整的 `.gitignore` 语法，尤其不要依赖它对复杂嵌套目录实现所有 Git pathspec 的语义。正式项目应该给关键路径添加测试用例，必要时升级成更明确的路径匹配规则。

## 四、最小架构：让 Git 和批准合同各司其职

```text
          人工批准的原始任务合同
             ├─ protected_paths
             └─ allowed_paths
                       │
Git 初始基线 ───────────┼────────── Git 当前工作树
                       ▼
                 逐文件比较
                       │
          ┌────────────┼──────────────┐
          ▼            ▼              ▼
    保护文件已变化   超出允许范围   允许路径内变化
          │            │              │
          ▼            ▼              ▼
    确定性差异事实   待人工复核      不触发此类风险
                       │
                       ▼
                有限的监督提醒
```

这里的“允许路径内变化”也不意味着修改正确。Agent 仍然可以把 `auth/login.py` 改得一团糟；我们的路径范围检查不会替代码审查，也不会替功能测试。

相反，范围规则只是**必要但远非充分**的条件。它能帮助我们把用户最讨厌的无关改动及早暴露出来，让用户决定是否需要介入。

## 五、代码详解：scope_guard.py 怎样判断？

完整代码位于 [`scope_guard.py`](examples/v04/watchdog/scope_guard.py)，不用重新安装模型。

主要流程可以压缩为：

```python
contract, approved, _, _ = task_contract.load(repo)
if not approved:
    return {"status": "UNTRUSTED_CONTRACT", "findings": []}

base = evidence.read_json(evidence.state_dir(repo) / "baseline.json")
if base is None:
    return {"status": "NO_BASELINE", "findings": []}

changed = evidence.diff_files(base["files"], evidence.snapshot(repo))
```

这三段各自回答不同的问题：第一段确保判断标准得到人类批准，第二段确保存在可信的比较起点，第三段确保文件确实发生变化。

然后逐个比对：

```python
for path in changed:
    if matches_protected(path):
        code = "PROTECTED_CHANGE"
    elif allowed_paths_is_defined and not matches_allowed(path):
        code = "OUTSIDE_DECLARED_PATH_SCOPE"
    else:
        continue
```

设计上优先处理 `PROTECTED_CHANGE`，因为这是已经明确被保护的路径。其他超范围变化则标为需要人工复核的信号。

最终结果包含 `path`、`code`、`kind` 和 `severity`，但不包含“作者一定是 Codex”这样的推断。文件作者归属，需要更充分的进程、执行时序和审计数据；一条 Hook 事件与一个文件变更在时间上相邻，并不足以构成归因证明。

## 六、实验 A：为安全演示创建合同

先确认你使用的是测试仓库：

```bat
conda activate torch_env
cd /d D:\program\agent_watchdog\watchdog
python task_contract.py --repo "D:\program\agent_watchdog\hook_demo" status
```

如果该仓库已经存在正式批准的合同，不要直接覆盖它。建议为本篇使用新的 Git 演示副本，或者在原有合同可以公开修改且已备份的前提下按人工审核流程重新批准。以下 JSON 只是供你在**新演示仓库**创建合同的例子：

```json
{
  "schema_version": 1,
  "goal": "修复 hello.py 的问候语逻辑，不改动任务目标",
  "protected_paths": ["GOAL.md"],
  "allowed_paths": ["hello.py", "test_hello.py"],
  "acceptance": [
    {
      "id": "A1",
      "description": "问候语返回值正确",
      "command": ["python", "-m", "unittest", "test_hello.py", "-v"]
    }
  ]
}
```

将它存储在被监督仓库外，例如 `D:\program\agent_watchdog\contracts\scope_demo.json`。仔细审核后，在新演示仓库首次执行 `init` 和 `approve`：

```bat
python task_contract.py --repo "D:\program\agent_watchdog\hook_demo" init --contract "D:\program\agent_watchdog\contracts\scope_demo.json"
python task_contract.py --repo "D:\program\agent_watchdog\hook_demo" approve
```

这些命令只适用于尚无旧合同的演示状态；已有合同时 `init` 应拒绝覆盖。若你已经为第 15 篇准备了一份经批准的合同，也可以直接在它包含 `allowed_paths` 时继续使用，无需重复初始化。

## 七、实验 B：第一次扫描，认识 NOT_CONFIGURED 与 NO_FINDINGS

执行：

```bat
python scope_guard.py --repo "D:\program\agent_watchdog\hook_demo"
```

如果你刚创建了基线，文件没有变化，且合同包含 `allowed_paths`，示意结果应接近：

```json
{
  "status": "NO_FINDINGS_IN_SCOPE",
  "changed": [],
  "findings": [],
  "allowed_paths_configured": true
}
```

这依然**不代表没有任务偏离**，只代表“本篇范围检查没有观察到范围问题”。例如 Agent 可能完全没工作、原功能仍然错误，路径范围检查也不会报告这一点。我们要与第 15 篇的验收进度结合看，而不是互相替代。

如果你删除 `allowed_paths` 并重新批准这个变化，就应该显示 `NOT_CONFIGURED`；但不要为了测试这一分支去破坏真实合同。仓库的自动化测试已经使用临时仓库对这一情况进行了隔离验证。

## 八、实验 C：修改无关文件，观察越界提醒

在实验仓库创建一个不在允许范围的文件：

```bat
cd /d D:\program\agent_watchdog\hook_demo
echo # manual scope probe > unrelated_payment.py
```

再次运行：

```bat
cd /d D:\program\agent_watchdog\watchdog
python scope_guard.py --repo "D:\program\agent_watchdog\hook_demo"
```

如果该文件不在 `.gitignore` 中，又没有被合同允许，你应该看到类似：

```json
{
  "status": "FINDINGS",
  "findings": [
    {
      "path": "unrelated_payment.py",
      "code": "OUTSIDE_DECLARED_PATH_SCOPE",
      "kind": "needs_human_review",
      "severity": "medium"
    }
  ]
}
```

此处最重要的不是颜色，而是 `kind=needs_human_review`。为什么不是 `codex_misbehavior`？因为本实验是你亲手创建的文件，Watchdog 没有理由把它归咎于 Codex。

这也是你以后调试 Agent 监督软件时必须养成的思维：**观察到事实 → 检查归因 → 最后才决定是否需要责备或干预。**

## 九、实验 D：受保护文件变化的优先级

继续在演示仓库中修改 `GOAL.md` 一行，再运行 `scope_guard.py`。你应该同时看到 `unrelated_payment.py` 的范围提醒和 `GOAL.md` 的 `PROTECTED_CHANGE`。后者优先标为高严重度的“确定性快照差异”，但仍不表明一定是 Agent 修改了它。

再把 `hello.py` 修改成错误实现，执行第 15 篇的 `progress.py`：可能看到“路径没有超出允许范围，但验收不通过或证据过期”。这两个实验联合起来揭示：**路径没有越界，不等于任务完成；任务验收通过，也不代表每一处额外修改都经过授权。**

想象我们的目标是一个可解释的监督报告，它应当把两种事实同时展示：

```text
TASK：修复问候语逻辑

验收 A1：STALE
路径范围：发现 unrelated_payment.py 超出声明范围
保护文件：GOAL.md 发生变化
归因：尚无法证明修改由 Codex 造成
建议：先检查 Git diff 和来源；随后在可信环境中重跑 A1
```

这种报告不需要强行给出 91 分的“异常指数”，却比一个神秘的评分更有用。

## 十、这算“AI 语义目标偏离检测”了吗？

**还不算。**

第 16 篇实现的是一个具备任务上下文的、确定性加保守启发式的**范围偏离检测器**。它识别的是人类批准的路径边界，并不能理解任意自然语言要求。例如：

- 用户说“只做必要的重构”，系统暂时不知道什么算必要。
- 用户说“不要增加运行成本”，Git 文件路径可能全部合规，性能却下降。
- 用户说“必须保留 API 向后兼容”，仅凭文件范围不能证明接口兼容。
- 用户说“不要访问外部网络”，目前没有完整的命令参数或网络流量审计，无法据此得出保证。

如果未来在第 17 篇加入 StepWise 或轻量语义模型，我们应把它定位为**候选风险建议**：模型读取经审查、最小化的任务与行为摘要，给出疑似偏离原因、证据引用和不确定性；模型不得修改合同批准状态、Git 指纹或测试退出码。对于高风险结论还需要独立复核和误报评估。

也就是说，**真正的语义监督应当建立在可信的事实层上，而不是取代事实层。**

## 十一、用户确认、数据最小化与安全界限

你可能想让 Watchdog 自动终止越界 Agent。但本篇明确不做。原因有三点：

第一，`OUTSIDE_DECLARED_PATH_SCOPE` 可能是必要的间接修复，误停会损害任务；第二，当前没有足够的进程级归因，误认用户手工修改也可能触发错误控制；第三，自动中断、回滚和重试属于更高权限操作，应有单独的授权与恢复协议，不能被一个路径规则悄悄触发。

我们的目标是独立软件提醒你：“这里有值得调查的事实”，而不是另一个代替用户做决定的 Agent。

日志也应维持最小采集。路径名本身可能泄露个人项目结构；公开发布 GitHub 时，提交的是**工具代码与示例数据**，不是本机私有合同、日志、SQLite 账本或真实会话原始输出。

## 十二、常见问题与实操检查

| 症状 | 可能原因 | 正确处理 |
|---|---|---|
| `UNTRUSTED_CONTRACT` | 合同未经批准或批准摘要不匹配 | 人工审核合同，再决定是否重新批准 |
| `NO_BASELINE` | 还没建立第三篇 Git 基线 | 在可信演示仓库先建立基线 |
| `NOT_CONFIGURED` | 合同缺少 `allowed_paths` | 视需求明确边界；不能当成安全证明 |
| 明明没碰文件却出现提醒 | 用户/其他进程修改、未忽略的生成文件 | 核对 Git diff 与时间，不能先归罪 Codex |
| 忽略目录中的文件变化没显示 | 旧 `evidence.py` 只检查 Git 可见范围 | 扩展专门的敏感路径监测，不虚报覆盖范围 |
| 允许的子目录未匹配 | `fnmatch` 不是完整 Git pathspec | 为路径模式增加明确的正反例测试 |
| 验收已通过但有范围提醒 | 路径约束与功能验收是独立维度 | 人工核对范围问题，不能只看测试状态 |

读者练习：如果 Codex 只修改了 `hello.py`，但将正确代码改坏，范围报告是什么？如果你自己修改了 `GOAL.md`，能否说 Codex 违反约束？如果当前合同没有 `allowed_paths`，为什么不能把空的 `findings` 解读为“无偏离”？

## 十三、本篇验收与下一轮路线

本篇至少应通过五个场景：没有批准合同时拒绝下结论；没有基线时拒绝比较；已批准且无变更时显示没有观察到范围问题；超出允许文件路径时给出待复核提示；受保护文件变化时明确标记快照差异。相关隔离测试在 [`test_next.py`](examples/v04/tests/test_next.py)。

完成第 16 篇后，Agent Watchdog 对你最初提出的**“发现可能擅自扩大任务范围”**已经有了可靠的第一层工程能力，而不是一个完全依赖语言模型猜测的黑箱判断器。

接下来的第 17 篇才应该讨论：如何利用真实 Codex 轨迹、失败重试信息、任务上下文与可选小模型，做经过误报测试的**智能异常与语义风险评估**。这一步需要真实轨迹评测，不能靠几个手写案例宣称模型已经可靠。

参考：[Git 文件列表](https://git-scm.com/docs/git-ls-files) · [范围检查源码](examples/v04/watchdog/scope_guard.py) · [任务合同](examples/v04/watchdog/task_contract.py) · [自动化测试](examples/v04/tests/test_next.py)。
