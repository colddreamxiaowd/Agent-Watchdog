# 从零开发 Agent Watchdog（20）：V1.0 不应该靠宣布完成——最后一次综合验收与发布候选版

系列教程 · 第 20 篇（主线收官）｜软件工程 · Release Gate · 可复现测试 · GitHub

> **这不是“软件已正式 V1.0 上线”的公告。** 这是把第 01–19 篇的能力整理成一份**可执行发布门槛**，让你能够在自己的 Windows 电脑上逐项核实，再决定是否创建 GitHub Release。当前参考代码通过的自动化测试，不等于真实 Codex 集成、长时间稳定性或安全审计都已经通过。

## 一、回到最初的问题：我们为什么要开发 Agent Watchdog？

你一开始就说得非常明确：你不是要复现 StepWise，也不是只想知道 AI 有没有报错。你要的是**独立软件监督 AI Agent 是否真正按用户要求推进工作**。

最初那七个问题其实是我们整个系列的验收要求，而不是文章结尾写上“全部实现”的宣传文案。现在把它们重新放在桌面上：

| 原始需求 | 本系列提供的模块 | 真正完成还缺什么 |
|---|---|---|
| Agent 在做什么 | Hook、App Server 脱敏适配、SQLite | 真实 Windows/Codex 多会话验证、覆盖率边界 |
| 用户任务哪些已完成 | 人类批准的 Task Contract、Progress | 验收标准覆盖原始要求的人工审核 |
| 是否卡住、重复失败、无效循环 | Risk + Supervision 弱信号 | 真实轨迹标签、误报漏报评估、更多 outcome |
| 是否偏离原始目标 | Protected Paths、Allowed Paths | 自然语言语义审查、修改来源归因 |
| Agent 宣称完成是否可验证 | `PASSED/FAILED/STALE/INCONCLUSIVE` | 测试充分性、环境和外部副作用验证 |
| 何时提醒/调整策略 | 终端 / Web 的风险解释 | 本机通知和用户反馈闭环需要验证 |
| 长期历史、恢复、交接 | JSONL → SQLite、Backup、Handoff | 长时运行、灾难恢复和恢复演练 |

这张表可能不像营销页面那么令人兴奋，却是真正的工程价值所在：**你知道系统的哪一部分已经有证据，哪一部分只是设计和下一阶段的任务。**

如果某一项关键功能没有实际达到定义的验收标准，就不能仅仅因为“第 20 篇写完了”而给整套软件盖上完成章。

## 二、V1.0 在这里究竟表示什么？

我们在第 13–19 篇有一个不断反复出现的原则：**功能存在 ≠ 功能被验证；能运行 ≠ 能长期可靠运行。**

在这个项目里，我建议明确三个可区分的状态：

1. **Tutorial Complete（教程完成）**：九轮代码和二十篇文章已编写，基本示例测试通过，但没有要求所有真实用户场景完成现场验证。
2. **Release Candidate（发布候选）**：完成代码审查、自动化测试、文件结构检查、打包与使用说明；真实 Windows 现场验收可能还没有全部完成。
3. **V1.0 Released（正式发布）**：用户亲自确认关键真实场景通过、风险边界接受、安装恢复流程有效，然后在 GitHub 创建版本标签和 Release。

第 20 篇的工作重点，是让前两个阶段不会再被混写成第三个阶段。

## 三、建立发布门槛：机器检查与人工见证缺一不可

你可能习惯跑完：

```bat
python -m unittest discover -s examples\v04\tests -v
```

看见 `OK` 就感觉项目差不多了。但自动化测试中的 Agent 事件是我们生成的，Git 仓库也是临时创建的。真实 Codex 是否发出了官方 Hook、用户的 `hook_runner.cmd` 是否指向正确 Python、Windows 休眠后有没有丢事件，这些都不是那条命令能证明的。

我们因此设计一个保守的 `Release Gate（发布门槛）`：

```text
┌─────────────────────┐
│ 隔离自动化测试       │  代码层证明
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ doctor: 数据可读性   │  环境层基本检查
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ Windows 人工验收     │  现场证据和复核
│ 真实 Hook + 范围隔离  │
│ STALE + 备份恢复     │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 人类最后批准发布     │
└─────────────────────┘
```

其中真正可以由 Python 脚本检查的内容，并不等于全部都自动通过。我们新建的 `release_gate.py` 在缺少人工验收记录时返回 `BLOCKED`，而且即使所有 JSON 声明填写了 `true`，也只能返回 `READY_FOR_HUMAN_RELEASE_REVIEW`，**永远不会替用户宣布正式发布**。

## 四、正式文件结构：这 20 篇最终如何沉淀？

从第 04 篇开始，我们坚持不推翻旧目录：

```text
Agent-Watchdog/                       # GitHub 仓库
├── README.md                         # 20 篇系列目录
├── 从零开发 Agent Watchdog（01）.md
├── ...
├── 从零开发 Agent Watchdog（20）.md
├── examples/
│   └── v04/
│       ├── README.md
│       ├── CHAPTERS_13-16.md
│       ├── CHAPTERS_17-20.md
│       ├── RELEASE_ATTESTATION.example.json
│       ├── watchdog/
│       │   ├── evidence.py
│       │   ├── hook_logger_v04.py
│       │   ├── bridge.py
│       │   ├── task_contract.py
│       │   ├── journal.py
│       │   ├── scope_guard.py
│       │   ├── supervision.py
│       │   ├── dashboard.py
│       │   ├── operations.py
│       │   └── release_gate.py
│       └── tests/
│           ├── test_course.py
│           ├── test_next.py
│           └── test_release_round.py
└── .gitignore
```

这里的 `examples/v04` 是**连续迭代的教学参考目录**，并不表示所有文件只有 V0.4 能力。我们没有把每篇复制成一个完整独立的软件，从而避免代码版本长期分叉。对于真正作为产品发布的独立安装包，今后还需要专门的打包目录和版本约定，不能靠更改博客编号代替。

## 五、正式的机器门槛：release_gate.py

完整源码：[examples/v04/watchdog/release_gate.py](examples/v04/watchdog/release_gate.py)。它的思路并不复杂，我们刻意没有为它加入又一个大模型。

核心函数：

```python
REQUIRED = (
    'real_codex_hook',
    'cross_repo_isolation',
    'claim_not_completion',
    'test_stale_on_change',
    'backup_restore',
    'local_dashboard',
    'safety_review',
)
```

这些名称不是随意写出的宣传用语，每一个都来自前面章节的真实测试目标。为什么没有把“StepWise 准确率大于某值”作为当前必要条件？因为本系列的核心监督功能首先由确定性数据链提供，而 StepWise 尚未在真实 Codex 轨迹上完成阈值验证。不能把未做完的模型评估当作一个假装已经具备的产品指标。

脚本会读取一份人工填的 JSON 文件：

```json
{
  "observations": {
    "real_codex_hook": false,
    "cross_repo_isolation": false,
    "claim_not_completion": false,
    "test_stale_on_change": false,
    "backup_restore": false,
    "local_dashboard": false,
    "safety_review": false
  }
}
```

这是仓库随附的**未验收模板**，不是你已经通过的报告。如果你在电脑上真实完成一个项目的受信任 Hook 接入、能在日志中找到相应事件、核对了时间和会话，你才有资格把 `real_codex_hook` 改成 `true`；其余条目同理。即便都填 `true`，它也只是你自己的声明，需要保留外部证明材料供核对。

### 为什么 JSON 不足以认证真实事件？

因为 JSON 可以手工编辑，也可以由模型直接生成。如果 Supervisor 看见 `"real_codex_hook": true` 就自动声明真实验收完成，那么它和“Codex 自己说我完成了”没有本质区别。

所以脚本返回的最高状态是：

```text
READY_FOR_HUMAN_RELEASE_REVIEW
```

而不是 `RELEASED`。状态命名本身就是工程上的防误解设计。

## 六、实验 A：没有人工作证时，应该严格阻断发布

在 Anaconda Prompt 中：

```bat
conda activate torch_env
cd /d D:\program\agent_watchdog\watchdog
python release_gate.py --repo "D:\program\agent_watchdog\hook_demo" --db "D:\program\agent_watchdog\watchdog\data\journal.sqlite3"
```

因为没有提供 `--attestation`，所有人工核查项都视为未完成。脚本预期返回 `BLOCKED`，并列出 `real_codex_hook` 等尚未满足的条目。这不是代码失败，而是成功执行了我们的发布保护逻辑。

试着构造一个空的 JSON 文件：

```json
{"observations": {}}
```

将它保存到**仓库外**的私人目录，例如 `D:\program\agent_watchdog\watchdog_backup\v1_attestation.json`。然后：

```bat
python release_gate.py --repo "D:\program\agent_watchdog\hook_demo" --db "D:\program\agent_watchdog\watchdog\data\journal.sqlite3" --attestation "D:\program\agent_watchdog\watchdog_backup\v1_attestation.json"
```

仍应返回 `BLOCKED`。自动化测试也覆盖了“缺少声明”和“非法声明结构”这两种情况。

## 七、实验 B：为什么自动化测试通过还不能晋级？

假设你运行了所有 Python 单元测试，31 个全部通过，但你从未在自己的 Windows 电脑上让 Codex 执行一次真实操作。发布门槛应该怎么决定？

答案是：代码层基本逻辑得到一部分支持；**真实工具接入仍未验证**。所以发布门槛仍然阻断。

这就是我们长期强调的证据分层：

```text
① 代码语法检查通过            只能证明可解析
② 隔离自动化测试通过          只能证明测试场景符合预期
③ Windows 真实工具操作通过    支持本机端到端结论
④ 多天真实项目长时观察        支持有限的稳定性结论
⑤ 用户审核并发布              形成有边界的 V1.0 承诺
```

这条链也提醒你：项目里自带的自动化测试不可能证明“没有任何 bug”，测试本身仍可能漏掉问题。后续越是加入模型解释，越要保留这种谦逊的工程判断。

## 八、给你的 Windows V1.0 验收清单

### 第一部分：真实事件接入

先看第 13 篇的工作单：能否在可信项目中通过 `/hooks` 检查配置；Hook 的 Python 路径是否正确；真正让 Codex 创建一个文件并运行一次工具后，是否在 `events.jsonl` 中留下对应的带源会话信息的记录；两个不同项目是否不会被当成同一仓库。

你应保存经脱敏的时间、工具类型、会话标识和现场截图。不要把整个私有日志随意上传公开仓库，也不要用模拟 `echo` 命令代替真实事件。

### 第二部分：任务约束和完成验收

在独立测试仓库里建一个明确、经过你批准的任务合同，先确认 `NOT_TESTED`，再运行一次批准的检查使其进入 `PASSED`；随后修改被测代码，确认它变成 `STALE`；再做受保护文件变更，确认出现路径证据；在 Agent 声称完成但还有失败或过期验收时，必须拒绝 `VERIFIED_COMPLETE`。

特别注意：如果测试命令本身不充分，状态机的 `PASSED` 也只证明这项测试在特定快照上返回了 0，**不证明所有用户要求都正确实现**。

### 第三部分：异常监督和解释

构造“同一会话六次 Bash”与“两个会话各三次 Bash”的对照实验，确认后一种不会触发伪循环；检查没有任何模块将启发式分数自动升级成事实；检查系统是否因几分钟没有事件就误判 Agent 已卡死。

还要确认你的日常提醒是可读、可行动的：指出哪个验收项过期、哪个文件超出允许范围，以及你下一步该去核对什么。

### 第四部分：长期运行和恢复

进行受控的 Bridge 关闭/重启、重复事件同步、SQLite 备份与副本恢复。真实运行一段你认可的观察周期，至少记录版本、操作系统、时间、恢复是否成功、发现的问题以及相应解决办法。对于涉及休眠和磁盘空间不足的测试，必须在不影响重要文件的前提下进行。

### 第五部分：安全与发布资料

检查是否只保存必要事件元数据、是否意外收录 API Key 或用户私人提示词、是否打开了网络监听、是否把包含路径与私人内容的日志提交进 Git。检查 `.gitignore`、许可证与第三方依赖，准备安装指南、变更说明和已知局限。

**以上任意一个关键门槛没有足够的真实证据，就先发布候选代码或继续内部试用，而不是提前宣布 V1.0 完成。**

## 九、GitHub 的正式发布顺序应该是什么？

这次你让我“继续写博客并上传”，我们可以把第 17–20 篇和对应源码提交到 `main`。但**提交教程文件 ≠ 创建产品 Release**。

建议顺序：先提交经过测试的参考代码和文档；你在本机真实完成验收并保存记录；确认与仓库代码对应的提交 SHA；再给出版本号和 Release Notes；最后由你明确认可后创建 GitHub Release。

如果后续要发布正式 V1.0，Release Notes 不能只写“支持智能监督”。应该说明目前支持哪些接入方式，哪些是离线导入、哪些是人工批准的验收、哪些依赖真实 Git 可见范围，以及 StepWise 为什么还不是默认控制器。

如果没有真正的安装包、正式许可证或可复现的 Windows 安装流程，我们还需要在发布前补齐。**本科生的个人项目完全可以先有一个高质量 Release Candidate，不必为了面子在第一天声称生产级。**

## 十、你现在具体应该执行什么？

完成本轮代码同步后，建议按顺序运行：

```bat
REM ① 在本地完整仓库根目录运行所有隔离测试
cd /d D:\program\agent_watchdog
python -m unittest discover -s examples\v04\tests -v

REM ② 检查原项目的 Git 基线与最新证据
cd /d D:\program\agent_watchdog\watchdog
python integration_check.py --repo "D:\program\agent_watchdog\hook_demo"

REM ③ 检查本地 SQLite 和 Git 报告的新鲜度
python operations.py --repo "D:\program\agent_watchdog\hook_demo" doctor

REM ④ 默认应阻断：未提供现场核查的真实记录
python release_gate.py --repo "D:\program\agent_watchdog\hook_demo" --db "D:\program\agent_watchdog\watchdog\data\journal.sqlite3"
```

其中第一条命令要求本地仓库完整包含 `examples/v04/`；如果你的 Windows 项目中仅复制了增量模块，就先不要假设这条路径存在。第二至四条要求你已经把对应 `.py` 文件放到旧 `watchdog` 文件夹。这些都是文档要明确交代的前置条件，不是报错后再让你重装整个环境。

## 十一、如果最终只完成了一个有界监督器，算不算成功？

算，但要正确命名范围。

如果系统能独立记录、可靠保存、让用户查看真实执行事件、检查 Git/测试证据、发现确定性越界、提醒人工检查，那么它已经是一项有价值的**Agent 监督工程原型**。

但如果仍无法可靠识别语义偏离、无法区别真实的无效循环与合理重复、没有真实 Windows 端到端验收、没有足够的备份恢复实验，那么就不应声称它完整实现了最初七项需求。

真正的工程成熟度不来自模型参数大小，也不来自教程的章数，而来自你能在具体场景下给出可复查的证据，并且诚实承认未知。

## 十二、给未来的你：二十篇之后应该怎么继续？

主线到第 20 篇就结束。此后所有工作应由真实使用问题驱动，而不是为了“第 21 篇”增加一个功能。

例如，你在实际开发中发现连续三次失败修复是高频痛点，就收集经许可的样例，比较简单规则、StepWise 和结构化 outcome 的实际误报表现。如果发现切换 Codex 会话后容易丢失目标上下文，就优先改进合同和交接。如果某个提醒经常误报，就为那类情况增加回归测试。最重要的是：**先用具体失败驱动产品迭代，再决定要不要引入更复杂的 AI。**

## 十三、第 20 篇的最终验收标准

- [ ] 明确区分 `Tutorial Complete`、`Release Candidate` 和 `V1.0 Released`。
- [ ] 缺少真实 Codex 人工核查时，`release_gate.py` 返回 `BLOCKED`。
- [ ] 即便所有声明为真，工具最多返回 `READY_FOR_HUMAN_RELEASE_REVIEW`，不自动创建 Release。
- [ ] 第 01–20 篇目录、增量源码、测试和文档路径都能互相对应。
- [ ] 你在自己的 Windows 电脑上保存了真实事件、测试证据过期、越界检查、备份恢复和安全复核记录。
- [ ] 正式发布前审阅全部关键门槛，没有把模型风险信号当作已经确认的事实。
- [ ] 本轮 GitHub 提交仅代表教程和参考源码更新，不冒充真实 V1.0 Release。

**收官语**：这二十篇教程最重要的成果，不是做出“又一个 AI 监控面板”，而是建立一种可持续迭代的工程方法——Agent 可以执行工作，但是否满足用户要求，应该由独立证据和明确标准来判断。等你完成真实验收，这套软件才有资格把版本号写成 V1.0。

### 参考与源码

- [本篇完整源码：release_gate.py](examples/v04/watchdog/release_gate.py)
- [V1.0 人工验收模板](examples/v04/RELEASE_ATTESTATION.example.json)
- [第 13–16 篇本机验收单](examples/v04/CHAPTERS_13-16.md)
- [第 17–20 篇本机验收单](examples/v04/CHAPTERS_17-20.md)
- [GitHub Releases 官方文档](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)
- [GitHub Actions 官方文档](https://docs.github.com/en/actions)

> **截止到本篇代码生成时的证据边界**：隔离自动化测试和静态质量检查可以在本次工作环境中执行；真实 Windows 11、Codex Hooks、多天持续运行和正式 GitHub Release 必须另行验收，不能替你自动补写成功记录。
