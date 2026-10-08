# Agent Watchdog · 第 13–16 篇本机验收工作单

这是一张**需要用户在自己的 Windows Codex 环境中填写**的验收表。不要把模拟日志或隔离 `unittest` 通过填成真实端到端已通过。

## 当前交付

- 第 13 篇：`integration_check.py`，只读联调就绪报告。
- 第 14 篇：`appserver_adapter.py`，导入明确提供的 NDJSON 导出并剔除命令、提示及输出。
- 第 15 篇：`progress.py`，从已批准合同与当前快照计算验收项、里程碑状态。
- 第 16 篇：`scope_guard.py`，复核受保护路径和超出声明范围的 Git 文件变化。

## 执行前检查

- [ ] 确认 `where python` 是正在用的 Conda 环境。
- [ ] 确认 `codex --version` 可用（否则先查 CLI 安装和 PATH）。
- [ ] 核对 Hook runner 真实绝对路径和当前 Codex 版本 Hook 信任状态。
- [ ] 仅使用安全的 `hook_demo` 仓库测试，不操作真实研究项目。
- [ ] 已审核合同验收命令；Hook 或 Bridge 都不应自动执行测试。

## 真实 Codex 端到端验收

| 步骤 | 预期观察 | 本机时间/截图/日志/结果 |
|---|---|---|
| 1. 真实 Codex 在 `hook_demo` 启动 | 当前会话可辨认 | 未填写 |
| 2. Hook 已加载并受信任 | 管理界面可核对 | 未填写 |
| 3. Codex 实际完成一次本地工具操作 | CLI 中能看到结果 | 未填写 |
| 4. Logger 同窗口收到对应事件 | 脱敏事件信息 | 未填写 |
| 5. Bridge 读取 Git 变更 | `changed` 与真实文件一致 | 未填写 |
| 6. 指定验收测试通过 | `PASSED` 与退出码 | 未填写 |
| 7. 修改文件后旧测试变过期 | `STALE` | 未填写 |
| 8. `journal.py` 备份并重启 | integrity=ok；状态可重新计算 | 未填写 |
| 9. App Server 脱敏导入 | 原命令/输出未写入日志 | 未填写 |
| 10. 范围与里程碑报告 | `progress.py` / `scope_guard.py` 与实际一致 | 未填写 |

## 真实性声明

离线样例证明的是代码在构造输入下如何运行，不证明事件来自 Codex。`integration_check.py` 会始终保持 `real_codex_end_to_end=NOT_VERIFIED`；真实联调是否通过由用户保留的现场记录来确认。

Git 文件变化不能无条件归因给 Codex。`appserver_adapter.py` **不启动实时连接**，只读取使用者明确提供的已导出通知。第 16 篇路径越界信号不能代替语义行为审查。
