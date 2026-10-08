# 第 21–24 篇：工程安装、断言与兼容说明

本目录是延续第 04–20 篇的参考真源，不是第二套平行产品。**本机真实 Codex 端到端仍为 NOT_VERIFIED**，确认依据必须来自私有的人工现场工作单。

## 源码章节表

| 章 | 新增/修改 | 正例与反例 | 状态 |
|---|---|---|---|
| 21 | `doctor_v21.py`、`hook_runner_v21.cmd` | `doctor` 就绪；人工假 JSON 不算 live；真实 `/hooks` 待本机核验 | 源码+CI / G1 NOT_VERIFIED |
| 22 | `execution_v2.py`、`journal.py` 字段白名单 | 整数退出码／UNKNOWN、字符串“0”不等于数字、敏感正文不落地 | 隔离测试 |
| 23 | `runtime_v2.py` | 长时未结束怀疑；无事件不认定死锁；跨会话不聚集；慢工具完成仅供复核 | 隔离测试；G3 未验证 |
| 24 | `step_links_v2.py`、示例关联模板 | 人工链接成功；孤立 ID=UNLINKED；合同摘要不匹配拒绝；STALE 不升级 | 隔离测试 |

## 使用方法（Anaconda Prompt/CMD）

```bat
cd /d D:\program\agent_watchdog\Agent-Watchdog-v2-eval
python -m unittest discover -s examples\v04\tests -v
python scripts\validate_round1_docs.py
cd examples\v04\watchdog
python doctor_v21.py --repo "D:\program\agent_watchdog\hook_demo_v2"
python runtime_v2.py --events logs\events.jsonl
```

`runtime_v2.py` 的 `--events` 要求已存在的私人脱敏 JSONL；当前没有日志则先完成 [真实接入工作单](../../docs/REAL_CODEX_E2E_RUNBOOK.md)，不应该把凭空建一个空文件当真机成功。`doctor_v21.py` 不自动写入 Codex 配置；新 Runner 只在你审核并信任后手工启用，绝不覆盖旧版 `hook_runner.cmd`。

对于 `codex exec --json` 和 App Server 的**已有授权导出文件**，使用：

```bat
python execution_v2.py import --format exec --input "D:\private\trace.jsonl" --out "logs\exec_safe.jsonl"
python execution_v2.py import --format appserver --input "D:\private\app.ndjson" --out "logs\app_safe.jsonl"
python journal.py sync --log "logs\exec_safe.jsonl"
```

这两条 `import` 不是 live attach。`step_links_v2.py` 需要已有的人工批准任务合同、当前有效的合同 hash、私有映射 JSON；不运行用户任意 shell，也不能通过观察一条事件替换验收。

## 第一次 Windows 运行失败应怎样回退？

1. 退出测试 Codex 会话，关闭带测试 Hook 的临时窗口。
2. 只检查/撤回你**新建测试项目**中的 `.codex\hooks.json`。不要修改原正式项目，也不要修改用户全局 `~/.codex`。
3. 保留必要的本地脱敏证据与出错环境版本；不分享原始 JSONL、完整命令、提示词、API Key 或私人路径。
4. 无完整端到端证据时记录 `NOT_VERIFIED`，不要再用模拟 JSON 替代。
