# 从零开发 Agent Watchdog（32）：第一版 Codex App 伴随监督器——今天能用到什么程度，如何真正上手？

> 第 32 篇 · Windows Codex App 实战总装 · 一键入口 · GitHub 交付 · 人工验收 · 发布边界  
> 这不是自动接管 Codex 的插件，也没有替用户完成 Windows App 现场测试；它是**用户可明确安装、运行、停止并撤回的外部伴随观察工具**。

## 一、经过 32 篇教程，我们到底在做什么？

刚开始开发 Agent Watchdog 的时候，你的愿望并不是研究“某个模型是否会卡住”这样一个孤立问题。你希望做一个真正属于自己的工程：Codex 接到任务以后，我不需要全程盯着它；它重复失败、可能绕圈、目标跑偏或者自称完成时，有一个**不依赖它自己说法**的观察者帮忙看一眼。

这个方向并没有因为我们参考 StepWise 的检测器而改变。StepWise 能帮助我们理解轻量风险信号，但它不是我们的产品本体。尤其你明确说，你使用的是 **Windows 的 Codex App**，所以第 29–32 篇把交付重点从“离线导入一份轨迹”转到“可以与你每天打开的 App 并排运行”。

我们现在有一条明确的最短路径：

```text
启动 Codex App                 启动 Agent Watchdog
选择一次性练习项目            独立 CMD 终端
        │                            │
        └── 项目级 Hooks（你审核） ──┘
                     │
              私有脱敏 JSONL
                     │
              SQLite 持久化
                     │
            失败聚集/缺终态提醒
                     │
                 Windows 气泡
                     │
                   你复核
```

这里的“你复核”非常关键：不是让 Watchdog 自动杀掉 Codex，不是把普通的三次 Bash 误认成无限循环，也不是让 Codex 自己改写你原来的任务合同。

## 二、与桌面 App 的关系：我们是伴随程序，不是 App 内部代理

如果说 Codex App 是执行任务的人，Watchdog 目前更像一个旁边拿着记录板的人：只看被授权的事件、保留时间和结果、指出需要你回头检查的迹象。

所以不要期待双击脚本以后，Watchdog 会自动出现一个悬浮窗覆盖所有 Codex App 项目，也不能期待它直接列出每一个 Agent 的完整聊天内容。我们没有使用 Codex 私有数据库，也没有在你的系统上安装全局键盘或屏幕监听。

**当前接入依赖你为每个被观察的项目人工审核 Hook。** 已有 Hook 的项目不会被安装器自动覆盖。Codex App 能否在你自己的版本和沙盒策略下执行这些项目级 Hooks，仍需要你的实机验证。这不是我们回避功能，而是没有真实运行证据就不能声称已经完成。

如果你未来希望无须逐项目安装、所有 Codex App 任务统一进入一个监督台，可能需要进一步研究受支持的桌面插件生命周期 Hooks、项目外部身份映射或其他官方接口，并单独处理多项目权限与数据隔离。现在不越过这道信任边界。

## 三、把四篇源码汇成一条可以复制的命令

第 29 篇带来 `app_hook_v29.py` 与 `app_setup_v29.py`，负责 Hook 数据采集和安装提案；第 30 篇的 `app_watch_v30.py` 实现 SQLite 事件处理和可选通知；第 31 篇的 `app_recovery_v31.py` 提供健康检查和显式备份。

为了让你不用记住五六个文件名，我们增加 [app_control_v32.py](examples/v04/watchdog/app_control_v32.py)，提供几个统一子命令：

| 子命令 | 意义 | 是否需要你授权或介入 |
|---|---|---|
| `doctor --repo PATH` | 检查目标路径和配置位置 | 不安装、不证明已接通 |
| `propose --repo PATH` | 打印准备使用的 Hooks | 仅供审阅 |
| `install --repo PATH --ack-reviewed-hooks` | 只创建新的配置 | 需要你明确同意，拒绝覆盖 |
| `watch --notify` | 前台持续观察新事件 | 通知仅表示建议检查 |
| `status` | 本地 SQLite 与日志健康检查 | 不检测 App 进程是否活着 |
| `backup` | 保存私有一致性备份 | 不自动恢复/重放 Codex |

你可以先不启用任何通知，仅用 `watch` 打印 JSON 形式的检查结果；如果不希望终端刷屏，未来可以增加更安静的本机 UI，但本轮优先确保每个告警有来源和去重。

**所有这些能力都不需要训练模型，也不要求你提供 OpenAI API Key。** 只有 Codex App 自己的正常登录和权限由你按照官方流程管理。

## 四、真正使用前，先保护你现有的项目

你的原工程和研究仓库可能很重要。最危险的不是一个单元测试不通过，而是为了试用 Watchdog，把一个正在使用的 Codex App 项目里原有 Hooks 改坏了。

所以我们从全新克隆与空白练习项目开始。打开 **Anaconda Prompt**：

```bat
conda activate torch_env
git clone https://github.com/colddreamxiaowd/Agent-Watchdog.git D:\program\agent_watchdog\Agent-Watchdog-app-eval
cd /d D:\program\agent_watchdog\Agent-Watchdog-app-eval
python -m unittest discover -s examples\v04\tests -v
```

若目标路径已经存在，请改用新路径；不要在现有目录直接执行新克隆。

然后新建一个一次性 Git 目录，并用 `app_control_v32.py doctor` 检查。这一步的完整命令已经写进 [Codex App Quickstart](docs/CODEX_APP_QUICKSTART_29-32.md)，不会在正文里替你假装它已执行。

配置分两步：

```bat
cd /d D:\program\agent_watchdog\Agent-Watchdog-app-eval\examples\v04\watchdog

python app_control_v32.py propose --repo "D:\program\agent_watchdog\watchdog_app_demo"
```

你检查输出里所指的 \`python.exe\` 和 \`app_hook_v29.py\` 确实属于新克隆，且是你愿意信任的代码，然后才运行：

```bat
python app_control_v32.py install --repo "D:\program\agent_watchdog\watchdog_app_demo" --ack-reviewed-hooks
```

若安装提示配置已存在，不要再添加“强制覆盖”参数——当前程序故意不提供这种参数。请打开文件自己确认它是否来自别的工具，优先在全新练习仓库测试，而不是混合未经审查的多个 Hooks。

## 五、真正的现场验收发生在 Codex App 里

现在打开 **Windows Codex App**，选择 \`watchdog_app_demo\` 测试项目，查看你当前版本的 Hook 加载/信任情况。然后用 App 的正常聊天窗口让 Agent 写一个 `add(a,b)` 函数并自己实际运行最小验证。这是**真正的 App 操作**，不是我们在 Python 单元测试里调用 `from_hook(...)` 构造的一条假记录。

请在 App 开始任务之前，另开一个 Anaconda Prompt，进入观察器源码目录：

```bat
python app_control_v32.py watch --notify
```

或者在有 Python 可用的 Windows 环境下双击 [START_CODEX_APP_WATCHDOG.cmd](examples/v04/watchdog/START_CODEX_APP_WATCHDOG.cmd)。它仅启动 Watchdog 观察器，**不会帮你打开或控制 Codex App**。

正确的验证不是看到“脚本运行起来”就打勾，而是核对两边：App UI 显示该练习任务执行过某个工具；新产生的私有 `events.jsonl` 确实包含时间上对应的 Hook 事件；你在 Watchdog 端能够看到新的事件计数。还要留意 App 中可能存在未覆盖的执行工具，不要拿一条成功事件概括所有路径。

如果仅能在 CLI 中触发 Hook，而 Windows App 完全没有触发，本轮真实 Codex App G1 就依旧是 `NOT_VERIFIED`。可以据此调整兼容方案，但不能换一个说法把它写成通过。

## 六、你可以把监控窗口关掉，不用怕 Codex 一起关闭

这一点是外部伴随工具和“把 Agent 启动为观察器子进程”的重要区别。当前 Watchdog 不负责启动 Codex App，自然也不会持有它的运行进程句柄。你关闭监控终端，App 仍属于自己的应用进程。

下次要继续观察时，再打开：

```bat
python app_control_v32.py watch --notify
```

SQLite 会让它记住已处理事件、警报和冷却时间，而不是仅用某个临时全局变量维持状态。第一次启动默认不回放旧告警，重新打开后继续处理新增完整行。但注意：如果监控器关闭期间错过了系统通知，并不能因此证明用户已收到；数据库记录与系统气泡显示之间仍需要未来更强的投递确认机制。

想检查当前私有状态：

```bat
python app_control_v32.py status
python app_control_v32.py backup
```

第二条会保存 SQLite 备份，不会自动恢复、重跑任务，也不会把任何数据上传网络服务。你应该把这个备份视为个人工作资料，即使它不包含完整命令，也不要公开分享。

## 七、这个版本究竟能干什么？也不能干什么？

**可以实际试用的工程功能**：在用户审核、App 版本实际加载 Hook 的条件下，保守收集生命周期元数据；通过统一入口从终端查看事件；对明确失败聚集或缺终态事件提示人工复核；防止普通日志重读导致重复通知；保存私有 SQLite 状态和备份。

**还不能保证的能力**：覆盖所有 Codex App 执行路径，实时知道每个模型内部在想什么，准确判断所有死循环，用 StepWise 自动给当前 App 的任务贴标签，可靠判定语义偏离，自动证明用户任务已经完成，以及在所有 Windows 休眠/网络波动环境中不漏报。

尤其“默认不采集命令与输出”是一个有意的隐私约束。这意味着 Watchdog 可以对“同一工具类别有多次明确失败”进行弱复核，却不能凭空知道这三次是否执行了同一条命令。我们不应该为了展示一个漂亮的“智能检测 99%”而偷偷改变采集范围。

## 八、四道必须认真完成的现场门槛

**第一道：Codex App 接入 G1。** 你真正操作 App 并核对 Hook、私有事件、时间和工具对应关系，记录 App 的版本与安全设置。这一步未做，不能称为 App 已接通。

**第二道：负例与误报 G3。** 在真实、经允许的操作里，至少关注六次合法 Bash、两项互不相干的失败、App 休眠/无 Hook 等负例。后续再通过人类标注评估告警是否有价值，而不是拿模拟数据计算准确率。

**第三道：长期可靠性 G4。** 观察 Windows 关窗口、重启、合盖、继续运行、通知权限关闭、日志截断与备份恢复时能否保留正确的状态。我们的合成单测只是这里的起点，不是这条门槛本身。

**第四道：原始任务是否完成。** Watchdog 的核心目标终究不只是检测执行过程，还要把用户一开始的目标、保护范围和独立验收结果关联起来。这一点依赖第 05–06、24、27–28 篇的人类 Task Contract 和验收机制。**当前伴随程序尚未自动把 Codex App 任务对应到批准的合同**，不能说产品全功能闭环已经做完。

## 九、这一轮的发布结论：允许个人试用，但不应当宣称正式完成

写到第 32 篇，我们已经能提供一份自包含的、主要使用 Python 标准库的 Codex App 旁路观察原型：用户可审核配置、明确安装、前台运行、退出、查看状态、备份和撤回。和第 20 篇所谓的“教程收官”相比，这一次至少把“实际使用的 App 客户端”拉进了设计目标。

但正式产品依然缺三类证据：你真实 App 的 Hook 覆盖率、真实标签的检测有用性、跨天使用的可靠性。任何一项没有通过，都应该维持相应 Gate 未验收，而不是把我们的章节数改成 V1.0 的许可证。

如果你现在就要开始试用，最有效的行动不是让 Codex 连续跑一个大研究项目，而是先用**一次性练习仓库**完成一条真实的“App 操作 → 本机新 Hook 事件 → Watchdog 输出”。这个最小闭环一旦真实通过，再把监控逐渐放到你愿意授权的正式项目里。

至此第 29–32 篇的源码、单元测试、Windows 安装清单与回退流程是可复查的工程交付。下一阶段真正该优先做的是收集真实 App 兼容性结果，把不同工具的 Hook 覆盖差异、通知漏报和人类验收问题逐一修复，而不是无止境地添加教程。

工具：[app_control_v32.py](examples/v04/watchdog/app_control_v32.py) · [Codex App 完整试用指南](docs/CODEX_APP_QUICKSTART_29-32.md) · [第 29–32 篇测试记录](docs/ROUND3_TEST_REPORT.md) · [GitHub 项目 README](README.md)。
