# 从零开发 Agent Watchdog（03）：让 AI 的任务进度有证据，而不是只听它说“完成了”

系列教程 · 第 3 篇

Windows 11 · Python · Git · 自动化测试

前两篇，我们尝试完成了 Agent Watchdog 的基础监控链路：

```
Codex → Hooks → events.jsonl → 实时监控面板
```

它能告诉我们 Codex 最近执行了什么工具，但还有一个明显的不足：

Codex 正在活动，不代表它正在取得进展；Codex 宣布完成，也不代表任务真的完成。

这一篇，我们要给 Agent Watchdog 增加一个很有价值的功能：独立证据检查。

本篇完成后的终端输出示例

AGENT WATCHDOG 03

EVIDENCE

项目

hook_demo

文件变更

2 个

保护文件

GOAL.md 已改动

最近一次测试

STALE — 测试证据已过期

原因：测试通过后，工作区文件再次发生变化。

结论：需要重新验证，不能仅凭旧测试宣布完成。

这是目标效果示意图，具体检查结果取决于你的项目文件和测试记录。

## 一、本篇要解决的三个问题

假设 Codex 正在修复一个登录 Bug。

它先修改 `auth.py`，运行测试并成功通过。随后又修改了 `auth.py`，但没有重新执行测试，最后回复用户：“已经修复。”

我们的监督系统应该识别三件事：

1. 文件真的发生变化了吗？ 使用 Git 可见文件及其内容指纹进行对比。
2. 测试真的执行并通过了吗？ 由我们的程序启动用户指定的测试命令，记录真实退出码。
3. 测试结果现在还有效吗？ 比较测试时与当前工作区的文件指纹。如果代码之后发生变化，将旧证据标记为过期。

这三种能力不需要大语言模型，也不需要 StepWise。使用 Python 标准库和 Git 就能完成。

这里借鉴了开源项目 codex-watchdog 的工作区监督思路，它使用 Git 状态及项目规则来发现修改和越界行为。我们这一篇实现的是独立的简化版，并不直接复制该项目代码。

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub



## 二、下载本篇的工程文件

我已经写好一个可独立运行的 Python 程序，并对正常测试、过期测试、保护文件修改和测试失败等场景进行了本地验证。



Agent Watchdog 03 · 完整源码

Python 3.9+ · 不需要额外 Python 依赖

evidence.py

下载 Python 文件

watchdog_rules.json

下载规则配置

完整工程压缩包

下载 ZIP

本篇采用“下载源码、逐步运行、理解核心逻辑”的方式。完整脚本大约 200 行，你可以用 VS Code 阅读和修改，不需要在聊天窗口复制大段代码。

将 ZIP 解压后，把 `evidence.py` 与 `watchdog_rules.json` 复制到你现有的目录：

```
D:\program\agent_watchdog\
│
├── StepWise\
├── hook_demo\
│
└── watchdog\
    ├── hook_logger.py
    ├── hook_runner.cmd
    ├── monitor.py
    ├── evidence.py            ← 新增
    ├── watchdog_rules.json    ← 新增
    └── state\                 ← 程序自动创建
```

这里我们保留之前写的 Hook 采集器和监控面板，本篇的新功能暂时通过手动命令触发。不要直接把它加入 `PostToolUse` Hook，因为对大型代码仓库进行全量文件指纹计算可能有明显开销。

## 三、准备一个安全的测试项目

这一次，我们仍然使用上篇的独立测试目录，而不是直接操作你正在研究的正式项目。

打开 Anaconda Prompt：

```
conda activate torch_env
cd /d D:\program\agent_watchdog\hook_demo
```

检查 Git 是否可用：

```
git status
```

如果显示当前分支和文件状态，说明测试仓库已经初始化。

接下来，我们创建一个非常简单的 Python 项目，让 Watchdog 有东西可以检查。

### 第 1 步：创建 hello.py

执行：

```
notepad hello.py
```

写入：

```
def greet():    return "Hello Agent Watchdog"if __name__ == "__main__":    print(greet())
```

保存。

这个程序只有一个函数 `greet()`，返回一段固定文字。

### 第 2 步：创建测试文件

执行：

```
notepad test_hello.py
```

写入：

```
import unittestfrom hello import greetclass GreetingTest(unittest.TestCase):    def test_greet(self):        self.assertEqual(            greet(),            "Hello Agent Watchdog"        )if __name__ == "__main__":    unittest.main()
```

这里使用 Python 自带的 `unittest`，所以不需要额外安装 pytest。

测试要求非常简单：

> `greet()` 必须返回 `"Hello Agent Watchdog"`。

### 第 3 步：创建一份任务约束

执行：

```
notepad GOAL.md
```

写入：

```
# Project Goal

实现 hello.py，并通过自动化测试。

## Constraints

- 不允许修改 GOAL.md。
- 所有测试必须通过。
```

这是一份模拟的用户任务契约。

以后我们会让 Agent Watchdog 读取并理解这种目标文件。但这一篇先只做一项确定性检查：它有没有被改动。

### 第 4 步：忽略测试缓存

执行：

```
notepad .gitignore
```

确保文件包含：

```
__pycache__/
*.pyc
.pytest_cache/
```

如果文件已经存在，请把这几行追加进去，保留原有内容。

这是因为 Python 测试会生成缓存文件，我们不希望缓存变化导致每次测试都被误判为代码变化。

此时测试项目至少包含：

```
hook_demo/
├── .codex/
├── .git/
├── .gitignore
├── GOAL.md
├── hello.py
└── test_hello.py
```

## 四、第一次记录项目基线

基线（Baseline） 是本篇最重要的概念。

简单来说，就是先保存一个“开始前是什么样子”的参照。

例如：

```
初始状态
    │
    ├── GOAL.md        hash-A
    ├── hello.py       hash-B
    └── test_hello.py  hash-C
```

以后再扫描：

```
当前状态
    │
    ├── GOAL.md        hash-A
    ├── hello.py       hash-D  ← 发生变化
    └── test_hello.py  hash-C
```

我们就知道 `hello.py` 的文件内容已经变化。

程序使用 Git 获取被跟踪的文件，以及尚未被 Git 忽略的未跟踪文件，再计算 SHA-256 内容指纹。Git 官方的 `ls-files --cached --others --exclude-standard` 正好支持这类文件枚举。

[image](https://www.google.com/s2/favicons?domain=https://git-scm.com\&sz=32)

git-ls-files Documentation



### 开始创建基线

执行：

```
python D:\program\agent_watchdog\watchdog\evidence.py --repo "D:\program\agent_watchdog\hook_demo" baseline
```

正常情况下会出现类似输出：

```
Baseline saved outside the repo: 4 Git-visible files.

Agent Watchdog 03
Changed vs baseline: 0
Protected files: no changes detected
Test evidence: NOT_TESTED
```

文件数量取决于你原来在 `hook_demo` 里放了什么。

这里的 `NOT_TESTED` 是合理的，因为我们还没有通过监督程序执行测试。

基线文件保存在：

```
watchdog/state/<仓库路径标识>/baseline.json
```

而不是保存在 `hook_demo` 内，避免监控证据本身污染被观察的仓库。

注意：不要在后续每次扫描前重新执行 `baseline`，否则就会把已经发生的修改重新当成正常初始状态。

## 五、第一次执行独立测试

现在开始记录真正的测试证据。

在 Anaconda Prompt 输入：

```
python D:\program\agent_watchdog\watchdog\evidence.py --repo "D:\program\agent_watchdog\hook_demo" test -- python -m unittest discover -p "test_*.py" -v
```

这条命令分成两部分。

前半段：

```
evidence.py --repo ... test
```

表示由我们自己的监督程序启动一次测试。

后半段：

```
-- python -m unittest discover -p "test_*.py" -v
```

表示实际要执行的测试命令。

这次应该可以看到：

```
Ran 1 test in ...
OK

Test evidence:
PASS_FOR_TESTED_SNAPSHOT
```

我们已经有了一份真实测试证据。

本地样例测试中，脚本正确记录了测试通过与退出码 0。



但这并不代表整个项目目标已经完成。

`PASS_FOR_TESTED_SNAPSHOT` 的含义更严格：

> 在某个具体文件快照上，我们指定的测试命令返回了成功。

这与 Agent 自己说“测试通过”不同，因为测试进程和退出码由我们自己的程序记录。

这里的证据仍有边界：如果测试本身写得不充分、被 Agent 修改过，或者依赖外部状态，它就不能充分证明整个任务成功。

## 六、关键实验：让已经通过的测试自动失效

这是本篇我最希望你亲自做的实验。

假设 Codex 已经完成测试，然后继续修改代码。

我们应该继续相信先前的测试结果吗？

不应该直接相信。

现在打开：

```
notepad hello.py
```

在文件末尾增加一行注释：

```
# Modified after the test
```

保存。

注意，这只是增加一行注释，程序功能实际上没有变化。

然后执行：

```
python D:\program\agent_watchdog\watchdog\evidence.py --repo "D:\program\agent_watchdog\hook_demo" scan
```

你应该看到：

```
Changed vs baseline: 1
  MODIFIED hello.py

Test evidence:
STALE (repository changed after test)
```

为什么这是一项有价值的工程能力？

旧测试通过的是修改前的文件版本。现在文件内容发生变化，我们不能自动把旧结果视为当前版本的验收结果。

即便只是添加注释，第一版也采用保守规则：检测到 Git 可见文件变化就要求重新确认。以后再优化成只对相关文件或验收条件失效。

我对这项行为进行了本地测试，修改文件后，程序确实输出了 `STALE` 状态。



如果你现在重新执行第五节的测试命令，新的测试证据就会对应当前文件快照。

## 七、第二个实验：发现 Agent 修改了禁止修改的文件

现在我们测试另一种问题。

假设原始约束明确说：

> 不得修改 GOAL.md。

但是 Agent 后来修改了它。

我们的程序不需要询问 LLM，也能检测到这一项确定性违规。

打开：

```
notepad GOAL.md
```

在末尾追加：

```
## New requirement

额外重构整个项目。
```

保存。

然后重新扫描：

```
python D:\program\agent_watchdog\watchdog\evidence.py --repo "D:\program\agent_watchdog\hook_demo" scan
```

预期会看到：

```
Changed vs baseline: 2
  MODIFIED GOAL.md
  MODIFIED hello.py

PROTECTED CHANGES: GOAL.md
```

我在本地验证了这一功能，修改受保护的 `GOAL.md` 后，程序正确识别了保护文件变更。



### 保护规则在哪里定义？

打开：

```
notepad D:\program\agent_watchdog\watchdog\watchdog_rules.json
```

内容是：

```
{
  "protected_paths": [
    "GOAL.md",
    ".env",
    ".github/workflows/*"
  ]
}
```

以后你可以为自己的不同项目增加更多规则，例如：

```
{
  "protected_paths": [
    "GOAL.md",
    ".env",
    "requirements.txt",
    "docs/PROJECT_CONSTRAINTS.md"
  ]
}
```

这只是一个基础实现：它能识别基线前后文件发生了变化，但不能据此判断一定是 Codex 修改的。因为也可能是你手动修改，或者其他程序改变了文件。

另外，被 Git 忽略的文件不在本篇扫描范围内。因此，如果 `.env` 已被 `.gitignore` 排除，就不能依靠这里的规则保证监测到它。未来应单独实现敏感文件监控，而不是给用户一个虚假的安全保证。

## 八、第三个实验：真实测试失败

最后，我们不只是验证“证据过期”，还要验证测试失败能否被正确记录。

打开：

```
notepad hello.py
```

把函数改成：

```
def greet():    return "WRONG"if __name__ == "__main__":    print(greet())
```

现在重新执行：

```
python D:\program\agent_watchdog\watchdog\evidence.py --repo "D:\program\agent_watchdog\hook_demo" test -- python -m unittest discover -p "test_*.py" -v
```

由于 `greet()` 返回了错误的字符串，测试应该失败。

你会看到类似：

```
FAILED (failures=1)

Test evidence:
FAIL (test command returned non-zero)

Exit code: 1
```

本地测试也验证了这项行为：真实失败的测试没有被报告为成功。



以后，我们还可以改用 `pytest`。官方支持直接运行 `python -m pytest`，因此只需要把命令最后一部分替换为相应的 pytest 命令即可。

[image](https://www.google.com/s2/favicons?domain=https://docs.pytest.org\&sz=32)

pytest documentation



## 九、理解我们自己实现的证据状态机

到目前为止，我们没有训练任何新的 AI 模型。

但已经做出了一个很重要的监督模块。

测试证据判断流程

用户明确启动测试

记录测试前文件指纹

执行指定测试并记录退出码

记录测试后文件指纹

PASS

测试退出码为 0，且检测范围内的文件快照一致

FAIL

测试命令返回非零退出码

STALE

测试完成后，文件快照发生变化

INCONCLUSIVE

测试运行期间，文件快照发生变化

这套规则以后可以作为 IronLaw 式完成验收机制的一个基础。

不过当前程序还没有做到完整的任务契约理解、测试覆盖分析和运行环境验证。它只是一套可以复查的文件与测试证据记录机制。

## 十、我们这次真正复用了什么？

| 技术或项目               | 采用方式              |
| ------------------- | ----------------- |
| Git                 | 直接使用官方命令获取文件范围    |
| Python `hashlib`    | 计算文件 SHA-256 指纹   |
| Python `subprocess` | 按用户指令执行测试并读取退出码   |
| codex-watchdog      | 借鉴工作区与保护文件监督思路    |
| IronLaw             | 借鉴“完成必须有证据”的架构原则  |
| StepWise            | 本篇不使用，后续作为可选语义检测器 |

我特意没有让你克隆并运行多个第三方项目，因为这会增加 Windows 环境集成的复杂程度，而本篇的功能使用标准库就可以可靠起步。

另外请记住：`scan` 和 `baseline` 不会主动修改被监控仓库；但 `test` 会运行你指定的测试代码，而测试代码本身可能写文件或执行其他操作。所以现在只对可信任的测试仓库运行它，不要自动运行从陌生仓库下载的测试程序。

## 十一、完成这一篇后，我们拥有什么？

AGENT WATCHDOG — 当前工程进度

StepWise 推理 — 本地模型已成功运行

Codex Hooks — 根据上一篇配置进行实际接入验证

实时面板 — 根据上一篇教程部署

文件证据模块 — 源码完成并通过本地测试

测试证据模块 — 源码完成并通过本地测试

自动事件联动 — 下一阶段

独立任务验收 — 后续阶段

这里要区分：我已经在隔离的测试仓库中验证了 `evidence.py` 的逻辑，但它尚未在你的 Windows 电脑上完成实际验收。

本篇你只需要确保上面的 `baseline → test → scan` 三条主命令正常运行，就可以进入下一阶段。

## 下一篇预告

Agent Watchdog（04）

## 把事件监控与证据检查连接起来：Codex 修改文件后，Watchdog 自动更新检查结果

下一篇将把我们已经写好的两个独立模块真正连接起来：

```
Codex 执行操作
       ↓
Hook 收到事件
       ↓
触发文件证据检查
       ↓
发现修改 / 保护文件变化
       ↓
更新实时监控面板
```

同时实现去重与节流，避免每次工具调用都重复扫描大型代码仓库。测试仍然由用户明确授权运行，不会因为 Agent 声称完成就自动执行任意命令。

到这一篇为止，我们的软件开始具备一种重要的能力：把 AI 的陈述与实际可核查的执行证据分开。

这才是 Agent Watchdog 从普通日志查看器走向真正监督系统的第一步。
