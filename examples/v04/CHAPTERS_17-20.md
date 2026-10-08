# 第 17–20 篇：安装、测试和 V1.0 发布候选检查

> 四篇为同一个 `examples/v04/watchdog/` 参考工程增加 `supervision.py`、`dashboard.py`、`operations.py`、`release_gate.py`；不会替换旧版 `evidence.py`、`task_contract.py`、`journal.py`。**请先完成第 13 篇真实 Codex 联调，不能把模拟日志当作现场验收。**

## 1. 为什么要区分模块能力与验收事实？

四篇的目标是把现有的功能推向可用，但自动化测试通过并不能证明你的真实 Windows 环境已经接通 Codex。这里需要独立列出已实现范围和还需要你完成的现场验证。

### 正确理解已实现的功能

| 篇章 | 新文件 | 可实现的能力 | 尚未实现/不能证明 |
|---|---|---|---|
| 17 | `supervision.py` | 分离确定性事实与同会话重复工具类别启发式 | 不证明 stuck、同命令失败或语义偏离 |
| 18 | `dashboard.py` | Streamlit 本地只读数据显示 | 不证明全实时、无延迟或远端安全 |
| 19 | `operations.py` | 诊断数据库与快照、显式在线备份 | 不自动恢复、长期可靠性没有经过现场实验 |
| 20 | `release_gate.py` | 未达人工验收条件时阻断发布 | 不自动创建 Release；声明 JSON 不构成认证 |

## 2. Windows 11 安装（Anaconda Prompt / cmd）

前提：Python 3.9+、Git、旧 `watchdog` 目录已根据第 04–16 篇完成配置。

不要覆盖你的 `evidence.py`。从 GitHub 项目 `examples/v04/watchdog/` **仅复制四个新增文件**到 `D:\program\agent_watchdog\watchdog\`，此前各模块需要已存在。

```bat
conda activate torch_env
cd /d D:\program\agent_watchdog\watchdog
python supervision.py --repo "D:\program\agent_watchdog\hook_demo"
```

Web（依赖 Streamlit，首次使用若尚未安装才安装）：

```bat
python -c "import streamlit;print(streamlit.__version__)"
python -m pip install "streamlit>=1.37,<2"
python -m streamlit run dashboard.py -- --repo "D:\program\agent_watchdog\hook_demo"
```

第二条 `pip install` 仅在环境里没有兼容 Streamlit 时运行，不必每次重复安装。

运维诊断与备份：

```bat
python operations.py --repo "D:\program\agent_watchdog\hook_demo" doctor
python operations.py --repo "D:\program\agent_watchdog\hook_demo" backup --out "D:\program\agent_watchdog\watchdog_backup\events_001.sqlite3"
```

未验收时阻断正式发布：

```bat
python release_gate.py --repo "D:\program\agent_watchdog\hook_demo" --db "D:\program\agent_watchdog\watchdog\data\journal.sqlite3"
```

## 3. 自动化测试（从仓库根目录）

```bat
python -m unittest discover -s examples\v04\tests -v
```

这个测试只在临时 Git 仓库模拟事件，不读取你的真正 Codex 数据，也不会证明 Windows 集成已经完成。

## 4. 发布前逐项签署的现场验收

建议将 [RELEASE_ATTESTATION.example.json](RELEASE_ATTESTATION.example.json) **复制到仓库之外**，逐项检查并更新：

- [ ] `real_codex_hook`：在真实 Codex 会话下观察到受信任 Hook，核对来源与对应任务。
- [ ] `cross_repo_isolation`：两个真实项目不能串台。
- [ ] `claim_not_completion`：有过期或失败验收时，即使 Agent 说完成，状态也不得成为 `VERIFIED_COMPLETE`。
- [ ] `test_stale_on_change`：测试通过之后相关 Git 可见文件变化，旧测试证据变为 `STALE`。
- [ ] `backup_restore`：成功备份并在隔离副本中检查/恢复，保留原始数据。
- [ ] `local_dashboard`：本机页面能够显示状态、风险和最近事件；浏览器关闭不会要求 Codex 停止。
- [ ] `safety_review`：检查敏感数据、日志保留、访问权限、第三方许可证及公开提交内容。

`release_gate.py` 对全部 `true` 的 JSON 最多返回 `READY_FOR_HUMAN_RELEASE_REVIEW`；**不能验证签署记录来源，也不能代替最终的人类审查**。现场通过前，不应宣称已发布 V1.0。

## 5. 关键安全和数据限制

- 不将原始命令、工具输出、提示词、API Key 上传 GitHub。
- `st.fragment(run_every='5s')` 是页面刷新频率，不保证最多五秒的事件到达延迟。
- SQLite 诊断通过只是数据可读，不代表真实 Agent 在线。
- `events.jsonl` 和数据库不应加入仓库，备份也应放在仓库外。
- 发布门槛缺少证据时应为 `BLOCKED`；没有“自动声明已完成”的后门。

## 6. 资料

- [第 17 篇](../../从零开发%20Agent%20Watchdog（17）.md)
- [第 18 篇](../../从零开发%20Agent%20Watchdog（18）.md)
- [第 19 篇](../../从零开发%20Agent%20Watchdog（19）.md)
- [第 20 篇](../../从零开发%20Agent%20Watchdog（20）.md)
- [第 13–16 篇本机验收](CHAPTERS_13-16.md)
