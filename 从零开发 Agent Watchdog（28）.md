# 从零开发 Agent Watchdog（28）：Agent 说交付了报告，怎么证明？把非测试产物接入独立验收

> 第 28 篇 · 任务契约 · Git 文件指纹 · 人工批准 · 安全路径 · Windows 跨平台回归  
> **本篇能够证明预期字节与当前文件一致，不能替用户确认报告内容有用、UI 可用或整个项目完成。**

## 一、通过单元测试之后，为什么你的任务仍可能没完成？

你要求 Codex 做一份技术报告，交付 `docs/report.md`，同时不要改动 `GOAL.md`。Codex 最后回复：“所有 Python 测试通过，报告已完成。”听起来没问题，但你一打开文件发现报告是旧版本，或者 `report.md` 根本不存在，只是脚本测试成功退出了。

第 03 篇的 `evidence.py` 能检查文件是否发生过变化、测试执行退出码是否为 0。第 06 篇的 `task_contract.py` 又能对人类批准的某个测试保存 `PASSED/FAILED/STALE/INCONCLUSIVE`。这些都很有价值，但不等于验收所有类型的工作成果。

真实的软件开发还有很多不是单元测试的任务：生成指定的 JSON 配置、导出报表、提供模型产物、编写文件、配置文档、提交某个清单。为了让独立监督器向你的原始目标靠近，我们需要一种**不运行任何陌生命令、也不信任 Agent 自述**的非测试验收途径。

第一版选择最容易解释和独立复核的一种：由**用户事先批准**某个相对路径应存在的文件，以及期望它的确切 SHA-256 摘要。然后 Watchdog 在验收时自己读取字节重新计算。

这个能力看似简单，却比“发现 Agent 调用了 apply_patch”多了一层证据：**现在的产物确实匹配某个已经得到用户批准的预期内容。**

## 二、这里所谓“完成”其实有四种不同的层级

```text
1. Agent 宣称 report.md 已经完成
   └─ 只是 Agent 的说法

2. Git 快照发现 report.md 文件存在/变化
   └─ 说明观察到了文件，不说明其内容正确

3. 计算 SHA-256，等于用户提前批准的预期摘要
   └─ 说明当前文件字节符合那个已批准期望

4. 业务验收：用户检查内容、部署效果、外部 API、其他副作用
   └─ 仍可能需要完全不同的独立观察工具
```

第 28 篇只实现第 3 层。因此状态取名 `ARTIFACT_BYTES_MATCH_ONLY`，而不是 `VERIFIED_COMPLETE`。

为什么这个区别重要？假设 Agent 为一份毫无价值的空报告准备了哈希，随后自己提交这份报告和对应哈希，系统也会匹配。这证明的只是“文件与 Agent 自己选择的期望相同”，不是“满足用户原始需求”。所以**期望哈希必须由你事先审查并明确批准**。批准本身还需要可信流程；一个 JSON 中写着 `approved=true` 也不能代替你本人真的确认过。

## 三、沿用已批准的 Task Contract，不能另建第二套目标

新的 [artifact_acceptance_v28.py](examples/v04/watchdog/artifact_acceptance_v28.py) 会先调用旧 `task_contract.load()`，确认原合同还在并且此前已批准的 SHA-256 与当前版本一致。没有合同，或者合同被后来修改而未重新批准，就不能开始产物验收。

产物计划是第二层、专门描述“哪些文件的哪些字节需要核对”的数据。为避免产物计划偷偷修改目标，它也需要携带当前原合同的 `contract_sha256`。例如：

```json
{
  "schema_version": 1,
  "contract_sha256": "由 task_contract.py status 给出的哈希",
  "checks": [
    {
      "id": "report_bytes",
      "path": "report.txt",
      "sha256": "已批准的64位小写SHA256十六进制值"
    }
  ]
}
```

这只是结构说明，不能直接复制这些中文占位符当作有效计划。真实示例放在 [artifact_plan.example.json](examples/v04/watchdog/artifact_plan.example.json)，使用前应放到**被监控仓库之外的私人目录**并按本机实际批准值填写。

为什么计划也要有一次 `approve`？因为人类可能在准备工作单时写错文件名或摘要。脚本应把“正在起草”和“已经批准”分开，之后修改文件或计划便不能静默继承同一次批准。

## 四、实际计算的不是文件名、大小，而是原始字节

核心逻辑使用 Python 标准库的 `hashlib.sha256()`，逐块读取：

```python
actual = hashlib.sha256()
with target.open("rb") as fd:
    for chunk in iter(lambda: fd.read(1024 * 1024), b""):
        actual.update(chunk)
matched = actual.hexdigest() == expected_sha256
```

这段代码保留三个重要特征。首先使用 `rb` 二进制读取，而不是文本模式，避免编码/换行转换。其次按 1 MiB 块读取，不要求把整个文件塞进内存。最后明确限制单个产物最大 20 MiB，超出则返回 `OVERSIZED`，而不是为了验收未知大文件把电脑资源耗尽。

你可以把 SHA-256 理解为一份内容的高强度指纹；任何字节变化几乎都会得到不同的摘要。但它并不理解语义：“报告里只改了一个错别字”依然会改变指纹，这正是本章的保守预期。

这里还有一个我们**真的在工程测试中撞上的 Windows 坑**。最初的测试在 Windows 用：

```python
Path("report.txt").write_text("expected bytes\n")
```

Windows 文本写入可能自动把换行转换为 CRLF，于是文件实际字节与 Linux 的 LF 不同，预先按 LF 算好的 SHA-256 就不匹配。托管 Windows CI 因此失败，而 Ubuntu 可以通过。测试后来改成：

```python
Path("report.txt").write_bytes(b"expected bytes\n")
```

这样测试的**原始字节**在两个平台才真正一致。这个经验说明：哈希不是“文件内容看着差不多”的语义比较；我们选择字节级验收，就要把字节级细节纳入测试。

## 五、独立验收最危险的部分其实是路径

如果程序接受一个任意路径并调用 `Path.read_bytes()`，那么攻击者只需把计划路径写成：

```text
../../secrets/api_key.txt
```

Watchdog 就可能读取被监控仓库以外的敏感文件。尽管我们不保存文件正文，这仍不符合最小权限原则。

因此 `artifact_acceptance_v28.py` 要求 `checks[].path` 是仓库内的**相对 POSIX 路径**，拒绝绝对路径、`..` 穿越、反斜杠、NUL 等输入；访问前还会检查最终路径不逃出 Git 仓库。遇到符号链接，不假装其目标文件属于正常产物。所有检查都与 Git 可见文件清单对照。

这也意味着：如果被验证的文件已经被 `.gitignore` 排除，结果应是 `NOT_IN_GIT_VISIBLE_SCOPE`。我们不能无声地跨出此前明确约定的观察范围。未来如需验收外部数据库、浏览器页面或用户私有文件，要设计单独的授权适配器，而不是把路径保护取消。

## 六、怎么确保 Agent 不能改掉验收标准？

本章有两个明确写入操作，但它们**只写 Watchdog 自己在外部维护的元数据**，不会自动修改 Codex 工作区：

```text
artifact_acceptance_v28.py init
      └─ 保存一份未批准的 artifact_plan_v28.json
           │
           ▼
用户阅读内容，显式执行 approve
      └─ 保存 artifact_approval_v28.json（计划摘要）
           │
           ▼
artifact_acceptance_v28.py status
      ├─ 原合同是否仍受批准？
      ├─ 当前计划摘要与批准文件一致？
      ├─ 是否存在可信初始 Git baseline？
      ├─ 是否改动了受保护文件？
      └─ 产物字节与预期是否匹配？
```

如果用户后来修改了计划文件，却没重新批准，直接 `BLOCKED_UNAPPROVED_OR_CHANGED_PLAN`。如果没有旧 Git 基线，返回 `NO_BASELINE`。如果 `GOAL.md` 被修改，返回 `BLOCKED_PROTECTED_FILE_CHANGE`，不因为报告哈希正确就给它一个绿色的“完成”。

更重要的是这个模块根本不会修改 `task_contract.py` 的 `acceptance_results.json`，也不会将文件字节匹配升级成完整的 `VERIFIED_COMPLETE`。两个验收机制分别回答不同的问题，不能绕过原合同。

## 七、Windows 上完整实践一次

先按 [第 25–28 篇 Windows 工作单](docs/ROUND2_WINDOWS_RUNBOOK.md)创建单独的验证克隆，再在**临时** `hook_demo_v2` 仓库中准备批准的任务合同、Git 基线和你已经审核过的预期产物。

在 Anaconda Prompt（CMD）中：

```bat
conda activate torch_env
cd /d D:\program\agent_watchdog\Agent-Watchdog-v2-round2-eval\examples\v04\watchdog

python task_contract.py --repo "D:\program\agent_watchdog\hook_demo_v2" status
python artifact_acceptance_v28.py --repo "D:\program\agent_watchdog\hook_demo_v2" init --plan "D:\private\artifact_plan.json"
python artifact_acceptance_v28.py --repo "D:\program\agent_watchdog\hook_demo_v2" approve
python artifact_acceptance_v28.py --repo "D:\program\agent_watchdog\hook_demo_v2" status
```

**不要盲目照抄 approve。** 你必须先打开计划核对具体文件名和 SHA-256；实际产品还需要更强的身份确认与权限边界。这里的 CLI 明确是一次人工批准，不是 Hook 自动执行。`init` 如果发现同一仓库已有计划会拒绝覆盖，避免把原本批准过的标准改掉。

如果你的合同或练习仓库与这组示例不同，按实际路径调整；不要直接在正在研究的正式仓库上试验未审核的验收配置。

## 八、反例比“匹配成功”更能证明这个功能可靠

**反例 A：文件被修改。** 先在批准计划时指向原始预期文件，然后把报告中的一个字节改掉。结果必须变成 `MISMATCH`；如果仍显示匹配，说明检查读的不是当前文件。

**反例 B：GOAL.md 被修改。** 即使报告字节完美匹配，也必须返回 `BLOCKED_PROTECTED_FILE_CHANGE`。这能证明产物检查没有盖过你最初批准的安全范围。

**反例 C：试图读仓库外文件。** `path="../outside.txt"` 应被拒绝。符号链接、Git 忽略文件、超大产物也不应偷偷算作有效的预期匹配。

**反例 D：偷偷换掉计划摘要。** 改写 `artifact_plan_v28.json` 的 SHA-256 值，却不重新经过人工批准，结果必须阻断。不能让 Agent 一边改文件一边改计划、再宣布自己匹配成功。

**反例 E：测试仍未运行。** 产物完全匹配，但 Task Contract 的某项单元测试还是 `NOT_TESTED`。程序最多报告 `ARTIFACT_BYTES_MATCH_ONLY`，原合同阶段仍是 `IN_PROGRESS`。这是本篇最重要的防过度结论。

这些断言都在 [test_round2.py](examples/v04/tests/test_round2.py)。与第 26 篇不同，它们不需要模型分数；与第 21 篇不同，GitHub Hosted Windows 跑通它们并不能替你证明真实 Codex 执行时没有丢事件。

## 九、我们现在到底做出了哪一部分真正的 Watchdog？

经过第 25–28 篇，我们拥有了四个互相不抢话的部件：失败序列的保守复核、可选择的小模型成对评价框架、锚定批准合同的目标偏离线索，以及预先批准期望字节的非测试产物检查。

它们都遵守一条原则：**Agent 可以提供线索，但不应当自证全部完成。** 监督器更不应该在没有足够数据时编造“正常、成功、已完成”的标签。

当前还欠真实 Windows Codex 轨迹、多天恢复、样本人工标注、StepWise 适配与误报率、外部浏览器/API/服务副作用的可信验收。我们没有忽略这些，而是让它们成为后续明确要完成的产品门槛。

下一轮第 29–32 篇将走向个人软件体验：Windows 主动通知与去重、开源模块真实复用决策、长时恢复和可撤回的安装/发布。**只有 G0–G4 所需证据齐全，才有资格宣布正式 V1.0**；增加文章数量不能代替用户现场审核。

源码：[artifact_acceptance_v28.py](examples/v04/watchdog/artifact_acceptance_v28.py) · [产品门槛](docs/PRODUCT_REQUIREMENTS_V2.md) · [本轮真机工作单](docs/ROUND2_WINDOWS_RUNBOOK.md)。
