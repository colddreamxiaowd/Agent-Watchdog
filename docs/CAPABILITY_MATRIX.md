# Agent Watchdog — 当前能力 / 来源 / 证明矩阵

## 复核范围

GitHub `main` 起点 `cac008eb7ac2ebb159e8f23d2d50bd773e282c2e`。本轮新增文件置于原 `examples/v04/watchdog`，旧 `hook_logger_v04.py`、`evidence.py`、`task_contract.py`、`bridge.py` 原样可用。真实 Windows 电脑与 Codex 会话未连接到本次工作环境。

| 能力 | 本轮实现 | 可验证途径 | 仍然未知 |
|---|---|---|---|
| 旧 JSONL→SQLite | `journal.py` 原有流式同步；扩充白名单字段保留 `phase/outcome` | 原有自动化测试，重复导入/半行 | 断电及长期日志轮转 |
| Codex Hook 接入 | `execution_v2.py hook`、`hook_runner_v21.cmd`，不覆盖旧 Runner | 模拟 stdin、可信 Codex 人工 Runbook | **真实 Windows：NOT_VERIFIED** |
| `codex exec --json` | 显式离线 `import --format exec`，不替用户运行 Agent | 测试脱敏 item 和数值退出码 | 桌面会话实时监听能力 |
| App Server | 显式导出流 `import --format appserver`；不发审批 | 离线 fixture | 是否附着到现有 Codex Desktop：不声称 |
| 统一工具结果 | 数值 `exit_code` 或显式 failed/declined；其他 `UNKNOWN` | 缺字段、文字失败、布尔伪码反例 | 任意 tool_response 格式未知 |
| 工具配对 | 稳定 `source/session/turn/call` 分组 | 交叉会话、冲突终态测试 | 无 ID 时 `UNLINKED` |
| 停滞风险 | 可配置时间阈值、`SUSPECTED_STALL`、`NO_OBSERVATION` | 人工时钟、长期无输出反例 | 休眠、无覆盖路径与真实误报率 |
| 失败聚集 | 区分显式失败与同类多次使用 | 两会话、六次 Bash 反例 | 是否同一个命令/是否无效循环 |
| 任务证据 | 合同哈希与人工 event_id 映射，保留 `STALE` | 模拟批准合同和孤立事件 | 事件不会自行使测试通过 |
| Git/范围 | 旧 `evidence.py` / `scope_guard.py` | 独立快照与受保护文件测试 | 不能仅凭变化推断改写者 |
| 主动提醒 | 目前 CLI/文件报告供手动查看 | 输出和去重需要进一步验收 | Windows 系统通知推送留待 29 |
| Windows 整体发布 | GitHub hosted Windows CI 是跨平台隔离测试 | CI 链接与日志 | G1/G3/G4 未通过 |

## 故障处理与权限

默认禁止上传任何真实日志、token、任务合同、命令或私人路径。`events.jsonl`、`state/`、`data/`、`*.sqlite3` 不应纳入提交。`Stop` 只是回合结束，不是任务完成；`PASSED` 只代表某个被批准命令在特定快照上退出码为 0。旧监督 `supervision.py` 的“六次同类工具”启发式不是循环事实；新 `runtime_v2.py` 优先查明确的失败结果和配对缺口。

## 第 29–32 篇 Codex App 专用增量（2026-10-08）

| 能力 | 当前结果 | 不能声称 |
|---|---|---|
| 项目级 Codex App Hook | 人工审查后可显式安装新 `hooks.json`；默认本机脱敏采集 | 尚无用户 App 真实 Hook 记录，`G1=NOT_VERIFIED` |
| 用户本机前台观察 | JSONL 游标和 SQLite 状态持久化、漏写半行等待 | 不证明所有 App 工具路径均可见，不是系统后台服务 |
| 失败/疑似缺终态提醒 | `FAILURE_CLUSTER_REVIEW`、`SUSPECTED_STALL` 保守复核，可选 PowerShell 气泡 | 不确认死循环、模型预测准确率、Windows 通知必达 |
| 备份/恢复 | SQLite 原生在线备份、健康扫描、重启防重复提示 | 无自动还原、更不会让 Codex App 自动重试 |
| 个人试用 | [Windows Codex App Runbook](CODEX_APP_QUICKSTART_29-32.md) | `G3=NOT_EVALUATED`、`G4=NOT_VERIFIED`、不可当正式 V1.0 |

Hook 接收器与 Watcher 没有捕获 prompt、命令或输出，默认删除路径字段。但会话标识仍属于用户本地私有资料。观测器自报来源 `hook_input_unverified`，任何假 Hook 输入都不能作为 Codex App 身份认证。
