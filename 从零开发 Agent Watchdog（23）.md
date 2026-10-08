# 从零开发 Agent Watchdog（23）：五分钟没动静就是卡死？设计不会乱报警的运行监督状态机

> 系列教程 · 第 23 篇｜异常检测 · 状态机 · 失败聚集 · 时钟 · Windows 休眠  
> 这是一套**保守、未在真实 Codex 轨迹上校准**的监督规则，不是已经验证准确率的 Stuck Detector。

## 一、昨天 Codex 很忙，今天它突然安静了

想象你把一个较长的任务交给 Codex，然后去吃饭。过了一段时间，你发现终端没有输出。一个简单的监督脚本可能写：

```python
if seconds_since_last_event > 300:
    print("STUCK!")
```

看似合理，但至少会误伤四种完全不同的情况：模型正在长时间推理；工具运行很久且暂时没有可见输出；Codex 使用的工具根本不经过我们配置的 Hook；Windows 进入睡眠，程序没有机会观察任何东西。更糟糕的是监控器自己崩掉或日志满磁盘，也可能让记录停住。**没有数据，最先应该怀疑的是“我们不知道”，而不是“Agent 肯定死了”。**

第 23 篇要教会 Watchdog 使用证据等级，而不是给沉默贴标签。

## 二、如何用一个小表格区别三种看起来相似的现象？

| 真实可观察情况 | Watchdog 该说什么 | 为什么 |
|---|---|---|
| 只看到某个配对操作开始，经过阈值仍没见终态 | `SUSPECTED_STALL` | 可怀疑悬挂，但也可能是日志丢失/睡眠/正常长任务 |
| 最近根本没有新事件，也看不到有效进行中的配对操作 | `NO_OBSERVATION` | 不知道 Agent 是否在工作 |
| 某次调用明确报告非零退出码或 failed 状态 | `FAILED` | 这是报告的具体失败，不等于所有任务失败 |
| 同一会话多个不同操作有明确失败 | `FAILURE_CLUSTER_REVIEW` | 可提醒人工检查，但不证明正在重复**同一条**命令 |
| 事件最新且没有上述异常证据 | `OBSERVING` | 仅表示观测正常，绝不是“项目已完成” |

你可能问：为什么不再加一个状态 `STUCK_CONFIRMED`？因为我们还没有可验证的外部进程心跳、模型推理状态、端到端覆盖和真实标注。**缺少必要证据时，最正确的状态就是没有这个状态。**

## 三、程序如何区分“一个没结束的工具”和“一段安静的时间”？

完整实现放在 [runtime_v2.py](examples/v04/watchdog/runtime_v2.py)。和第 22 篇一样，我们优先看结构化事件，而不是解析中文日志正文。

整体算法：

```text
读取脱敏事件 → 检查时间戳有效、剔除未来时钟
    ↓
按 (source, session_id, turn_id, tool_use_id) 分组
    ↓
同一组内部：启动/更新/结束去重、检查冲突
    ├─ 存在明确 FAILED → 记录失败（可人工查看）
    ├─ 同一调用有相矛盾终态 → CONFLICTING_TERMINAL
    ├─ 只见完成、不见开始 → ORPHAN_TERMINAL
    └─ 有开始没结束且超过阈值 → SUSPECTED_STALL
    ↓
最近没有任何事件 → 另记录 NO_OBSERVATION
    ↓
返回“可解释风险”，不自动触发重试/杀进程
```

其中 `SUSPECTED_STALL` 的判定只允许一个清楚的输入条件：确实看到某个**有稳定操作 ID** 的开始事件，且始终未见配对结束。阈值 `stall_seconds` 不是统计学习得到的通用五分钟定律。它是你可以按任务性质调节的**提醒复核等待时间**。构建大型 C++ 项目的工具，和一条瞬间完成的 `echo`，不能用相同的阈值解释为同样严重的故障。

示例实现的关键判断：

```python
age = (now - last_time).total_seconds()
if age >= stall_seconds:
    incidents.append({
        "kind": "SUSPECTED_STALL",
        "certainty": "SUSPECTED_NOT_CONFIRMED",
        "seconds_since_observation": int(age)
    })
```

这里真正的意义是“距离上次可观测信息已经过去多久”。**它不知道中间实际发生了什么**。因此我们把提示命名为 `SUSPECTED`，并提供来源、会话和调用 ID，方便你回来核对。

## 四、为什么不能按“同一会话连续六次 Bash”定义循环？

写一个 Python Web 项目时，你可能按顺序执行：

```text
Bash  python -m unittest
Bash  git diff --check
Bash  python -m compileall
Bash  git status
Bash  python build.py
Bash  git status
```

这六次都属于 Bash，但做的事情不同，而且每一步都可能推进目标。若系统仅看到六个“Bash”就宣布无效循环，用户只会越来越不信它。

新版规则只针对 **明确失败、具有不同调用 ID、又落在同一来源/会话/工具类别** 的多次操作产生 `FAILURE_CLUSTER_REVIEW`。即便满足这个条件，它仍不够证明“重试了同样的命令”。例如一次任务可能有三个不同的失败测试，它们都返回非零码，实际上是在逐个发现缺陷。

这也是本轮比第 17 篇 `POSSIBLE_REPETITION` 更有用的地方：旧规则只是低置信度的工具类别重复提醒；新规则至少需要明确的失败结局。但“能观察多个失败”不等于“理解了失败原因”；真正的相同修复尝试识别要等第 25 篇，在隐私、授权与标注约束下才能讨论。

## 五、如何证明我们不是靠打印信息自我感动？

实验 A：没有任何事件。

```python
assert runtime.diagnose([], now=now)["state"] == "NO_OBSERVATION"
```

如果得到 `SUSPECTED_STALL`，说明只靠沉默就判卡住，本章不能通过。

实验 B：某个工具 400 秒前开始、调用 ID 清晰，但之后没有对应完成：

```python
{"phase": "STARTED", "tool_use_id": "op-A", "linkable": True, ...}
```

在阈值 300 秒时预期有 `SUSPECTED_STALL` 和 `SUSPECTED_NOT_CONFIRMED`。这只是人为构造的案例，**不能拿它证明真实检测准确率**。

实验 C：六个不同工具调用都显示正常退出。不能出现 `FAILURE_CLUSTER_REVIEW`。

实验 D：会话 A 和 B 各有两次失败。程序不能把四次合并为同一个“失败循环”。

实验 E：一个调用出现两种互相矛盾的结束结果。应标记 `CONFLICTING_TERMINAL`，而不是“最后出现的肯定是真相”。

实验 F：当前时间比记录时间更早。程序记录 `invalid_or_future_time`，避免一条乱时钟制造夸张的停滞时长。

这些对照已写成 [第 23 篇回归测试](examples/v04/tests/test_round1.py)，默认不需要 GPU、StepWise，也不连接网络。

## 六、你可以在 Windows 上直接看到 JSON 风险解释

在 Anaconda Prompt 中执行（先完成第 21 篇源码的安全检出）：

```bat
cd /d D:\program\agent_watchdog\Agent-Watchdog-v2-eval\examples\v04\watchdog
python runtime_v2.py --events logs\events.jsonl --stall-seconds 300 --quiet-seconds 300
```

这是**一次性快照诊断**，不是自带 Windows 服务的持续后台通知。你可以用已存在的 Bridge 与显示面板观察日志更新；第 29 篇才去设计系统级通知、冷却、人工确认，不能提前宣称桌面推送完成。

还可以用 Python 自带单元测试的可重放合成事件验证逻辑：

```bat
cd /d D:\program\agent_watchdog\Agent-Watchdog-v2-eval
python -m unittest discover -s examples\v04\tests -p test_round1.py -v
```

没有新事件的情况，依然不会得出“Agent 仍正常运行”，只能得出 `NO_OBSERVATION`。`FAILED` 对应某些明确报告失败的调用；不表示用户任务已宣告失败。

## 七、Window 休眠、进程重启、消息乱序：时钟并不是魔法

程序现在使用时区感知的接收时间 `received_at`。这能避免把 UTC 与本地时间直接混用，但不是单调时钟（monotonic clock）。系统休眠后重新唤醒，墙上时钟会向前跳很多；如果有未结束操作，就可能触发 `SUSPECTED_STALL`。这**只能要求人工看一眼**，不能据此判断 CPU 卡死。

第二个问题是重启：程序如果仅扫描日志末尾，可能丢失历史开始事件；SQLite 账本虽然有断点续导，轮转与异常断电的覆盖尚需第 31 篇的真机测试。第三个问题是乱序：我们只根据稳定操作 ID 分组，完全不允许把不同会话或不同调用按行号强行配对。

还有一个值得保留的负面原则：没有权限去读取的内容，就不要为了追求漂亮的准确率而偷偷采集。我们的基础检测器宁愿承认 UNKNOWN，也不要把用户私人代码输入一套未经验证的外部服务。

## 八、参考现成的 Windows 开源项目，而不是复制其危险假设

[Codex Task Watchdog](https://github.com/TanChuping/codex-task-watchdog) 已考虑后台流、长时任务、Windows 原生提醒等问题，也把本机数据库访问限定为只读。它处理的一些信号比我们当前的 Hook 元数据丰富。但它对特定 `logs_2.sqlite` / `state_5.sqlite` 的兼容性依赖意味着：是否能迁移到你的 Codex 版本，必须先独立检查其当前许可证、平台支持和运行效果。

本轮因此只复用思路与标准库：`datetime` 做时间比较，`collections.defaultdict` 做分组，SQLite 使用既有 `journal.py`。不为了借一个“卡住”功能就把另一个项目的后台自动恢复、安装器和数据库解析统统塞进来。

## 九、第 23 篇的验收与下一道坎

本篇交付的是**有解释、有来源、会承认未知的运行异常提示原型**。它可以在合成事件上验证：不以无事件证明卡死、不以六次 Bash 证明循环、不会合并跨会话失败、有明确终态才报失败。

它还没有经过真实轨迹的人工标注，不知道对你常用的长任务误报多少次、漏报多少次，也没有经过 Windows 休眠后长期运行的覆盖测试。故 G3 仍未通过。这些边界不能靠增加几个阈值或者一个 AI 模型掩盖。

下一篇要把“发生过这些操作”与“用户任务实际推进到哪一步”连接起来：**一个成功的 Bash 调用，不应该平白变成任务完成百分比。**

源码：[runtime_v2.py](examples/v04/watchdog/runtime_v2.py) · [能力边界](docs/CAPABILITY_MATRIX.md)。

