# 第 29–32 篇：Codex App 可安装的伴随监督器

从 [第 25–28 篇](CHAPTERS_25-28.md)继续，不另起一套架构。**本轮直接面向 Windows Codex App，第一步是独立测试仓库验证 Hooks**；如果你只使用 CLI 验证事件，并不能替代 Codex App 现场验收。

## 入口与开箱体验

1. `app_control_v32.py doctor --repo <练习仓库路径>`：检查将要使用的路径，不宣称真实接入成功。
2. `app_control_v32.py propose --repo <练习仓库路径>`：只生成配置提案，不安装。
3. 阅读 Python 脚本和提案，用户亲自决定后执行 `app_control_v32.py install --repo <练习仓库路径> --ack-reviewed-hooks`；只创建新的 `.codex/hooks.json`，不会覆盖其他配置。
4. 使用 **Codex App Windows UI** 打开该仓库，检查 Hooks 信任，在 App 中执行实际练习任务，不用 `codex exec` 冒充。
5. 打开另一个前台终端：`app_control_v32.py watch --notify`，在私有日志和 SQLite 中观察新的脱敏事件。停掉 Watchdog 不会关闭 Codex App。
6. `app_control_v32.py status` / `backup`：检查状态或备份，绝不自动恢复 Codex。

完整 Windows CMD/PowerShell 命令、真实 G1 验收与回退见 [Codex App Quickstart](../../docs/CODEX_APP_QUICKSTART_29-32.md)。

## 文件对应

| 教程 | 代码 | 有界功能 |
|---|---|---|
| [29](../../从零开发%20Agent%20Watchdog（29）.md) | [app_hook_v29.py](watchdog/app_hook_v29.py)、[app_setup_v29.py](watchdog/app_setup_v29.py) | 审查优先的项目级 Hook，默认去除工作区原始路径 |
| [30](../../从零开发%20Agent%20Watchdog（30）.md) | [app_watch_v30.py](watchdog/app_watch_v30.py) | 读取完整 JSONL，持久游标与复核提醒，默认跳过历史告警 |
| [31](../../从零开发%20Agent%20Watchdog（31）.md) | [app_recovery_v31.py](watchdog/app_recovery_v31.py) | SQLite 在线私有备份、不做危险的 App 自动重跑 |
| [32](../../从零开发%20Agent%20Watchdog（32）.md) | [app_control_v32.py](watchdog/app_control_v32.py) | 用户手动启动和撤销的统一操作入口 |

## 兼容与未完成项

这是一个**前台旁路个人试用候选**，不是所有 Windows 机器上无须配置就生效的正式 Codex App 插件。配置信任、App 沙盒、具体执行工具的 Hook 覆盖、气泡通知弹出效果，均需要用户现场检查。评估真实误报/漏报、恢复跨天稳定性与任务合同自动关联仍需独立后续证据。

合成单测 [test_round3.py](tests/test_round3.py) 检验已成功/失败/UNKNOWN、游标与冷却、首次新日志出现、日志半行、跨会话、重启、无日志、备份。不会自动跑模型、读你私人 Codex 历史库或上传日志。**禁止把合成成功案例当作真实检测准确率**。
