# 第 34–37 篇：面向 Codex Desktop 的任务级监督

继续第 33 版**已成功的全局 Hook**，本轮不要重新安装项目级 Hooks。以前观察器能发现工具开始/结束与疑似失败，却不知道“这个会话究竟对应什么用户目标”。第 34–37 篇解决**经人认可的任务关联**，并把旧合同、Git 和测试验收复用到统一观察窗口。

| 第几篇 | 新增内容 | 源码 |
|---|---|---|
| [34](../../从零开发%20Agent%20Watchdog（34）.md) | 会话别名、人工批准的 Git 项目与合同关联 | [session_binding_v34.py](watchdog/session_binding_v34.py) |
| [35](../../从零开发%20Agent%20Watchdog（35）.md) | 按实际证据显示哪些任务验收缺失、过期、范围异常 | [task_overview_v35.py](watchdog/task_overview_v35.py) |
| [36](../../从零开发%20Agent%20Watchdog（36）.md) | 状态变化才提醒，重复/重启不刷屏，复发可再次提醒 | [task_pulse_v36.py](watchdog/task_pulse_v36.py) |
| [37](../../从零开发%20Agent%20Watchdog（37）.md) | 统一前台观察入口、可选本地 Windows 通知 | [app_task_watch_v37.py](watchdog/app_task_watch_v37.py) |

**先读 [Windows 真实工作单](../../docs/ROUND4_TASK_LOOP_RUNBOOK.md)**：创建一次性仓库、baseline、合同批准 → App 真会话 → sessions 查看别名 → 明确 bind → overview → watch。这才是一条完整的人为授权链。

隔离测试在 [test_round4.py](tests/test_round4.py)：正反例验证跨会话隔离、假 Hook 不认证、baseline/合同变化失效、Git 保护文件事实不归因、通过测试后证据变过期、告警重启去重和 A→B→A 复发。它们没有运行真实桌面 App，不是 detector efficacy 或正式 G4。

**重要**：前一版会话日志因最小化原则不包含 cwd，自动关联项目在当前证据下不可信。因此第一版采用人工绑定；未来若要减少人工介入，必须独立审查相应来源身份/授权边界，而不是偷偷恢复收集提示词与命令。

Windows 手动启动脚本：[START_TASK_WATCHDOG.cmd](watchdog/START_TASK_WATCHDOG.cmd)。先完成批准合同与会话绑定，否则它仍可观察通用事件，但没有任务级可审查对象。
