# Agent Watchdog

> 一个正在开发中的个人 AI Agent 独立监督工程项目。

目标不是判断 AI 有没有报错，也不把 StepWise 的 Stuck Detector 当成整个项目。希望让 Codex 等 Agent 的执行过程可观察、用户任务要求可追踪、Git / 测试结果有独立证据、风险提示可解释，且默认不自动控制 Agent。

## 从零开发 Agent Watchdog · 博客教程

| 篇章 | 标题 |
|---|---|
| 01 | [让 Codex 的执行过程进入我们自己的监控程序](从零开发%20Agent%20Watchdog（01）.md) |
| 02 | [用 Python 实时监控 Codex 的执行状态](从零开发%20Agent%20Watchdog（02）.md) |
| 03 | [让 AI 的任务进度有证据](从零开发%20Agent%20Watchdog（03）.md) |
| 04 | [让 Hook 事件自动触发 Git 证据检查](从零开发%20Agent%20Watchdog（04）.md) |
| 05 | [让监督器知道任务的目标](从零开发%20Agent%20Watchdog（05）.md) |
| 06 | [独立验收与过期证据](从零开发%20Agent%20Watchdog（06）.md) |
| 07 | [异常监督与误报](从零开发%20Agent%20Watchdog（07）.md) |
| 08 | [监督工作流与统一面板](从零开发%20Agent%20Watchdog（08）.md) |
| 09 | [SQLite 持久事件账本](从零开发%20Agent%20Watchdog（09）.md) |
| 10 | [Codex 执行轨迹适配](从零开发%20Agent%20Watchdog（10）.md) |
| 11 | [可解释监督决策](从零开发%20Agent%20Watchdog（11）.md) |
| 12 | [长期运行与跨会话交接](从零开发%20Agent%20Watchdog（12）.md) |
| 13 | [真实 Codex 联调与证据验收](从零开发%20Agent%20Watchdog（13）.md) |
| 14 | [App Server 结构化事件与最小化采集](从零开发%20Agent%20Watchdog（14）.md) |
| 15 | [任务要求与验收证据的进度关联](从零开发%20Agent%20Watchdog（15）.md) |
| 16 | [任务范围偏离与人工复核](从零开发%20Agent%20Watchdog（16）.md) |

## 配套源码

[第 04–16 篇兼容工程与测试](examples/v04/README.md)，沿用你原第三篇 `evidence.py` 的接口，Windows 11 + Conda 为主要目标。真实 Codex Hook 接入与长时间运行需要在用户本机另外验收，隔离环境中的自动测试通过不能代替现场验证。

## 设计边界

- 监控器默认只读：不自动 `kill`、`retry`、`rollback` 或改写 Agent 工作区。
- 采集最少元数据，不默认保存原始提示、命令参数或工具输出。
- Agent 声称完成不等于 `VERIFIED_COMPLETE`，测试过期不再算当前已通过。
- Hook 事件并不能完整覆盖一切 Agent 执行路径；Git 检查无法单独证明是谁修改了文件。
- StepWise 等模型只是未来可能加入的风险信号模块，不是本项目的唯一目标。

参考：[Codex Hooks](https://developers.openai.com/codex/hooks) · [Codex App Server](https://developers.openai.com/codex/app-server) · [Rich](https://github.com/Textualize/rich)。

## 第 13–16 篇增量及验收范围

[第 13–16 篇的安装与验收说明](examples/v04/CHAPTERS_13-16.md)。新增 `integration_check.py`、`appserver_adapter.py`、`progress.py`、`scope_guard.py`，并保留原来的 `evidence.py` 与 Task Contract 接口。`appserver_adapter.py` 只导入用户明确提供的离线事件流，不接管 App Server 运行或审批；`scope_guard.py` 是路径边界监督，不是通用语义偏离分类器。

上述内容属于教程与隔离测试成果，不代表作者用户 Windows 机器已完成真实 Codex 端到端联调。
