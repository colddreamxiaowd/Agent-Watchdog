# 第 25–28 篇：增量源码、实验对照与兼容使用

## 读者起点

延续 [第 21–24 篇](CHAPTERS_21-24.md) 的 `examples/v04/watchdog/` 工程。**不要覆盖 Windows 本机 `D:\program\agent_watchdog\watchdog`；在新目录克隆本轮分支并先跑全套回归**。GitHub Actions 的 Windows Runner 不等于真实 Codex 本机接入。

| 章 | 文件 | 核心结果 | 不能声明 |
|---|---|---|---|
| 25 | `failure_review_v25.py`、`failure_groups.example.json` | 稳定调用 ID 的明确失败聚集/人工同意图分组 | 同命令/死循环/自动恢复 |
| 26 | `stepwise_compare_v26.py`、`stepwise_protocol.example.json`、`stepwise_samples.example.json` | 预注册阈值与同一留出集上的两种评分 | 已运行 StepWise/已获得真实增益 |
| 27 | `drift_review_v27.py`、`drift_candidates.example.json` | 批准合同约束下的范围事实+待审建议 | 语义违规已证实 |
| 28 | `artifact_acceptance_v28.py`、`artifact_plan.example.json` | 批准计划后预期字节哈希核对 | 整个用户任务已完成 |

## 命令范例（Anaconda Prompt/CMD）

```bat
cd /d D:\program\agent_watchdog\Agent-Watchdog-v2-round2-eval
python -m unittest discover -s examples\v04\tests -v
python scripts\validate_round1_docs.py
cd examples\v04\watchdog
python stepwise_compare_v26.py --protocol stepwise_protocol.example.json --samples stepwise_samples.example.json
```

注意示例比较应出现 `external_model=NOT_EVALUATED`，因为没有真实模型分数。另三个模块分别要求已存在的脱敏 `events.jsonl`、批准 Task Contract、可选人工映射或经批准产物计划；没有这些数据就保留 `UNKNOWN`，不要造一个“真实”输出。

完整可复制 Windows 步骤：[docs/ROUND2_WINDOWS_RUNBOOK.md](../../docs/ROUND2_WINDOWS_RUNBOOK.md)。真实实验前的标签和资源条件：[docs/ROUND2_EVIDENCE_PROTOCOL.md](../../docs/ROUND2_EVIDENCE_PROTOCOL.md)。

## 兼容与隐私

所有 JSON 示例均为 **synthetic 或占位结构**；请先复制到仓库外的私有目录再填写，不把真实会话 ID、命令、路径、提示词、模型轨迹提交 GitHub。可单独停用所有四个新模块，旧的 Hook / Bridge / JSONL / SQLite / Task Contract 不依赖它们。不运行未知 shell 命令，不自动杀进程、回滚或修改合同。
