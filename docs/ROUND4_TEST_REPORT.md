# Round 4：Codex App 任务级监督闭环——测试记录与范围

日期 2026-10-09。基线 GitHub main `e939e92dcd5ede094ac719fe2d69cd13c895306f`。本轮第 34–37 篇面向用户预期的“目标→进展→验收→风险提醒”增加参考工程，**不将合成案例当成真实 App 使用效果**。

- v34 通过已有脱敏事件的最近会话 alias，由用户人工核对项目并明确批准绑定 Git + 合同；别名不等于来源认证。
- v35 合并现有 `task_contract.py` / `scope_guard.py` / `evidence.py` 的结果；明确不能认定 Git 变更作者或自然语言完整性。
- v36 持久化基于合同/文件范围/验收状态的证据指纹，首次轮询不弹旧历史；重复稳态不再通知，**A→B→A 复发通知另有 revision 区分**。
- v37 一个 CLI 提供 `sessions` / `bind` / `overview` / `watch`，统一事件风险和任务风险，未执行测试/修改配置/杀掉 Codex。
- [Windows 实操与边界](ROUND4_TASK_LOOP_RUNBOOK.md) · [完整隔离测试](../examples/v04/tests/test_round4.py)。

**阶段回归故障不能删除**：初次 Linux 120 用例中有一条“测试用 mock 抹掉会话后再次从 mock 获取 alias”的断言顺序问题；初次 Windows 120 用例中还有测试夹具 Git 根目录路径表示不一致导致合同状态找不到的问题。两者均在后续补丁改正。终版 CI 测试数量和最终 SHA 应以合并前 GitHub Actions 的实际结果为准，严禁先填“全部通过”。

G1：用户曾报告真实 Windows Codex Desktop 事件链已收集，未在本轮独立读取私有日志，Hook 正常信任仍需现场审核。G2：代码隔离回归；G3：真实人类标注误报漏报未检验。G4：休眠/多天可靠性/通知显示未验。**任务闭环是经用户批准的参考原型，不是正式无人值守产品。**
