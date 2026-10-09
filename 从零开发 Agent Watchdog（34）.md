# 从零开发 Agent Watchdog（34）：Codex App 明明在工作，Watchdog 为什么不知道它在做哪个任务？

> 第 34 篇｜会话别名、Git 项目映射与 Task Contract 人工绑定｜Windows Codex App

## 一、最容易被忽视的产品断层：有事件，不等于有任务

上一轮你在 Windows 上已经报告成功：Codex Desktop 确实经全局 Hook 产生了 SessionStart、PreToolUse、PostToolUse、Stop、SessionEnd 等事件。Watchdog 可以读取这些事件，还能对重复失败和未结束的工具调用提醒人工检查。

不过我重新打开源代码时发现，我们距最初的目标仍有一道关键鸿沟：**日志里的一个会话，Watchdog 并不知道具体属于哪份工作。**

你可能在 Codex App 中并排打开几份项目。一个 Agent 修复实验代码，另一个 Agent 写报告，第三个 Agent 仅仅读取资料。旧观察器知道有多少工具调用，但不知道“这个修复任务原本承诺禁止修改哪个文件”。如果直接把所有事件合在一起，它会产生跨项目污染：本来应该属于项目 A 的失败，可能被错误归给 B。

这一次我要解决的是**观察事件和用户任务之间的身份映射**，而不是继续加一个新的异常分类器。

## 二、为什么我们不能直接拿 Hook 中的 cwd？

第 29 篇为了保护用户隐私，故意在 `app_hook_v29.py` 中将 `cwd` 置为 `None`。这是有道理的：工作目录可能包含姓名、科研课题、用户私有路径，而 Hook 可能来自整个 Windows 桌面客户端。默认将它写入公开日志或报告是不必要的数据收集。

但这也有代价。老版本的 `bridge.py` 通过 `cwd` 判断事件属于哪个 Git 仓库；在新的 App 脱敏日志中，它看不到这个字段，因而不能安全归属项目。

有两个看起来方便的错误方案：第一，把 `cwd` 恢复采集并自动以路径绑定项目；第二，根据“最近打开的目录”猜当前会话。前者扩大采集范围，后者在并行任务下几乎必然出错。更重要的是，Hook 事件里的路径也是进程提供的声明，不是密码学认证，不能把它当作绝对可信的用户授权。

我选择比较笨但可靠的方案：**人只需确认一次对应关系，然后程序在这个授权范围内持续观察**。这不是长期方案的终点，却是我们在不破坏既有安全边界时能真正实现的闭环。

## 三、会话别名究竟是什么？

新文件 [session_binding_v34.py](examples/v04/watchdog/session_binding_v34.py) 默认从已存在的私有脱敏 JSONL 读取最近一段完整事件。事件中必须有来源标签、会话 ID、接收时间和事件名；半条尚未写完的 JSON 不会参与匹配。会话默认必须在 48 小时内出现过，否则不推荐用来新绑定。

它不把原始会话 ID 直接打印到终端，而是计算一个短别名：

```python
import hashlib

def alias_for(source, session):
    value = source + "\0" + session
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
```

这不是加密签名，也不能用来鉴别 Codex App 身份。它只是让用户选择某个会话时，不必在日志之外反复复制完整会话 ID。短别名可能理论上碰撞，所以代码在观测窗口中发现别名对应多组来源/会话时直接拒绝继续，而不是选择第一条数据。

真正影响使用体验的是：即使事件里没有 `cwd`，我们仍能从**同一来源 + 同一会话 ID** 的后续事件识别“它是否属于之前人工选过的那条会话”。

## 四、先有任务合同，才允许绑定

如果用户还没有说清楚要做什么，那么“把事件连到任务”只会制造虚假的进度。我们已经在第 05、06 篇开发了 `task_contract.py`，其作用是让用户描述目标、保护路径以及要运行的独立验收命令，并为经过人工审核的合同保存哈希。

因此新 `bind` 命令强制要求两件事：**当前 Git 仓库存在基线、任务合同处于审核状态**。二者缺一个就拒绝绑定；这是为了防止所谓“自动识别任务”跳过用户目标这个最重要的依据。

新流程不重写原合同格式，也不重新开发一套测试系统，仍使用既有接口：`task_contract.load`、`task_contract.contract_hash`、`evidence.root_for`、`evidence.state_dir`。这些模块早已在仓库中存在，新的映射只是把它们连接起来。

回想一个真实反例：Codex 正在改某个项目，你临时更改了“不能修改 GOAL.md”的约束。如果 Watchdog 自动沿用旧的合同关联，它会以错误前提给你出结论。新模块会把批准合同时的哈希一起保存，后续需要重新审核，而不是默默换成新目标。

## 五、Windows 实操：先不要碰你已经跑通的全局 Hooks

一定记住上一轮的排错经验：你的 Windows Codex App 实际能工作的链路依赖已审核的**全局 Hook、commandWindows、ASCII .cmd 包装器**。第 34 篇不要求你重新安装任何 Hook，也不建议把老的项目级 `hooks.json` 再叠加回去。

先从最新 GitHub 克隆到没有旧文件的独立目录，并选择一次性的演示 Git 项目。使用 **Anaconda Prompt**：

```bat
conda activate torch_env
git clone https://github.com/colddreamxiaowd/Agent-Watchdog.git D:\program\Agent-Watchdog-v37-eval
cd /d D:\program\Agent-Watchdog-v37-eval
python -m unittest discover -s examples\v04\tests -v
```

如果目录已存在，换一个新目录，不要覆盖。详细创建基线、审核 Task Contract 的命令见 [第 34–37 篇上手指南](docs/ROUND4_TASK_LOOP_RUNBOOK.md)。重点是先建立 Git baseline、审核合同，再让 Codex App 开始修改演示仓库。

## 六、让 Watchdog 列出会话，而不是猜项目

打开 Codex App，在你的演示仓库内进行一次低风险工具操作后，再从 CMD 运行：

```bat
cd /d D:\program\Agent-Watchdog-v37-eval\examples\v04\watchdog
python app_task_watch_v37.py sessions
```

输出包含脱敏别名、来源标签、事件数以及最后观测时间。你要对照 **Codex App 界面中刚才发生的操作** 选出正确会话。

如果工具输出完全为空，可能是 Hook 未被正常信任、Codex App 与 CMD 使用不同 Windows 用户的数据目录，或者你看的只是另一个用户的日志。之前你遇到过 `LOCALAPPDATA` 指向两个目录的实际问题，所以新 CLI 提供 `--log` 显式指定由你确认的日志文件。千万不要为了让 `sessions` 输出非空，就随便从网络下载日志冒充现场证据。

## 七、只有明确授权才保存绑定

把刚才真正观察到的别名代入：

```bat
python app_task_watch_v37.py bind --repo "D:\Projects\watchdog-demo" --alias "REPLACE_WITH_ALIAS" --approve-binding
```

`--approve-binding` 是必须手动提供的参数，不会从 Hook 自动触发。这份绑定记录存放于用户私有数据目录中的 `task_bindings.json`，不是被 Codex 修改的仓库内部；文件中保留完整来源/会话标识和项目路径，所以不能公开分享。

代码还会检查“这个别名是不是之前已经绑定过”。已绑定会话不能不声不响改绑到另一个 Git 项目，这能避免把旧事件与新的合同混为一谈。它会保存合同哈希与 baseline 指纹。以后合同或基线发生变动，上一份关联不再自动获得信任。

一个重要限制是：这份绑定只能代表**人认为这个会话正在处理该仓库**，它没有通过 Hook 签名、App 官方身份 API 认证来源。用户仍应在界面里检查事件与会话是否对应，不要把这张表误认成防恶意篡改的审计证明。

## 八、反例比“成功绑定”更值得看

第一个反例是不提供 `--approve-binding`。程序会拒绝写入私人注册表。第二个反例是传入不存在或过旧的别名，绑定会拒绝，而不是把它指向最近的其他会话。第三个反例是合同没有审核或不存在 Git baseline，此时就算日志有成百上千条，也不会自动生成任务。

第四个反例是试图把绑定注册文件保存到被监督仓库内部，程序拒绝。我们希望保存“监督者的授权信息”，而不是把该授权文件暴露为 Agent 工作区里可随意改动的一个源文件。

最后一个反例最常见：两个 Codex App 项目在同一时间调用 Bash。Watchdog 应按来源与会话隔离这两组事件，而不是看到 Bash 就归为同一项目。我们为这些场景写了隔离单测，但它们不代表你的真实 App 已经跨所有会话通过了现场验证。

## 九、做到这里，才开始有真正意义上的任务监督

第 34 篇新增的不是一个好看的展示字段，而是整个监督系统的**任务归属条件**。有了它，下一篇才有资格把合同、Git 文件变化与独立验收状态放在同一个报告里。

我们至今仍然没有解决“语义上是否做对了所有要求”。但至少从现在起，Watchdog 在明确用户授权以后，可以把一个真实会话与一份具体目标挂钩，而不是只知道一些孤立的工具事件。

这一篇已经实现了可运行的会话列表、人工绑定、合同/基线哈希锚定和安全拒绝；真实 Codex App 会话 ID 是否稳定、长期身份认证与自动换任务识别仍待后续实测。

源码：[会话映射模块](examples/v04/watchdog/session_binding_v34.py) · [隔离测试](examples/v04/tests/test_round4.py) · [Windows 使用指南](docs/ROUND4_TASK_LOOP_RUNBOOK.md)。
