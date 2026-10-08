# Round 3 — Codex App 伴随程序证据记录

日期 2026-10-08。起始主分支 commit `6e5a70ad406cc5f9c1240bed472078a898894248`。受测对象是 Windows Codex App 伴随程序参考实现，不是对真实用户 App 的远端操控或现场日志读取。

## 实现

- 第 29 篇：`app_hook_v29.py` 和 `app_setup_v29.py`；人工审阅、显式批准新 `hooks.json`；项目范围 Hook；安全抽取事件，输出 `{}` 让 App 继续执行。
- 第 30 篇：`app_watch_v30.py`；用户数据目录、本地 SQLite、追加式文件游标、已处理事件去重、失败聚集冷却、疑似缺终态告警、可选 Windows PowerShell 气泡。**不读原始 prompt/command/output**。
- 第 31 篇：`app_recovery_v31.py`；只读健康状态和由用户发起的 SQLite 备份，**无自动恢复/重试/杀进程**。
- 第 32 篇：`app_control_v32.py` 和 `START_CODEX_APP_WATCHDOG.cmd`；统一只读 CLI 和显式安装入口，Windows 实机使用工作单。

## 不能从合成测试升级的结论

1. Hook 本机来源身份还不可信。模拟调用 `app_hook_v29.observe(...)` 只能验证字段白名单。
2. 官方描述 Hooks 支持在 Codex 中配置，但本轮没有直接访问用户的 Windows Codex App，没有检验安装、信任和沙盒下数据目录写入。
3. 原 Hook 投影只有明确数值退出码才声明工具 `FAILED/SUCCEEDED`；一般工具即使产生 PostToolUse，也可能是 `UNKNOWN`。
4. 断网、睡眠、Code Runner 被系统拦截或 app 更新可能使 Hook 完全缺失；`NO_LOG_NOT_CODEX_OFFLINE` 是**观测不足**，绝不是“Codex App 已离线”。
5. 隐私：默认日志在 `%LOCALAPPDATA%\AgentWatchdog`，不是仓库；但 SQLite 仍保存 session/tool 标识，用户不应分享日志/备份。
6. 有界安全性：SQLite 游标和临时崩溃恢复属于测试覆盖的机制；日志代际和前缀 fingerprint 并非外部认证，对敌意篡改不可构成完整防御。需要 OS 级身份、崩溃注入和长期观察才能证明稳健。
7. **G1 NOT_VERIFIED / G3 NOT_EVALUATED / G4 NOT_VERIFIED**，本文无误报率、模型 F1、长时间可靠性宣称。

## 测试工作流

CI: `.github/workflows/round1-ci.yml` 已扩展至 round3 分支，Windows + Ubuntu Python 3.11 运行所有原 67 项及 `test_round3.py` 中新增的隔离单测；Markdown 静态检查只验证标题、围栏和已存在的相对链接，不证明业务正确。**已核验结果**：[Actions Run 37792802473](https://github.com/colddreamxiaowd/Agent-Watchdog/actions/runs/37792802473)，对应分支提交 `553ea69b738dd324139c37a6d9e5f9a3390ac33f`：Windows Hosted Runner 85 项 unittest 通过，Ubuntu Hosted Runner 85 项 unittest 通过；26 份 Markdown 静态检查，两平台均 errors=0。初次扩展文档时 [Run 37792675993](https://github.com/colddreamxiaowd/Agent-Watchdog/actions/runs/37792675993) 因第 30 篇代码注释被误认为第二个 H1 而失败，现已修复。这些是有界自动回归而**不是 Codex App 真实试用证据**。

Windows 现场：按 [Codex App Quickstart](CODEX_APP_QUICKSTART_29-32.md) 手工审查日志、App UI 实际工具调用和 Hook 执行。不得用 CLI、合成事件、另一个安装的 Codex 或 GitHub Runner 替代 App 验收。
