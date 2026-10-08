# 事件来源覆盖与 G2 解释合同

对照 2026-10-08 查询的 [Codex Hooks](https://developers.openai.com/codex/hooks)、[Codex App Server](https://developers.openai.com/codex/app-server) 公开文档。**文档描述不等于用户 CLI 版本的现场实测**。

| 来源与事件 | 可能持有字段 | 本项目记录 | 明确不能推断 |
|---|---|---|---|
| Hook `PreToolUse` | `session_id`、`turn_id`、`tool_use_id`、`tool_name`、`cwd` | `phase=STARTED`，`outcome=UNKNOWN` | 工具一定已执行 |
| Hook `PostToolUse` | 同上，`tool_response` 的格式依工具而异 | `phase=FINISHED`；仅在直接数字 `exit_code/exitCode` 明确出现时判成功/失败 | PostToolUse 存在 = 成功 |
| Hook `Stop` | 会话/回合 | `phase=TURN_END`，`outcome=UNKNOWN` | 项目完成 |
| `codex exec --json` `item.started/updated/completed` | `thread_id`、`item.id/type`、有些命令项的数值 `exit_code` | 显式**离线** `codex_exec_export_unverified` | 任意 GUI Desktop 执行被覆盖 |
| `codex exec --json` `turn.failed/error` | 类型与有限上下文 | `outcome=FAILED`，来源只是未认证导出 | 工具失败一定对应同一调用 |
| App Server `item/started/updated/completed` | `threadId/turnId/item.id`、`status`、命令 `exitCode` | 显式**离线** `app_server_export_unverified` | 已连接 live App Server |
| App Server `turn/completed` | `turn.status` 可能为 completed/interrupted/failed | 仅映射有明确语义的终态 | turn completed = 用户所有需求已验收 |
| 未覆盖工具、推理、休眠或离线 | 无稳定观测 | `NO_OBSERVATION` / `UNKNOWN` | Agent 已卡死或没有做事 |

## 结果分层

- `SUCCEEDED`：仅有明确数值退出码 0，**表示那个命令的进程退出成功**，不是业务正确。
- `FAILED`：有明确非零数值退出码，或明确报告的 `failed` 终态。
- `CANCELLED`：`declined/interrupted/cancelled` 显式状态；区别于失败。
- `UNKNOWN`：没有上述证据。字符串里写着 “0 tests failed” 也不能解析成成功。

`source` 是导入标签，不是数字签名；`received_at` 是接收时间，不自动代表工具实际执行时间；`cwd` 只是被报告的路径，不是文件变更作者。`event_id` 是脱敏记录的稳定参考哈希（有调用 ID 时），不是密码学来源认证；无稳定调用 ID 的记录标记 `linkable=false`。

## 已知接口边界

旧 `journal.py` 在本轮扩大允许字段，仍兼容其早期 8 个元数据字段；旧数据的新增字段是 `null`，不可用时保持 `UNKNOWN`。不得把历史旧格式批量补造成成功结果。

开源复用选择：`sqlite3` / `hashlib` / `unittest` / Git 优先于重复造轮子；第三方 [Codex Task Watchdog](https://github.com/TanChuping/codex-task-watchdog) 的 Windows 只读 SQLite 观测设计值得借鉴，但依赖 Codex 内部日志数据库版本，因此本轮没有复制其解析器、安装脚本、后台控制和自动恢复；参照其安全约束亦不代表与其代码完成集成。进一步评估见第 30 篇。
