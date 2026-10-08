# Agent Watchdog 第 25–28 篇｜Windows 本机离线验收单

状态：`REQUIRES_WINDOWS_VALIDATION`；本文件是操作步骤，**不是已执行的真实记录**。第 21 篇真实 Codex 的 G1 工作单仍是前置：[真实 E2E](REAL_CODEX_E2E_RUNBOOK.md)。

## A. 下载并回归（Anaconda Prompt，CMD）

选择**不存在的**新目录以保护你的旧 `D:\program\agent_watchdog\watchdog`，不在正式研究仓库试运行：

```bat
conda activate torch_env
git clone --branch feature/aw-v2-round2-25-28 https://github.com/colddreamxiaowd/Agent-Watchdog.git D:\program\agent_watchdog\Agent-Watchdog-v2-round2-eval
cd /d D:\program\agent_watchdog\Agent-Watchdog-v2-round2-eval
python --version
git --version
codex --version
python -m unittest discover -s examples\v04\tests -v
python scripts\validate_round1_docs.py
```

若最终已经合并到 main，可以直接切换为 main；上述 branch 用于保存本轮可复核版本。代码测试不需要 GPU、不自动安装或下载 StepWise、不会运行 Codex。

## B. 25：明确失败聚集，排除无效循环误报

先在测试克隆中阅读以下源码和合成 fixture；**不要复制任何私有 raw trace 到公开仓库**：

```bat
cd /d D:\program\agent_watchdog\Agent-Watchdog-v2-round2-eval\examples\v04\watchdog
python failure_review_v25.py --events "logs\events.jsonl" --min-failures 3
```

需要提前按第 21 篇生成 `logs\events.jsonl`。如果还没有真实日志，可仅运行完整 unittest 查看人工 fixture 的测试。这个 CLI 只对**明确 FAILED + 稳定 tool_use_id** 的调用产生复核提示，不能声称脚本发生死循环。带人工意图映射时额外给 `--manual-groups D:\private\groups.json`，例子见 `failure_groups.example.json`，必须填真实经过许可的 ID。

## C. 26：自愿导入模型分数，不执行 StepWise

```bat
python stepwise_compare_v26.py --protocol stepwise_protocol.example.json --samples stepwise_samples.example.json
```

示例中模型分数均是 `null`，预期 `external_model=NOT_EVALUATED`。**不允许**据此声称模型优势。真正比较之前需要取得授权的逐步文本输入、明确真实模型权重/版本与阈值，再按 [证据协议](ROUND2_EVIDENCE_PROTOCOL.md) 另行预注册。不能直接将 StepWise 的 GUI Stuck 标签视作 Codex 重复失败标签。

## D. 27：关联真实 Git 范围差异与待复核建议

只有当临时测试仓库已有**批准的 Task Contract**：

```bat
python drift_review_v27.py --repo "D:\program\agent_watchdog\hook_demo_v2"
```

即使显示 `NO_FINDINGS_IN_OBSERVED_SCOPE`，也仅表示当前受观察的 Git 范围没发现匹配问题，不是“Agent 目标正确”。可选择提供结构化 `--events logs\events.jsonl --candidates D:\private\drift.json`，若 event_id/合同 hash 对不上必须失败。

**反例**：手工修改测试仓库中原来受保护的 `GOAL.md`，应该产生 `PROTECTED_CHANGE`，但修改作者应为 `UNKNOWN`。

## E. 28：批准不可执行的产物核验计划

在 **私有本地文件夹** 根据 `artifact_plan.example.json` 填写批准的 SHA-256 期望值（必须在验收之前由人批准），并使用测试仓库已有的合同 hash：

```bat
python artifact_acceptance_v28.py --repo "D:\program\agent_watchdog\hook_demo_v2" init --plan "D:\private\artifact_plan.json"
python artifact_acceptance_v28.py --repo "D:\program\agent_watchdog\hook_demo_v2" approve
python artifact_acceptance_v28.py --repo "D:\program\agent_watchdog\hook_demo_v2" status
```

`init` 拒绝覆盖已有计划。`approve` 是用户显式认可的动作，不由 Hook、Codex、LLM 或浏览器自发进行。匹配结果 `ARTIFACT_BYTES_MATCH_ONLY` 仅证明一个**预先批准的文件预期哈希**与当前字节一致，不证明 UI、网络或业务已经完成，也不会写回 `task_contract.py` 的验收结果。

**反例**：更改报告文件 → `MISMATCH`；更改 GOAL.md → `BLOCKED_PROTECTED_FILE_CHANGE`；把计划指向 `../outside` → 拒绝；修改计划 JSON 却不重新批准 → `BLOCKED_UNAPPROVED_OR_CHANGED_PLAN`；Git 忽略文件 → `NOT_IN_GIT_VISIBLE_SCOPE`。

## 本机记录表（私有保存）

| 事项 | 填写 |
|---|---|
| Windows / Python / Git / Codex 版本 | 未验收 |
| 本次仓库 HEAD 与源码 SHA | 未验收 |
| G1 Hook 与工具真实执行的映射 | NOT_VERIFIED |
| 25 重复失败真阳性/假阳性案例 | 未收集 |
| 26 是否实际运行 StepWise / 权重哈希 | 未运行 / 未验证 |
| 27 人工复核的目标偏离案例 | 未收集 |
| 28 审核的合同、预期 hash 与独立结果 | 未验收 |
| 隐私/日志审计 | 未验收 |

**不要将这张空白记录表改写成全部 PASS；用户真正填表之前仍未通过真实现场验收。**
