# 从零开发 Agent Watchdog（06）：独立验收不是“看到 PASSED”，而是知道 PASSED 证明了什么

> **系列教程 · 第 6 篇** · Windows 11 · unittest · subprocess · Git fingerprint  
> 从第 05 篇已经获批准的 Task Contract 出发，为每一项验收分别保存证据。

你可能遇到过这样的情况：Codex 先运行了单元测试，显示绿色的 `OK`，随后继续改代码并回复“完成”。如果一个监督系统只保存“最近一次测试通过”，它会把**对旧代码的证明**误当成**对新代码的证明**。

这一篇我们要建立一条比“执行完成”严格得多的证据链。

## 一、从一个反直觉的实验开始

先准备 `hello.py`：

```python
def greet():
    return "Hello Agent Watchdog"
```

以及 `test_hello.py`：

```python
import unittest
from hello import greet

class GreetingTest(unittest.TestCase):
    def test_greet(self):
        self.assertEqual(greet(), "Hello Agent Watchdog")
```

运行测试，得到 `OK`。此时立刻在 `hello.py` 最后一行添加：

```python
# just a comment
```

功能没有变化，测试也可能仍通过。可监督器应该继续保留原来的 PASSED 吗？

**第一版选择保守答案：不能。** 因为我们记录的是“当时某一版文件通过了某个命令”，不是“软件在任何后续更改后都会保持正确”。高级版本将允许按依赖范围判断哪些文件与哪些检查相关，但那需要额外证据，不能现在猜测。

## 二、测试证据至少需要四个字段

```json
{
  "before": "sha256:...",
  "after": "sha256:...",
  "exit_code": 0,
  "command": ["python", "-m", "unittest", "test_hello.py", "-v"]
}
```

`before` 是执行测试前的 Git 可见文件指纹；`after` 是测试结束后的指纹。若二者不同，就意味着测试本身修改了被监控的文件，或者测试期间有其他并发修改；即使退出码为 0，也应标记为 `INCONCLUSIVE` 而不是直接相信。

如果 `before == after`，我们再检查当前指纹：

```text
测试从未运行                    NOT_TESTED
测试期间文件变化                INCONCLUSIVE
执行后文件又变化                STALE
退出码非 0 且快照匹配           FAILED
退出码 0 且快照匹配            PASSED
```

注意优先级：`STALE` 并非说那次测试当时失败了；只是说它不足以证明**现在这版文件**通过测试。

## 三、为什么第三篇已有测试记录，这一篇还要新建？

第三篇的 `evidence.py` 只有 `last_test.json`，很适合学习“最后一个测试”状态。但合同可以有 A1、A2、A3 三项要求。如果执行 A2 覆盖 A1，我们就不知道 A1 是否真的通过。

因此这次并不是重复造轮子，而是复用第三篇的三项基础函数：

```python
before = evidence.fingerprint(evidence.snapshot(repo))
# 运行已经批准的命令
...
after = evidence.fingerprint(evidence.snapshot(repo))
```

再把每一项结果按验收 ID 保存：

```text
state/<仓库标识>/
├── baseline.json
├── last_test.json               ← 第 03 篇，保留
├── task_contract.json           ← 第 05 篇
├── contract_approval.json
└── acceptance_results.json      ← 第 06 篇，每项独立保存
```

你可以直接阅读 `task_contract.py` 里的 `run_one()` 和 `acceptance_status()`：我们没有要求重新运行一个新的 `evidence.py` 安装程序，更没有让 Codex 去修改内部数据库。

## 四、第一次验收：A1 与 A2 必须分别执行

先确认第 05 篇已批准合同，并且 `hook_demo` 中的 `hello.py` 与 `test_hello.py` 可以正常运行。

```bat
conda activate torch_env
cd /d D:\program\agent_watchdog\watchdog
python task_contract.py --repo "D:\program\agent_watchdog\hook_demo" status
```

然后执行 A1：

```bat
python task_contract.py --repo "D:\program\agent_watchdog\hook_demo" verify A1
```

**这是一个主动运行测试的命令，会执行你批准的 Python 测试文件。** 本篇只应使用你自己信任的 `hook_demo`，切勿对不认识的外部仓库照抄此命令。

随后再执行：

```bat
python task_contract.py --repo "D:\program\agent_watchdog\hook_demo" verify A2
python task_contract.py --repo "D:\program\agent_watchdog\hook_demo" status
```

如果两项测试确实全部成功、执行过程中没有 Git 可见文件变化、原始基线可用且没有受保护文件变更，当前教学规则才能显示 `VERIFIED_COMPLETE`。

请认真理解这一句：**`VERIFIED_COMPLETE` 在这里的含义只是“此版合同列出的这些机器可检查条件均已满足”**，不是声称整个自然语言功能已被形式化证明。

## 五、最有价值的练习：让证据过期

不要停止在绿色结果。打开 `hello.py`，在末尾追加一条注释或修改函数。然后运行：

```bat
python task_contract.py --repo "D:\program\agent_watchdog\hook_demo" status
```

预期 A1、A2 均变成 `STALE`（具体取决于你实际修改的文件及当前记录）。这不是测试失败的证据，而是现在需要重新验证的信号。

进一步尝试：把函数改成返回 `"WRONG"`，然后重新 `verify A1`。这次应该是 `FAILED`。修复源代码，再运行 `status`：旧失败可能变成 `STALE`，仍然需要真正重跑才能得到新的 `PASSED`。

这里最容易搞混的四个词是：`NOT_TESTED`（没测过）、`FAILED`（这版测失败）、`STALE`（曾测过但版本变了）、`INCONCLUSIVE`（测试期间版本改变，结果无法可靠归属于一个稳定快照）。把它们都合并成 `RISK` 会损失重要信息。

## 六、为什么“测试通过”仍有三个关键局限

**局限 1：测试可能不充分。** 如果单元测试只覆盖一个正常输入，登录系统的错误密码、权限检查、并发问题仍然可能没有被测到。

**局限 2：测试代码可能被 Agent 改写。** 这就是我们把测试代码也纳入 Git 指纹比较、并建议保护关键测试或人工审核 diff 的原因。仅仅测到 `exit_code=0` 不足以证明断言没有被偷偷删除。

**局限 3：外部状态没有纳入指纹。** 数据库、网络服务、环境变量、忽略文件、权限配置等可能影响程序行为。当前 v0.6 只对 Git 可见范围建立指纹，不能把“未知”冒充“通过”。

未来可以增加测试覆盖分析、环境证明、依赖感知和 Docker 隔离，但当前先把最基本的证据模型做对。

## 七、调试课：如果每次测试后都会 STALE 怎么办？

Python 执行 `unittest` 可能生成 `__pycache__`；如果这些文件被扫描，测试前后的指纹就不一致。检查 `hook_demo/.gitignore`：

```gitignore
__pycache__/
*.pyc
.pytest_cache/
```

注意：如果缓存已经被 Git 跟踪，单纯新增 `.gitignore` 也不能让它立即停止被跟踪。还要检查 `git ls-files`。此外，测试过程若确实修改了项目代码，**不要盲目忽略这些修改来换取绿色**。

## 八、本篇的学习检查

你应该能在不查看答案的情况下解释：为什么要保存 `before` 和 `after` 两个指纹？为什么退出码 0 不是“任务达成”的等价定义？当 A1 通过、A2 失败时，系统应显示什么？当测试通过后只有 README 被修改时，当前保守规则为什么仍会提示过期？

本篇验收条件：A1/A2 能单独记录；确实失败时不得记录 PASSED；测试后的代码修改会让相应旧证据变为 STALE；没有被明确执行的检查不得被填成 PASSED。

下一篇我们加入异常监督。但重要的是：不会因为看到六次 Bash，就直接宣布 Codex 卡死。

参考：[Python unittest](https://docs.python.org/3/library/unittest.html) · [Python subprocess](https://docs.python.org/3/library/subprocess.html) · [Git diff](https://git-scm.com/docs/git-diff)。
