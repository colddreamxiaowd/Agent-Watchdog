# 从零开发 Agent Watchdog（05）：让监督器知道任务的目标，而不只是看见工具在运行

> **系列教程 · 第 5 篇** · Windows 11 / Python / JSON / Git / Task Contract  
> 接着第 04 篇：不重建监控器，而是在已有独立证据层上建立**任务契约**。

上一节的 Monitor 04 已经可以把事件与 Git 变化联动起来。假设 Codex 连续执行了二十个工具调用，修改了三个文件，随后测试成功。你是否可以放心地说“任务完成了”？

先不要回答。我们构造一个故事：用户要求“修复登录失败，不要改数据库结构，完整回归测试必须通过”。Codex 修改 `auth.py` 并且登录测试通过，后来它又改变了数据库 Schema，但全套回归测试根本没有运行。面板如果只显示“测试 PASSED”，就可能给出一种**非常有欺骗性的安心感**。

这正是普通运行监控器与真正 Agent 监督系统之间的差距：前者只知道**发生了什么**；后者还需要知道**原本应该发生什么**。

## 一、先把自然语言要求拆成三层

对于“修复登录失败，不要修改数据库结构，全部测试要通过”，我们至少要拆成：

1. **目标（Goal）**：修复登录问题。这一层暂时无法完全靠规则验证。
2. **硬约束（Constraints）**：不能碰 `GOAL.md`，不能修改数据库迁移文件。某些文件级约束可以直接用 Git 识别。
3. **验收（Acceptance）**：登录测试成功、回归测试成功。这部分可通过独立的测试进程和退出码记录。

先用一个易懂的 JSON 表达：

```json
{
  "schema_version": 1,
  "goal": "修复 hello.py，不能改动任务文件，必须通过功能和回归测试",
  "protected_paths": ["GOAL.md", ".github/workflows/*"],
  "acceptance": [
    {"id":"A1","description":"功能测试","command":["python","-m","unittest","test_hello.py","-v"]},
    {"id":"A2","description":"回归测试","command":["python","-m","unittest","discover","-p","test_*.py","-v"]}
  ]
}
```

这是本篇的**正式入门 Schema**。完整示例已经保存为 [`task_contract.example.json`](examples/v04/watchdog/task_contract.example.json)，验证器写在 [`task_contract.py`](examples/v04/watchdog/task_contract.py)。

### 为什么测试命令是数组，而不是一段字符串？

看这两种形式：

```json
"command": "python -m unittest discover -p test_*.py -v"
```

和：

```json
"command": ["python", "-m", "unittest", "discover", "-p", "test_*.py", "-v"]
```

第二种形式可以直接交给 Python 的 `subprocess.run(argv, shell=False)`，不必让 Shell 再重新解释整条命令，能够显著减少“字符串拼接后被当成额外命令”的风险。但**它并不保证测试本身安全**，因为 Python 测试文件仍然可以读写磁盘、访问网络。所以我们坚持：不由 Hook 自动执行测试，只允许用户显式运行已审核的合同命令。

## 二、真正困难的问题：谁可以修改契约？

假设 Codex 一开始收到用户要求“回归测试必须全部通过”，运行中发现 A2 一直失败。它把任务合同改成“只运行 A1”，再宣称全部完成。监督器如果只看当前合同，自然会报告成功。

这就好比考试时，学生可以偷偷改评分标准。

解决方法不是“再训练一个更聪明的 LLM”。至少在第一版，可靠做法是：

```text
用户任务原文
    ↓
形成契约草案（人工审核）
    ↓
SHA-256 锁定批准版本
    ↓
独立验收
    ↓
如果契约发生变化 → BLOCKED，等待重新批准
```

在 `task_contract.py` 中，`contract_hash()` 对**规范化后的 JSON 对象**计算 SHA-256；`approve()` 将其摘要写在仓库之外的监督器状态目录。注意：这只是同一用户权限下的**意外篡改检测**，并非对具有相同文件权限的恶意进程提供密码学身份认证。以后如果要防止一个完全不受信任的 Agent 修改监督数据，就得把监督器放到真正隔离的账户或环境里。

### 这和第三篇的 Git 基线有什么不同？

第三篇的基线回答：“文件与最初有什么差异？”

这一篇的合同摘要回答：“批准过的验收规则有没有被换掉？”

它们不是互相替代：基线防止目标文件被悄悄改动；合同摘要防止游戏规则被悄悄改动。要用不同的变量保存，不应该都叫 `baseline`。

## 三、亲手建立第一份任务合同

仍然使用 `hook_demo`，不要把未经检验的功能直接装到正在研究的正式仓库。

第一步，在 `D:\program\agent_watchdog\watchdog` 内新增 `task_contract.py`，并将本篇的 `task_contract.example.json` 放在同一目录。检查原 Git 基线仍可读取：

```bat
conda activate torch_env
cd /d D:\program\agent_watchdog\watchdog
python evidence.py --repo "D:\program\agent_watchdog\hook_demo" scan
```

第二步，建立合同草案：

```bat
python task_contract.py --repo "D:\program\agent_watchdog\hook_demo" init --contract "D:\program\agent_watchdog\watchdog\task_contract.example.json"
```

它会把合同复制到 `watchdog/state/<仓库标识>/task_contract.json`。源合同和监督状态都在**被观察的 Git 仓库之外**，避免测自己的文件导致指纹变化。

第三步，先打开这个生成的文件看一遍，确认没有误读原目标。再显式批准：

```bat
python task_contract.py --repo "D:\program\agent_watchdog\hook_demo" approve
```

最后查看当前状态：

```bat
python task_contract.py --repo "D:\program\agent_watchdog\hook_demo" status
```

第一次很可能看到：

```text
approved: true
acceptance:
  A1: NOT_TESTED
  A2: NOT_TESTED
stage: IN_PROGRESS
```

**这个状态才是合理的**。我们只是描述任务，并没有执行任何验收。

## 四、做一次反例：修改合同会怎样？

找到监督器的 `state/<仓库标识>/task_contract.json`，尝试把 `goal` 改成较弱要求，再运行 `status`。程序重新计算摘要，`approved` 应变成 `false`，总状态是 `BLOCKED`。

这时不要着急“修复”成通过。先问自己：是不是用户真的批准了改需求？如果是，应该检查差异并重新批准；如果不是，应恢复原合同并调查为什么出现改动。

特别注意，本篇的 `approve` 会**清空以前保存的所有验收结果和声明**，防止拿旧规则下的测试结果冒充新规则的证据。你可以阅读 `approve()` 里 `results_path.unlink()` 的代码，亲自验证这一点。

## 五、声明完成与真正完成，是两种完全不同的消息

监督器可能听到 Codex 说：“功能已修复，任务完成。”我们把它记录为声明，不视为事实。

```bat
python task_contract.py --repo "D:\program\agent_watchdog\hook_demo" claim --text "Agent 声称功能已完成"
```

再次运行 `status`，可能看到 `CLAIMED_COMPLETE`，但 A1、A2 仍是 `NOT_TESTED`。

这很重要，因为未来即使我们让 Watchdog 用 LLM 总结 Agent 的话，它也不能把“声称”偷换成“通过验收”。

**想一想：如果没有合同，系统怎么知道 A2 从未运行？如果只看最后一条 `Stop`，为什么会误判任务结束？**

## 六、动手检查：Schema 错误时应该拒绝，而不是替你猜

你可以做几个刻意破坏的实验：

- 把 `schema_version` 改成字符串 `"1"`；
- 将 `acceptance` 改成空数组；
- 让两个验收条件的 `id` 都变成 `A1`；
- 将命令从字符串数组改成一段 Shell 字符串。

我们的验证器会明确拒绝。这不是吹毛求疵。如果监督器对验收规则含糊其词，以后任何“已完成”都可能建立在错误 Schema 上。

## 七、你真正学会了什么？

本篇结束后，Watchdog 仍不懂“登录功能”的全部含义。但是它已经掌握一条非常有用的工程规则：**用户审核过的验收标准不能被 Agent 的最新总结静默覆盖。**

验收标准：能够创建和批准合同；改动合同后变为 `BLOCKED`；仅 Agent 自称完成不会自动通过；合同被重新批准后旧证据不会自动继承。

下一篇我们将处理更棘手的问题：**测试到底能证明什么？测试通过后继续修改代码，又该怎么办？**

延伸阅读：[Python subprocess](https://docs.python.org/3/library/subprocess.html) · [Python hashlib](https://docs.python.org/3/library/hashlib.html) · [本篇代码](examples/v04/watchdog/task_contract.py)。
