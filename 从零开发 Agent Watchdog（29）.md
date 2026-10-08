# 从零开发 Agent Watchdog（29）：这一次真的对接 Windows Codex App，而不是把 CLI 日志当成 App 事件

> 第 29 篇 · Windows Codex App · 项目级 Hooks · 权限审核 · Python 脱敏观察器  
> 本篇完成**可供本人实际安装的接入方案**，但不能代替本人在 Codex App UI 中完成真实联调。

## 一、你问出了比“再写四篇”重要得多的问题

我们的 GitHub 仓库有了 28 篇博客、几十项隔离测试，但你真正使用的不是 \`codex exec --json\`，也不总是在 CMD 中启动 \`codex\`。你平时打开的是 **Codex App 的 Windows 桌面界面**：直接选择项目、和 Agent 聊天、并行跑多个任务。

那么前 28 篇写的 Watchdog，能不能观察这些任务？

回答必须分成两句：**官方提供 Hook 接入点；我们原来的测试还没有证明你的 Codex App 确实调用过那些 Hook。** 这是一个工程问题，不是再换一个 AI 模型就能解决的分类问题。

官方 [Codex App](https://openai.com/index/introducing-the-codex-app/) 已有 Windows 版本；[Hooks 文档](https://developers.openai.com/docs/hooks)列出了 \`SessionStart\`、\`PreToolUse\`、\`PostToolUse\`、\`Stop\`、\`SessionEnd\` 等生命周期事件，并说明可用 JSON/TOML 配置本地执行程序，以及未经信任的配置需要审核。我们可以把 Watchdog 做成一个**外部伴随观察器**，不修改 Codex 内核，也不尝试窥探它的私人会话数据库。

但这不表示不同版本、不同沙盒、不同工具路径会发出相同事件。兼容性要在你的实际 Codex App 中确认。

## 二、选择最小侵入方案：项目级 Hook + 独立观察程序

直接“接管 Codex App”听起来很厉害，却未必是好选择。我们不需要让 Watchdog 取代 Codex 的运行器、修改它的权限逻辑、读取其私有 SQLite，也不需要自动点击界面。

真正合适的架构是：

```text
Windows Codex App
      │
      ├─ 你原本的项目与任务（继续使用）
      │
      └─ 生命周期 Hook（需要你审核并信任）
                  │  stdin JSON
                  ▼
        app_hook_v29.py
          只摘取允许字段
          丢弃命令/提示词/输出
                  │
                  ▼
      %LOCALAPPDATA%\AgentWatchdog\events.jsonl
                  │
                  ▼
        app_watch_v30.py（下一篇）
          独立进程显示/提醒
```

这里最关键的设计：**Watchdog 的监控窗口关掉，不应该连带关闭 Codex App。** Hook 即使因为某次写文件失败，也应该结束返回一个不干预 Codex 的空 JSON 对象。

我们只使用 Python 标准库，避免你为了装一个小观察器被迫安装深度学习、CUDA、模型检查点。原来 \`torch_env\` 可以继续用，但此处实际不依赖 GPU。

## 三、为什么我们要写新 Hook，而不是照搬第 21 篇？

以前的 [execution_v2.py](examples/v04/watchdog/execution_v2.py) 已经会处理 \`PreToolUse\` 与 \`PostToolUse\` 的有限字段；它的默认输出放在教学项目里的 \`logs/events.jsonl\`。这对实验方便，但真实 Codex App 的项目可能在另一个目录；长时间使用时，我们不希望某个工程项目的仓库顺便包含监督日志。

第 29 篇只写一个很薄的 [app_hook_v29.py](examples/v04/watchdog/app_hook_v29.py)：底层重用 \`execution_v2.from_hook\` 与 \`hook_logger_v04.append\`，不重新定义成功/失败、不重新发明日志格式。它把日志改放在当前 Windows 用户的 \`%LOCALAPPDATA%\AgentWatchdog\events.jsonl\`，并默认将 \`cwd\` 设置为 \`null\`。

这有两个理由。一是你会在学习、研究、个人项目之间频繁切换，绝对目录本身可能泄露项目名和个人资料。二是 Codex Hook 的 \`tool_input\` 可能包含所有命令参数，\`tool_response\` 也可能有机密错误日志。**监督器不等于日志搬运工**，我们只应该保存为判断提供必要证据的最小字段。

核心函数的意思可以简化为：

```python
data = json.loads(raw_hook_json)
row = from_hook(data)          # 只采白名单字段
row["cwd"] = None             # 默认不保存工作区路径
append(row, local_event_path) # 不保存原始 JSON
```

务必看清楚：这段是源码逻辑摘要，完整异常处理与大小限制在仓库文件里。面对无法解析的 Hook 输入，程序选择忽略并返回空 JSON，**不会试图判断工具成功或失败**。

## 四、在 Windows 上安装前，先看生成出来的配置

Hook 是程序执行权限的一种入口，哪怕我们只打算观察，你也应该亲自看到会执行哪个解释器、哪个脚本。不能因为这是我写的，就自动跳过信任审核。

[app_setup_v29.py](examples/v04/watchdog/app_setup_v29.py) 和 [app_control_v32.py](examples/v04/watchdog/app_control_v32.py) 支持两阶段流程：先提案，后明确安装。第一次使用请在新的测试目录，不要拿你正在做科研的仓库直接尝试。

在 **Anaconda Prompt（CMD）**：

```bat
conda activate torch_env
git clone https://github.com/colddreamxiaowd/Agent-Watchdog.git D:\program\agent_watchdog\Agent-Watchdog-app-eval
cd /d D:\program\agent_watchdog\Agent-Watchdog-app-eval
python -m unittest discover -s examples\v04\tests -v
```

接着单独创建一个用于 App 练习的 Git 仓库：

```bat
mkdir D:\program\agent_watchdog\watchdog_app_demo
cd /d D:\program\agent_watchdog\watchdog_app_demo
git init
git config user.name "Watchdog Fixture"
git config user.email "fixture@example.invalid"
echo Disposable task> GOAL.md
git add GOAL.md
git commit -m "Initial fixture"
```

此处明确约束：如果目录已经存在，不要照抄覆盖或把原有仓库当一次性环境。

然后回到观察器：

```bat
cd /d D:\program\agent_watchdog\Agent-Watchdog-app-eval\examples\v04\watchdog
python app_control_v32.py doctor --repo "D:\program\agent_watchdog\watchdog_app_demo"
python app_control_v32.py propose --repo "D:\program\agent_watchdog\watchdog_app_demo"
```

\`doctor\` 报告目标项目、目标配置路径、观察日志路径；\`propose\` 打印将要写入的 \`hooks.json\`。**这两个命令都不会安装 Hook**。

## 五、为什么配置里要使用绝对 Python 路径？

你在 Anaconda Prompt 中运行 \`python\` 没问题，不代表 Windows 桌面 App 进程继承了同一个环境变量 \`PATH\`。如果 Hook 配置只是 \`python script.py\`，App 启动的环境可能找不到对应 Python，甚至找到另一个版本。

本篇的配置生成器采用你实际运行它时的 \`sys.executable\`，也就是 Python 的完整路径；脚本也使用完整路径。你在 \`propose\` 输出里能直接检查它们。

脚本将产生包含五类生命周期事件的 JSON。请特别注意 \`SessionEnd\` 的超时设置短于其他 Hook，符合官方 Hooks 的特殊超时边界。这次配置**不会自动覆盖任何已有的 \`.codex/hooks.json\`**。

如果你确认测试仓库没有原来的 Hook，审阅无误后才执行：

```bat
python app_control_v32.py install --repo "D:\program\agent_watchdog\watchdog_app_demo" --ack-reviewed-hooks
```

这里的 \`--ack-reviewed-hooks\` 不是装饰，而是防止误触执行。程序以排他创建方式写入，只接受新文件；路径已存在或符号链接异常时直接拒绝。

## 六、现在轮到真正的 Codex App，不是 CLI

打开 **Windows Codex App**，选择刚才的 \`watchdog_app_demo\` 项目。在 App 里查看你的版本是否加载了这个项目级 Hook，以及是否需要信任审核。只对你亲眼检查过的配置授权。**不要为了让 Hook 跑通就关闭应用沙盒或绕过 Hook 信任。**

在 Codex App 内发送：

> 只在当前测试仓库创建 add.py，定义 add(a,b)，通过实际 Python 调用验证 add(2,3)==5。不要修改 GOAL.md，也不要读取其他私人文件。

另开一个 PowerShell 查看日志：

```powershell
Get-Content "$env:LOCALAPPDATA\AgentWatchdog\events.jsonl" -Tail 10 -Wait
```

如果日志不存在或者只有以前手工模拟的数据，此时不能算成功。必须对照 App UI 中**同一次**任务的时间、会话和实际工具调用，发现新的对应 Hook 记录。App 如果使用了不被当前 Hook 支持的特殊执行路径，那也应该如实记录。

更全面的现场验收步骤放在 [Codex App 专用工作单](docs/CODEX_APP_QUICKSTART_29-32.md)。

## 七、三种反例决定它能不能被信任

**反例一：你在命令行自己打印了一条 Hook JSON。** 观察器会把它保存下来。这只能证明我们的数据采集函数正常，不能证明 Codex App 真的触发。日志里的 \`source=hook_input_unverified\` 不是密码学认证。

**反例二：App 调用了 Bash，但是没有明确 exit_code。** 即使收到了 \`PostToolUse\`，\`outcome\` 也必须保留 \`UNKNOWN\`，不能用“Tool 已返回”推断“任务成功”。

**反例三：项目已有其他 Hooks。** 安装程序不覆盖、不自动合并，避免误删你已经存在的安全检查或审批机制。此时应该另建空白测试仓库人工测试，再设计有充分审查的多 Hook 共存方案。

如果出现 App 无法写入 \`%LOCALAPPDATA%\` 的沙盒限制，那是尚未通过的兼容性条件，不应该通过无限放大 Codex App 权限来绕开。不要把“能让它工作”看得比用户机器安全更重要。

## 八、第 29 篇做成了什么？

我们终于把关注点从“在实验目录模拟事件”转向了“用户可以在 Windows Codex App 项目里**显式安装**的只读观察入口”。

完成的是真实可执行的配置生成、最小化 Hook 接收器和安全安装原则；**未完成的是你这台 Windows 上 Codex App 的 G1 现场认证**。这件事只能由本机实际会话证据完成，GitHub 的 Windows 测试不能替代。

下一篇把“收到事件”进一步做成“能提醒你，但不会因为重启而刷屏”的日常使用体验。你不会再需要一直盯着 \`events.jsonl\`。

源码：[Hook 接收器](examples/v04/watchdog/app_hook_v29.py) · [配置工具](examples/v04/watchdog/app_setup_v29.py) · [Windows 真实使用步骤](docs/CODEX_APP_QUICKSTART_29-32.md)。
