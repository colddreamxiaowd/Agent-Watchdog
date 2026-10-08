# AW-V2-ROUND1-21-24 — 自动测试、已知局限与下一轮准入报告

**报告日期：2026-10-08（Asia/Singapore）**。项目是独立个人工程；**托管 Windows CI 不是用户的 Windows 11 主机；用户真实 Codex Hook G1 仍是 `NOT_VERIFIED`**。不得将本文作为真机验收证明。

## 起点与证据链

- 经 GitHub API 核对的 `main` 起始 HEAD：`cac008eb7ac2ebb159e8f23d2d50bd773e282c2e`，已有教程 01–20。
- 代码开发于 `feature/aw-v2-round1-21-24`，从上述 HEAD 创建；完整历史在 [GitHub 提交列表](https://github.com/colddreamxiaowd/Agent-Watchdog/commits/feature/aw-v2-round1-21-24)。
- 首次 GitHub Actions 运行 [37783860314](https://github.com/colddreamxiaowd/Agent-Watchdog/actions/runs/37783860314)：Ubuntu 成功，Windows **失败**。输出显示 `Ran 43 tests`，Windows `failures=1, errors=2`。这次失败不能隐藏。
- 已排查：旧 `journal.summary` 使用 `sqlite3.Connection` context manager 后未显式 `close()`，Windows 临时文件 `backup.sqlite3` 仍被占用；旧 `operations.check/archive` 同样改为显式释放句柄；旧测试临时 Git 工作区路径没有通过 `evidence.root_for` 规范化，导致范围判断在 Windows 上不一致。保留并最小修改现有接口。
- 修复和新增两项人工证据链接负例测试之后，[GitHub Actions 运行 37784304732](https://github.com/colddreamxiaowd/Agent-Watchdog/actions/runs/37784304732) **Ubuntu 与 Windows 两个 job 均成功，每个平台 45 tests、OK**（Python 3.11 托管 Runner）。
- 随后新增两个运行时反例：旧失败不得永久刷屏、慢调用已完成不得算“卡死”。[GitHub Actions 运行 37785913634](https://github.com/colddreamxiaowd/Agent-Watchdog/actions/runs/37785913634) 在提交 `85a029a54f589106a32f340f64e2b0470b75a784` 上 **Windows 与 Ubuntu 皆为 SUCCESS：各 47 tests、OK，另有 Markdown 文件 11 份检查 0 errors**。此记录仅证明所指提交的托管 CI；本报告自身编辑仍需随 PR 复验。
- 本轮另加入 `scripts/validate_round1_docs.py`，检测四篇的 Markdown 标题、代码围栏、相对链接，并在两个 CI 平台执行。此脚本只能检查格式和本地文件存在，不证明内容正确。

## 覆盖边界

| 验证 | 预期且需留下的正反例 | 不能证明 |
|---|---|---|
| 旧工程回归 | Git/contract/SQLite/证据过期/路径保护和备份 | 完整生产行为 |
| Hook JSON 投影 | 明确整数 0/1、布尔/字符串伪码、隐藏的命令与输出 | 真实 Codex Hook 被调用 |
| `codex exec --json` 与 App Server 导出 | 缺字段、显式取消、半写完 JSONL、稳定事件 ID | Live Desktop 旁路连接 |
| 状态机 | 配对悬挂、无观测、冲突终态、跨会话、六次 Bash 正常调用、旧失败不永久报错 | 真正死循环的分类准确率 |
| 任务关联 | 合同批准、哈希不匹配、缺事件=UNLINKED、STALE 不升级 | 自动理解自然语言目标 |
| CI 文档 | 第 21–24 篇 Markdown 与源码、工作单链接存在 | 用户真正运行了所有 Win 步骤 |

## G0–G4 结论

- **G0（基线代码与回归）**：起点 HEAD 已核对，使用 GitHub Hosted Linux/Windows Python 3.11 CI 进行代表性跨平台回归；**用户本机**的 `git --version`/`python --version`/`codex --version`、原项目已修改内容与安装方式需要 Runbook 补证。
- **G1（用户真实 Codex）**：`NOT_VERIFIED`。必须由用户在临时仓库匹配 `/hooks`、真实工具操作及私有脱敏日志，再检查独立 Git 变化。
- **G2（结构化结果）**：参考适配器和模拟测试可核查；真实版本字段覆盖率仍未知，缺码保持 `UNKNOWN`。
- **G3（真实检测效果）**：`NOT_EVALUATED`；没有按实际任务场景标注样本的误报、漏报、延迟与不可判定比例，不允许声称“智能 stuck 检测已准确”。
- **G4（长期产品）**：`NOT_VERIFIED`。睡眠、重启、滚动、通知冷却、多项目和恢复演练尚待执行。

## 已知软件安全与后续技术债

- Hook stdin 的 `source` 标签与 `event_id` 的 hash 都不验证来源真实性；恶意同权限本地进程也可能注入相同结构。
- `received_at` 是本机收到记录的 wall-clock 时间，不是工具真实耗时；异常运行状态仅弱提示。
- 工具响应依类型和版本变化。只从受支持的数值退出码/显式终态推结果，未知的结果保持 `UNKNOWN`。
- `step_links_v2.py` 只读已批准合同并由人写出关联，不能自动匹配步骤或升级独立验收；静态 links 文件必须放在被监控仓库之外。
- 旧 Streamlit 看板与新版事件分析尚未形成完整自动轮询与原生弹窗通知；本轮 CLI 为一次性诊断，第 29 篇再做通知/去重/确认。
- `journal.py` 对 JSONL 的位置去重不等于对所有真实语义事件精确去重；轮转、同步崩溃与磁盘异常仍需长期测试。
- 不运行陌生测试命令，不删除用户项目，不上传私人日志、会话 ID、指令正文或原始工具结果。

## 第 25–28 篇决定

**可开始受门槛约束的工程准备与离线标注协议；不允许把第二轮标为“真实智能监督完成”。** 第 25 篇应优先获得获授权的真实结果样本，固定标注定义；第 26 篇按规则基线比较可选 StepWise；第 27 篇合同语义偏离仅提示人工复核；第 28 篇补非测试类的独立可追溯验收。若 G1/G3 样本暂不可用，就持续将评估状态写为未验证，并以规则/可靠性工程为主。

相关工作单：[Windows E2E Runbook](REAL_CODEX_E2E_RUNBOOK.md) · [事件来源矩阵](EVENT_SOURCE_MATRIX.md) · [能力矩阵](CAPABILITY_MATRIX.md)。
