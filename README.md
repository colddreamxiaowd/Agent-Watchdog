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
| 17 | [事实优先的智能异常监督与误报控制](从零开发%20Agent%20Watchdog（17）.md) |
| 18 | [Streamlit 本地 Web 监督控制台](从零开发%20Agent%20Watchdog（18）.md) |
| 19 | [长期运行、SQLite 备份与恢复](从零开发%20Agent%20Watchdog（19）.md) |
| 20 | [V1.0 综合验收与发布候选门槛](从零开发%20Agent%20Watchdog（20）.md) |
| 21 | [别再用模拟事件证明 Codex 已接入：Windows G1 验收](从零开发%20Agent%20Watchdog（21）.md) |
| 22 | [工具结束不等于成功：统一事件与结果状态](从零开发%20Agent%20Watchdog（22）.md) |
| 23 | [五分钟没动静就是卡死？保守运行监督状态机](从零开发%20Agent%20Watchdog（23）.md) |
| 24 | [操作与任务步骤关联，但不让“做过”冒充“做成”](从零开发%20Agent%20Watchdog（24）.md) |
| 25 | [连续失败也不一定在死循环：失败聚集与人工意图审查](从零开发%20Agent%20Watchdog（25）.md) |
| 26 | [StepWise 不是魔法按钮：小模型增益的公平比较](从零开发%20Agent%20Watchdog（26）.md) |
| 27 | [AI 忙错方向怎么办：合同锚定与目标偏离复核](从零开发%20Agent%20Watchdog（27）.md) |
| 28 | [报告、产物的非测试类独立验收](从零开发%20Agent%20Watchdog（28）.md) |
| 29 | [真正面向 Windows Codex App 的项目级 Hook 安装](从零开发%20Agent%20Watchdog（29）.md) |
| 30 | [前台提醒、持久游标与 Windows 通知](从零开发%20Agent%20Watchdog（30）.md) |
| 31 | [Watcher 恢复、数据库健康与私有备份](从零开发%20Agent%20Watchdog（31）.md) |
| 32 | [Codex App 伴随监督器试用与完整验收](从零开发%20Agent%20Watchdog（32）.md) |

## 配套源码

[第 04–20 篇兼容工程与测试](examples/v04/README.md)，沿用你原第三篇 `evidence.py` 的接口，Windows 11 + Conda 为主要目标。真实 Codex Hook 接入与长时间运行需要在用户本机另外验收，隔离环境中的自动测试通过不能代替现场验证。

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

## 第 17–20 篇：主线收官与发布门槛

第 17–20 篇增加事实/弱信号分层、Streamlit 本地面板、数据级健康检查与 SQLite 在线备份、Release Candidate 检查机制。完整安装与本机验收见 [第 17–20 篇运行说明](examples/v04/CHAPTERS_17-20.md)。

**重要**：教程写到第 20 篇不等于软件正式 V1.0 发布。用户 Windows + 真实 Codex、跨会话、测试过期、备份恢复与安全审核仍需现场证据；未完成时发布门槛保持 `BLOCKED`。

## AW-V2 · 第 21–24 篇：先工程后博客（2026-10-08）

这是一轮**可审计参考工程增量**，不是产品 V1.0 已发布。第 20 篇的“收官”只表示当时的教程主线结束；真实产品目标尚未完成。本轮具体状态参阅：

- [修订版产品需求、G0–G4 门槛](docs/PRODUCT_REQUIREMENTS_V2.md) · [能力/证据矩阵](docs/CAPABILITY_MATRIX.md)
- [Windows + 真实 Codex E2E 验收 Runbook](docs/REAL_CODEX_E2E_RUNBOOK.md)（本机实测 **NOT_VERIFIED**）
- [事件来源与字段保守语义](docs/EVENT_SOURCE_MATRIX.md) · [自动化测试记录与限制](docs/ROUND1_TEST_REPORT.md)
- [第 21–24 篇源码、安装和反例测试指南](examples/v04/CHAPTERS_21-24.md)

新模块均在原有 `examples/v04/watchdog/` 中：`doctor_v21.py`、`execution_v2.py`、`runtime_v2.py`、`step_links_v2.py` 和可选 Runner `hook_runner_v21.cmd`。旧的 `hook_runner_v04.cmd` 与 `evidence.py` 保留。显式修改了旧 `journal.py` 的字段白名单与 SQLite 句柄关闭，以及 `operations.py` 的句柄关闭，修复跨平台测试用例里的仓库路径规范化。

一键验证全套（**仅隔离代码测试，不接入真实 Codex**）：

```bat
python -m unittest discover -s examples\v04\tests -v
python scripts\validate_round1_docs.py
```

GitHub Actions 同时配置 Ubuntu 和 Windows 托管 Runner；它们不等于用户的 Windows 11 真机。重复 Bash、无新事件、旧测试 PASS 均不自动触发“循环/死锁/任务完成”结论。真实 Codex Hook G1、真案例检测 G3、长期安全 G4 仍需分别验收；第 25–28 篇不能凭教程数量直接晋级。

## AW-V2 · 第 25–28 篇：核心监督 MVP 的有界工程基础（2026-10-08）

- **25**：新增 [failure_review_v25.py](examples/v04/watchdog/failure_review_v25.py)，区分明确失败聚集和被人工标注为同一尝试意图的候选；同类型 Bash 不等于同命令或无效循环。
- **26**：新增 [stepwise_compare_v26.py](examples/v04/watchdog/stepwise_compare_v26.py)，仅对明确导入的外部模型分数与同一批独立标签的规则基线做配对计算；不下载/运行 StepWise 模型，缺少真实输出时 `NOT_EVALUATED`。
- **27**：新增 [drift_review_v27.py](examples/v04/watchdog/drift_review_v27.py)，区分 Git 范围事实与来源未认证的语义偏离建议；只能 `HUMAN_REVIEW_REQUIRED`。
- **28**：新增 [artifact_acceptance_v28.py](examples/v04/watchdog/artifact_acceptance_v28.py)，核验经批准的预期产物 SHA256 和 Git 范围，结果最多是 `ARTIFACT_BYTES_MATCH_ONLY`，不绕过旧的 Task Contract 独立测试。

配套：[四章安装和源码对应说明](examples/v04/CHAPTERS_25-28.md) · [本轮证据协议与 G3 门槛](docs/ROUND2_EVIDENCE_PROTOCOL.md) · [Windows 人工验收工作单](docs/ROUND2_WINDOWS_RUNBOOK.md) · [本轮 CI 与差距报告](docs/ROUND2_TEST_REPORT.md)。

**边界**：当前新增代码是有正反例覆盖的参考实现，而不是完整智能监督 MVP。用户 Windows 上的 G1 真实接入仍 `NOT_VERIFIED`，G3 真实检测误报/漏报与 StepWise 增益仍 `NOT_EVALUATED`，G4 长期/提醒/恢复尚未验证。不得将合成数据的计算结果作为实际性能宣称，不上传私人日志与命令输出。

```bat
python -m unittest discover -s examples\v04\tests -v
python scripts\validate_round1_docs.py
```

## AW-V2 第 29–32 篇：Windows Codex App 伴随观察原型

**目标客户端是 Windows 桌面 Codex App，不是 `codex exec` 的日志回放。** 在用户审查并信任项目级 Hooks 后，可以运行独立的本地监控器，记录脱敏元数据、持续检查、持久化复核提醒，并尝试 Windows 本机气泡通知。无法自动确认真实 App 的覆盖率、死锁、语义偏离或最终任务完成。

- **[Codex App 真实试用快速开始](docs/CODEX_APP_QUICKSTART_29-32.md)**：一步步配置新练习仓库、审核安装、在 App UI 触发真实任务、检验私有日志及撤销。
- [四章源码索引](examples/v04/CHAPTERS_29-32.md) · [本轮测试及边界](docs/ROUND3_TEST_REPORT.md)。
- 核心新文件：`app_hook_v29.py`、`app_setup_v29.py`、`app_watch_v30.py`、`app_recovery_v31.py`、`app_control_v32.py`、`START_CODEX_APP_WATCHDOG.cmd`，位于 `examples/v04/watchdog/`。
- 私有日志和 SQLite 默认位于 `%LOCALAPPDATA%\AgentWatchdog`。**不扫描 Codex App 私有数据库，不采集原始 prompt/命令/输出，不执行 kill、retry、rollback，不自动安装 Windows 服务**。

在干净的 Git 测试项目中先审查并应用 Hook；开一个独立的 Anaconda Prompt：

```bat
cd /d D:\program\agent_watchdog\Agent-Watchdog-app-eval\examples\v04\watchdog
python app_control_v32.py watch --notify
```

**产品状态：个人自愿试用候选，不是正式 V1.0**。用户 Windows Codex App 的现场 G1=`NOT_VERIFIED`，真实误报/漏报 G3=`NOT_EVALUATED`，长时间使用 G4=`NOT_VERIFIED`。GitHub Actions Hosted Windows 不替代真实 App 现场证据。
