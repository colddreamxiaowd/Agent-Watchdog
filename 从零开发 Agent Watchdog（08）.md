# 从零开发 Agent Watchdog（08）：从三个终端到监督工作流——让你真正看得懂 Agent 的进度

> **系列教程 · 第 8 篇** · Rich · 状态面板 · 人工确认 · 只读监督  
> 本篇重在设计一套你愿意每天打开的工作流，而不是忙着堆更炫的 UI。

第 04 篇你打开了 Bridge 与 Rich 面板，第 05 篇批准了合同，第 06 篇完成了独立测试，第 07 篇出现了风险提示。功能已经不少，但如果用户每次都得记住六七条命令，这个项目就很难成为日常软件。

真正需要的不是“十个炫酷面板”，而是打开以后回答四个问题：**这个项目是什么？它现在有什么可信进度？哪些要求还没得到证明？我需要干预什么？**

## 一、想象一个不应该存在的界面

```text
AGENT WATCHDOG

Agent confidence: 99%
Progress: 100%
Status: FINISHED
Risk: GREEN
```

如果这些数字来自 Agent 的自述、工具调用次数或未经校准的模型判断，界面虽然很漂亮，却可能把用户带进错误决策。

相反，我们宁愿显示：

```text
AGENT WATCHDOG — hook_demo

最近事件：PostToolUse / Bash
Git：hello.py 已修改
保护文件：未观察到变化
任务合同：已批准
验收 A1：PASSED
验收 A2：STALE

结论：目前无法证明全部验收条件满足
建议：复核修改后，显式重新执行 A2
```

这个界面不是“没那么智能”，而是**把信息含义设计正确了**。

## 二、复用第四篇的 Rich 面板，而不是另做一个 Web 服务

你已经有一个 `monitor04.py`。它持续读取 Bridge 保存的 `bridge_report.json`，并查看最近一小段脱敏 JSONL 事件，使用 Rich 的 `Live` 每秒刷新一次。

```python
with Live(screen(repo), refresh_per_second=2) as live:
    while True:
        time.sleep(1)
        live.update(screen(repo))
```

`refresh_per_second=2` 不等于每秒去后台扫描 Git 两次。真正的 Git 扫描仍由 Bridge 控制。UI 与昂贵操作分离，就是为了降低资源消耗。

此时最重要的交互不是点一个“自动修复”按钮，而是让用户可以从当前状态进入对应的**检查命令**。

## 三、统一命令行：status、alerts 和 handoff

为了让 v0.8 形成一个可用入口，我们新增 [`watchdog_cli.py`](examples/v04/watchdog/watchdog_cli.py)。注意，它是**只读报告工具**，不是 Agent 执行代理。

查看综合状态：

```bat
cd /d D:\program\agent_watchdog\watchdog
python watchdog_cli.py --repo "D:\program\agent_watchdog\hook_demo" status
```

查看风险：

```bat
python watchdog_cli.py --repo "D:\program\agent_watchdog\hook_demo" alerts
```

生成可交接的 Markdown 摘要：

```bat
python watchdog_cli.py --repo "D:\program\agent_watchdog\hook_demo" handoff --out "D:\program\agent_watchdog\handoff_v08.md"
```

输出目录位于被监控 Git 仓库外，避免报告本身改变 Git 指纹。生成的 Markdown 包含：仓库、最后扫描、当前合同状态、各项验收结果、已观察风险，以及下次继续时要做的事项。

注意：我们**没有将工具命令参数和工具响应原文**写进这个交接文件，这可以降低敏感内容泄露风险。但 Git 路径、目标描述仍可能包含个人项目名称，发布前要人工审核。

## 四、“用户确认”为什么不能等于“任务完成”？

假设你看到保护文件告警，检查后发现是自己有意修改了 `GOAL.md`。你可以在将来为它标记“已阅读”。但这种确认只能表示“我看到了”，不能把当前文件变化从 Git 历史中抹掉，更不能让未执行的 A2 测试自动通过。

因此我们区分三个操作：

```text
acknowledge: 我知道这个提醒了
verify: 我明确要求运行一项受信任的验收
approve contract: 我确认这是新合同
```

它们改变不同状态，绝不能混成一个“绿色已完成”按钮。

**当前示例代码尚未实现持久的 acknowledge 按钮，也没有桌面通知或邮件推送。** 第 08 篇做的是统一查询和导出交接摘要。把计划功能写成已实现，会让之后排错非常痛苦。

## 五、做一次完整演练：从 Codex 声明到人工决策

你可以按下面这个顺序完成实验：

1. 使用第五篇的 `claim` 记录“Agent 表示完成”；
2. 修改 `hello.py`，使某一项测试证据过期；
3. 运行 `bridge.py --once` 获取最新 Git 状态；
4. 用 `watchdog_cli.py status` 查看合同是否仍然 VERIFIED_COMPLETE；
5. 用 `alerts` 查看实际提醒，再决定是不是需要重跑 A1/A2。

正常的观察应该是：**声明已经记录，但独立验收状态会因文件指纹变化而退回未验证。**

这才是一个真正监督系统应该具备的“不会轻信”。

## 六、为什么默认不允许 Watchdog 自动 kill / retry / rollback？

这不是“做不到”，而是我们在工程初期刻意划定权限边界。

如果监督器误判 Codex 卡住并自动 kill，可能造成任务中断；如果它根据老旧证据自动 rollback，可能删除你在 IDE 中手动做的修改；如果它自己不断 retry，还可能与主 Agent 形成两个相互影响的循环。

所以 V0.8 的角色是：**观察、解释、提醒、保存证据**。任何可能改动代码或执行任务的控制动作，都需要额外的授权与隔离机制。

## 七、日常使用时应该开什么窗口？

你可以只开两个终端，一个持续运行 Bridge，一个运行 Rich 面板；第三个终端只在需要执行测试或查看合同状态时开启。

**终端 A**：

```bat
python bridge.py --repo "D:\program\agent_watchdog\hook_demo"
```

**终端 B**：

```bat
python monitor04.py --repo "D:\program\agent_watchdog\hook_demo"
```

当某个验收过期时，人工启动 `task_contract.py verify A2`。关闭 A/B 终端不会向 Codex 发出停止请求，但 Bridge 关闭期间也就不会持续更新证据；这一点需要在界面中如实显示。

## 八、它离产品还差哪些关键能力？

目前仍有很明显的短板：Bridge 重启可能丢失中间事件；Rich 最近窗口不能回看整天历史；多个会话的准确关联仍有限；`cwd` 无法证明哪个进程修改了文件；风险规则没有真实标注数据校准；合同也没有独立的安全边界。

这就是下一阶段的重点。与其现在就做漂亮 Web UI，不如先把**数据可靠性与恢复能力**做扎实。

本篇验收标准：能够从统一 CLI 看状态、风险和生成交接；不会把 `claim` 等同于验收；关闭界面不影响 Codex；不偷偷执行测试或恢复动作；能指出交接报告不是完整审计记录。

下一篇：《从零开发 Agent Watchdog（09）：把事件存进 SQLite，让重启不再意味着忘记》。

参考：[Rich Live](https://rich.readthedocs.io/en/stable/live.html) · [SQLite](https://sqlite.org/docs.html) · [完整统一 CLI](examples/v04/watchdog/watchdog_cli.py)。
