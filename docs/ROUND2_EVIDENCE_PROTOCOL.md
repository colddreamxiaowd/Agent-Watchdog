# AW-V2-ROUND2-25-28｜证据合同与准入判断

日期：2026-10-08。项目治理基线：修订计划 v2.0。输入：上一轮 main `fc0b4b101d7e37bd092212bb42c4c331728213e5`。

**不是用户机器的现场验收**：G1 真实 Windows Codex Hook `NOT_VERIFIED`；G3 真实检测评估 `NOT_EVALUATED`。任何来源为 `fixture_only` 的轨迹、手工构造的标签、导出 JSON 或模型成绩文件都不得被展示成“真实准确率”。

## 第一轮遗留的可核实基础

前 24 篇已有 Hook / JSONL / SQLite、`execution_v2.py` 脱敏事件及工具结果、`runtime_v2.py` 弱停滞判断、`task_contract.py` 的批准合同与测试过期规则、`step_links_v2.py` 的人工步骤关联。第 25–28 篇沿用它们，**没有重写整个 Agent**。

## 本轮具体门槛

| 篇 | 新实现 | 计算层 gate | 强声明 gate |
|---|---|---|---|
| 25 | `failure_review_v25.py` 只从明确失败的不同调用产生聚集复核；可选择人工同意图映射 | 跨会话隔离、终态冲突、同类型不同操作正常反例 | 真实、可授权观测的同意图+outcome 案例与人工标签；无则不宣称已检测循环 |
| 26 | `stepwise_compare_v26.py` 可选择性导入离线模型分数（**不会调用模型**） | 相同 test 样本、session-split 无泄漏、冻结阈值、缺分数拒绝结果 | 相同标签与目标定义、可复核模型输入/版本/运行证明、有效正反样本及符合预注册的评估；无则 `NOT_EVALUATED` |
| 27 | `drift_review_v27.py` 原 Git 范围事实+来源未认证的候选建议 | 批准合同 hash、可关联 event_id、建议仍需人工审查 | 用户参与定义原任务的语义偏离标注标准和独立对照，不得将推测升级为事实 |
| 28 | `artifact_acceptance_v28.py` 显式批准的文件预期 SHA256（非测试产物） | 拒绝目录穿越、Git 忽略文件、未批准和改写计划、保护文件变更 | 只可称 `ARTIFACT_BYTES_MATCH_ONLY`，用户终任务完成还需合同的原始验收门槛 |

## 源数据与目标错位是硬性失败条件

StepWise 官方 [仓库](https://github.com/yale-nlp/StepWise)与[ComputerRouter 文档](https://github.com/yale-nlp/StepWise/blob/main/ComputerRouter/README.md)描述：Stuck Monitor 看最近的 rationale/action 文本，训练来源是 GUI 任务轨迹；Milestone Monitor 依赖任务条件。其[训练数据构建脚本](https://github.com/yale-nlp/StepWise/blob/main/ComputerRouter/bert/build_stuck_dataset.py)使用连续多个步骤的文本而非本工程当前的脱敏 Hook 工具元数据。这意味着**不能把模型在原 GUI Benchmark 的 F1 直接外推为 Codex 重复失败判别准确率**，也不能从事件标签无中生有地生成同等输入。第 26 篇只提供独立的评估接口；没有导入权利明确的对应数据，就不下载、不训练、不启动 StepWise。

## 隐私默认值

所有导出数据、评分、人工映射及批准文件都放**用户的私有本地目录**。GitHub 只收示例结构，不收原始提示、命令正文、终端输出、API Key、个人路径、带任务内容的截图或 rollout。README/API 层也不应记录“检测准确率已达多少”这样的未证实数字。相同工具类别只显示“失败聚集需复核”；除非人手工标注同一意图，否则不会猜测命令相同。

## 预注册最低要素（真实试验前必须冻结）

1. `outcome_definition`：例如“经独立人工复核，某段重复失败需要用户干预”，不是“Bash 调用了 N 次”。
2. 数据权利与脱敏规则、原始时间窗、去重和标签分歧处理、真实 provenance；`fixture_only` 永不参与结论。
3. 按会话、项目、时间块的训练/验证/测试隔离与去重；对同一用户任务跨会话重开的情况还应以 **任务 ID** 隔离，避免信息泄漏。当前适配器只校验 session，尚不足以保证任务 ID 层隔离。
4. 固定规则基线、模型的真正输入形式、阈值、正反样本最小数量、指标（precision/recall/F1/不可判定/延迟）、回退与 stop rule。
5. 资源与权重许可、版本、hash、本机 RAM/VRAM 预算；关掉 StepWise 后规则和独立验收仍可以运行。
6. 保留错误分析、人工质检与对“只记录缺失”的盲点说明。模型分数必须是目标数据上真实执行产生，不能造数或事后挑最佳阈值。

建议 stop rule：如果无法获得合规对应输入，停止 StepWise 路线并维持规则优先；如果有数据但预注册的 positives/negatives gate 不满足，报告 `INSUFFICIENT` 而不做优势推断；模型未超过预注册基线门槛或安全性不接受，则 `NO-GO`，不以反复改模型抵消。

## 状态总结

**本轮在工程层可完成 25–28 教学原型与跨平台单元回归；G1/G3/G4 不会自动晋级**。若日后收到真实标注，再新增明确版本的验证报告，不修改此处的历史门槛来追认结果。
