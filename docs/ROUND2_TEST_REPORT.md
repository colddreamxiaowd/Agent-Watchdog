# AW-V2-ROUND2-25-28 — 真实执行记录、自动测试与能力边界

日期：2026-10-08。第一轮 main 基线：`fc0b4b101d7e37bd092212bb42c4c331728213e5`。本轮在分支 `feature/aw-v2-round2-25-28` 增量开发，不覆盖既有 Hook Runner、`evidence.py`、`task_contract.py`、`journal.py`。

## 已实际执行的跨平台隔离回归

- 初始 [CI 37787357776](https://github.com/colddreamxiaowd/Agent-Watchdog/actions/runs/37787357776) **失败**：Windows 测试产物在 `write_text("expected bytes\\n")` 下可能发生 CRLF 转换；预期哈希按 LF 字节计算，Windows `REVIEW_REQUIRED` 而 Linux 能匹配。这里暴露的是测试夹具不跨平台，不是“真实模型识别到了异常”。
- 将夹具改为确定性的 `write_bytes(b"expected bytes\\n")`；不修改实际监督目标的文件文本。修复后 [CI 37788433028](https://github.com/colddreamxiaowd/Agent-Watchdog/actions/runs/37788433028) Ubuntu 与 Windows（Python 3.11 托管 Runner）**均 SUCCESS：每个平台 66 项测试，OK；13 份 Markdown 文件链接/结构检查 0 错误**。
- README/第 25–28 篇目录与链接检查之后继续运行 CI；上述 13 份是提交 `5d653a6e7d0e959e9174822f459d4e4217db3567` 的观察值。最终报告的提交 SHA 还需由 GitHub 当前 Actions 复核，不把旧提交的通过记录冒充新提交。

**新增一项 F1=0 的回归检查，最新套件应为 67 项（原有 47 项 + 本轮 20 项）；原先 66 项 CI 仅对应加入该修正之前的提交**；包括明确失败、六次 Bash 全成功、跨会话隔离、工具终态冲突、人工同意图分组、训练/测试泄漏、冻结阈值缺失、模型分数缺失、测试正例门槛、合同版本锚定、Git 保护路径、产物哈希匹配与被更改的计划阻断。所有测试都是在自动创建的临时环境/fixture 上运行；**没有在你的 Windows 11 实机上与真实 Codex 做 G1/G3 的现场验证**。

## 每篇真正实现的范围

| 章 | 工程证据 | 人工审核与未知 |
|---|---|---|
| 25 | `failure_review_v25.py` 用 `source/session/turn/tool_use_id` 去重，明确失败才进入复核；人工分组可标可能恢复 | 不能凭 Bash 类型判断同命令；没有真实无效循环的 TP/FP/FN |
| 26 | `stepwise_compare_v26.py` 同留出集配对计算、泄漏/缺分数/阈值/类别门槛 | **本轮没有调用 StepWise、没有下载权重、没有在 Codex 上产生其预测**；示例只是合成数学测试 |
| 27 | `drift_review_v27.py` 复用审批合同与 Git 范围事实，候选绑定事件 ID；外部声称 confirmed 无效 | 没有外部身份真实性保障、自然语言原始目标理解或独立人工语义数据 |
| 28 | `artifact_acceptance_v28.py` 审批计划与 Git 可见范围内文件的期望 SHA256，检查路径穿越与合同变更 | 匹配的是预期字节，**不是**任务最终完成；审批 JSON 同权限可被改写，尚无 OS 级可信授权 |

## 项目门槛状态

- G0：代码基线复核、托管 Linux/Windows 自动回归可核对；实际用户系统版本与安装状态还缺现场记录。
- G1：`NOT_VERIFIED`，仍需 [真实 Codex Hook 工作单](REAL_CODEX_E2E_RUNBOOK.md)。
- G2：已有有界适配与自动单测；本机 Codex 版本的覆盖率仍未知。
- G3：`NOT_EVALUATED`：没有代表性真实回合、独立人工标签、误报/漏报/延迟/不可判定测量。小模型与规则的增益不能声明。
- G4：`NOT_VERIFIED`，长期恢复、主动提醒冷却、隐私与发布审核未完成。

## 下一轮（29–32）建议

可以继续低风险实现 Windows 提醒、去重冷却、现有模块复用调查、故障注入与恢复工作单，但绝不能把编写第 32 篇等价于产品正式发布。**真实 G1/G3/G4 关口只会在用户提供现场证明或合规真实轨迹并独立复核后晋级**。没有足够案例时，优先稳健规则与人工建议，不编造 ML 优势。

参阅：[本轮评估协议](ROUND2_EVIDENCE_PROTOCOL.md) · [Windows 操作清单](ROUND2_WINDOWS_RUNBOOK.md) · [第 25–28 篇源码使用指南](../examples/v04/CHAPTERS_25-28.md)。
