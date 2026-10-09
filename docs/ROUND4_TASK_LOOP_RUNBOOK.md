# Windows Codex App → Watchdog：第 34–37 篇任务闭环实用手册

> 不覆盖已经跑通的全局 Hook。本轮新增**一次人工会话归属审核**、合同/ Git/验收联合查看、状态变化提醒和集成前台监控。所有真实 Codex 结果只能由本机验证；GitHub CI 只测试合成 Hook 与隔离 Git。

## 0. 先确定能证明什么

现有 Hook 默认丢弃原始提示、命令、工作目录 `cwd`，保护隐私却意味着我们无法自动认出“这个 Codex 会话属于哪个仓库”。本轮采用人工绑定一个最近的脱敏会话别名到一个**已有 Git baseline、已审核 Task Contract** 的项目。此映射是人的选择，不认证 Hook 来源，更不能证明 Codex 修改了后续 Git 文件。

第 33 篇仅有操作者报告桌面 App 已成功捕获事件；Hook 信任是否完全去掉 bypass，G3 的真实检测有效性和 G4 长期可靠性还没有独立结案。[Codex Hook 官方文档](https://developers.openai.com/codex/hooks)仍是权限和信任参考。

## 1. 下载这轮代码到独立目录

在 Windows **Anaconda Prompt (CMD)**：

```bat
conda activate torch_env
git clone https://github.com/colddreamxiaowd/Agent-Watchdog.git D:\program\Agent-Watchdog-v37-eval
cd /d D:\program\Agent-Watchdog-v37-eval
python -m unittest discover -s examples\v04\tests -v
```

如同名路径已经存在，请自己选一个新目录；不覆盖原有 `agent_watchdog_for_loomy` 的 Hook 配置。下文示例仓库 `D:\Projects\watchdog-demo` 和合同 `D:\Projects\approved_contract.json` 都应替换成你亲自核对的**一次性练习仓库/合同文件**。不要直接对正在进行的高风险科研项目重建 baseline。

## 2. 提前准备可审查的目标、不可修改文件和验收项

参考 [合同格式](../examples/v04/watchdog/task_contract.example.json)，把要做什么、保护哪些文件、允许修改哪些文件、验收命令是什么全部写清。每个验收命令都必须由你确认可以在该 Git 项目上安全运行。然后在监控器源码目录执行：

```bat
cd /d D:\program\Agent-Watchdog-v37-eval\examples\v04\watchdog
python evidence.py --repo "D:\Projects\watchdog-demo" baseline
python task_contract.py --repo "D:\Projects\watchdog-demo" init --contract "D:\Projects\approved_contract.json"
python task_contract.py --repo "D:\Projects\watchdog-demo" approve
python task_contract.py --repo "D:\Projects\watchdog-demo" status
```

**先 baseline，再让 App 开始修改目标文件。** 已经改动过的历史不能由新 baseline 追溯。不要为了让保护文件违规“消失”而重新采集 baseline。

## 3. 选择真正的 Desktop 会话（不需要重新安装 Hook）

保持已成功的**全局 Hook + Windows ASCII CMD 包装器**，不要运行旧的项目级 `app_control_v32.py install`。

在 Codex App 里打开该练习项目并做一个普通操作，再从 CMD 运行：

```bat
python app_task_watch_v37.py sessions
```

它显示当前私有日志里最近 48 小时的会话别名、事件数和最后时间。`alias` 不是用户名、路径或真实任务 ID，只是脱敏会话 ID 的哈希。你要对照 **App UI 的会话时间和任务** 手工确认选的是哪一个，不能把“日志有一条 SessionStart”直接认作所有会话已被认证。

如果两个程序因为 `LOCALAPPDATA` 环境身份不一致，支持显式传入你本人确认过的实际日志路径：

```bat
python app_task_watch_v37.py sessions --log "C:\ExampleUser\AppData\Local\AgentWatchdog\events.jsonl"
```

这里是**虚构路径**；不要照抄到自己的真实用户目录。当前全局 Hook 是否对所有项目生效，需要现场验证，不能靠这种临时路径映射自动证明。

## 4. 一次人工批准，把会话和任务合同关联

把刚才实际输出的别名替换下列占位符：

```bat
python app_task_watch_v37.py bind --repo "D:\Projects\watchdog-demo" --alias "REPLACE_WITH_ALIAS" --approve-binding
```

不加 `--approve-binding` 时会拒绝绑定；找不到最近会话、合同未审核、没有 baseline、别名已绑定、注册文件落到被监控仓库内部也会拒绝。私人绑定保存在当前 Windows 用户的数据目录下，不写入工作区。

**换任务时要用新的会话/新的人工关联**。程序不会因 Codex 在同个项目里发送过工具事件，就假装能理解它正在执行的自然语言目标。

## 5. 现在终于可以看“任务状态”，而非只有事件计数

```bat
python app_task_watch_v37.py overview
```

输出会把这份批准合同、当前 Git 实际文件变化、保存的验收结果与属于这个会话的脱敏事件放在一处。字段包含：

- `session_alias`：你曾明确认领的会话别名。
- `observations`：仅统计该来源/会话的事件、明确结果、未观察到终态的调用，不表示完成度百分比。
- `scope_findings`：受保护文件变化、允许路径以外的 Git 变化；**无法仅凭 Git 归因给 Codex**。
- `acceptance`：人工批准的每项测试当前是 `NOT_TESTED`、`PASSED`、`FAILED`、`STALE` 等。
- `actions`：提示下一步该检查合同、人工运行批准测试、检查风险范围，还是人工确认任务语义。
- 默认不打印合同中的原始目标文字；私人终端里明确使用 `--show-goal` 才会显示。

即使工具连续十次成功，如果批准的验收没有执行，`contract_checks_stage` 也不会变成已验收。即使输出 `VERIFIED_COMPLETE`，也**只证明合同中列出的独立检查**，并非自然语言要求的所有隐含细节都完成了。

## 6. 人工决定执行一次真正的独立验收

只有确认项目可安全运行并亲自审查合同后：

```bat
python task_contract.py --repo "D:\Projects\watchdog-demo" verify A1
python app_task_watch_v37.py overview
```

这里 `A1` 是合同检查 ID 示例。Hook/Watcher **不会自动执行验收命令**。如果文件在测试通过以后又发生变化，保存的通过证据会变成 `STALE`，Watchdog 将提示需要重新审核。不要无意识地给运行中的 Agent 添加新的写操作权限。

## 7. 让事件风险和任务证据变化同时监督

```bat
python app_task_watch_v37.py watch --notify
```

这条命令在一个终端中调用原来第 30 篇的事件观察，同时读取新的任务进度、Git 变化和验收结果。默认每五秒巡检；首次启动只记录已有状态、不把旧问题重新通知。之后检测到受保护文件变化、范围外文件、保存的测试变过期、合同改变，会写入私有 SQLite 并以**不包含文件名/路径/提示内容**的固定文字尝试 Windows 气泡。

停止监控器不会关闭 Codex App，不会 kill/retry/rollback；它仍然是你显式打开的**前台伴随程序**，不是开机自启动的系统服务。即使关闭期间发生过变化，重新运行可以在 overview 中看到当前状态，但首次启动的提醒策略会避免把旧状态伪装为刚发生的事故。

## 8. 四个必须主动验证的反例

1. **没有人工绑定**：同一台机器有多个 Codex 会话时，不能自动把别的会话算进你的项目；`overview` 的任务列表应保持空或只显示已批准绑定。
2. **Git 改动不是 Codex 做的**：用第二个终端自己修改被保护的 `GOAL.md`，即使出现风险，也只能输出 `author_attribution=UNKNOWN`。
3. **旧成功不能冒充新完成**：人工运行过的批准测试先 PASS，再修改普通源码，应显示 `STALE`，而不是完整任务已经完成。
4. **合同或 baseline 更新**：之前绑定必须失效，不能自动跟随新目标，更不能通过重新采集 baseline 去掩盖原来的违规。

这几条在本轮源码的 [隔离测试](../examples/v04/tests/test_round4.py) 中有合成对照，但真实 App 的 ID 稳定性、告警误报/漏报、休眠、不同用户配置、真实 Windows 气泡显示还需要你的现场记录。

## 9. 本轮剩余的真正难题

事件来源仍为 `hook_input_unverified`；会话→仓库仍需你人工选一次；Git 快照的作者身份无法确认；“语义目标偏离”没有实测的可用模型；复杂任务进度不是一个百分比；默认只读取最近有限日志窗口；G3/G4 还未通过。因此这一轮只能称为**将“真实 App 已接入”推进到“可审查任务监督闭环”的参考工程**，不能宣布成熟的无人值守 V1.0。

后续优先用真实 Codex App 的若干次合法任务，对照独立人类判断，建立准确率、误报、漏报与告警延迟的证据，再选择是否增强语义判别，避免为了显得智能而牺牲隐私和可信性。
