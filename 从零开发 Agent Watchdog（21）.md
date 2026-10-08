# 从零开发 Agent Watchdog（21）：别再用模拟事件证明 Codex 已接入——把 Windows 真实链路验收到证据里

> 系列教程 · 第 21 篇｜Windows 11 · Conda · Codex CLI · Hooks · Git · G1 验收  
> **当前结论：参考实现与 GitHub 托管 CI 可以测试，作者用户本机真实 Codex 接入仍为 `NOT_VERIFIED`。**

## 一、为什么写完第 20 篇还要继续？

前 20 篇已经有了丰富的零件：`hook_logger_v04.py` 接收 Hook JSON，`bridge.py` 定时看 Git，`task_contract.py` 管理任务验收，`journal.py` 记录事件。你甚至能让监控器显示 `PostToolUse`。

然而，你把一行人工拼出来的 JSON 送入脚本，面板照样会显示“Codex 的 Bash 工具完成”。**这只说明我们写的 Python 解析器能处理一种输入，不说明 Codex 真正调用过它。**

想象用一个体温计做医院监护：仪器能显示 37℃，却没有接到病人身上。这样的视频演示再漂亮，也不能叫现场验收。第 21 篇专门修复这个证据漏洞，而不是继续堆界面。

今天我们的目标很具体：在一个**全新、独立、没有真实私人资料的 Git 练习仓库**里，核对 Codex 的实际一次工具操作，与 Watchdog 记录的时间、会话、操作标识以及 Git 独立扫描。注意：我不能远程看到你电脑的终端，所以本篇给出可执行源码和现场工作单，不给你虚构“已接入”截图。

## 二、先明确我们究竟要打通哪一段

```text
用户在临时仓库启动 Codex
       │
       ├── /hooks 显示项目 Hook、信任状态
       │
       ▼
真实工具调用 ── PreToolUse / PostToolUse ──┐
                                            ▼
                                 hook_runner_v21.cmd
                                            ▼
                                 execution_v2.py hook
                                            ▼
                          logs/events.jsonl（脱敏元数据）
                                            │
                   ┌────────────────────────┴───────────────┐
                   ▼                                        ▼
             journal.py sync                           bridge.py
                   │                                        │
               SQLite                           Git 独立快照／测试状态
                   └────────────────────────┬───────────────┘
                                            ▼
                                   人工核对 G1 证据
```

过去第 13 篇的 `integration_check.py` 只能检查链路的**就绪度**，不能自己核实数据来自真正的 Codex。本篇新建 `doctor_v21.py`，保留旧检查器的保守结论。它会告诉你 Python、Git、Codex CLI 是否找得到、CLI 版本能否读取；它**不会**因为磁盘上有文件就把 `real_codex_end_to_end` 改成 PASS。

这看起来不够“智能”，却恰恰避免了一个严重的设计错误：让待验收的程序为自己颁发验收证书。

## 三、为什么继续优先 Hook，而不是去读 Codex 的内部数据库？

对第一版个人工程，选稳定且公开的接口比选最酷的接口重要。Codex [官方 Hooks 文档](https://developers.openai.com/codex/hooks)列明了 `PreToolUse`、`PostToolUse`、`Stop` 等事件及 JSON stdin；支持 Bash、`apply_patch` 与部分 MCP/本地函数工具，但不覆盖所有托管工具。Hook 还需要用户对命令进行信任审核。

另一条路线是第三方 [Codex Task Watchdog](https://github.com/TanChuping/codex-task-watchdog)：它面向 Windows Desktop，能从 Codex 的本地日志数据库以只读方式发现细粒度异常。这套设计有参考价值，尤其是“模型可能还在准备、不要按无输出就杀掉任务”。但它自己也说明相关 SQLite 日志模式属于内部实现细节。我们不能把一份尚未在你这台机器核对过版本的解析器直接安装到生产路径。

于是本轮选择：
- **正式接入优先**：用户自己审核可信项目级 Hook。
- **辅助来源**：`codex exec --json`、App Server 使用**明确给定的离线导出文件**，绝不假装监控到了别的 Codex Desktop 会话。
- **不复制大系统**：Git 用已存在的 `evidence.py`；SQLite 用已存在的 `journal.py`；新的只是少量适配层。

## 四、源码并不需要覆盖旧文件

新增文件在同一个 `examples/v04/watchdog` 目录：

- [doctor_v21.py](examples/v04/watchdog/doctor_v21.py)——Windows 就绪检查与证据状态；
- [hook_runner_v21.cmd](examples/v04/watchdog/hook_runner_v21.cmd)——新版可选 Runner；
- [execution_v2.py](examples/v04/watchdog/execution_v2.py)——新的允许字段白名单；
- [第 21–24 篇自动测试](examples/v04/tests/test_round1.py)——不依赖真实 Codex 的正反例。

**完整源码以这些可下载、可审查的文件为准**，而不是把不全的聊天代码片段复制出来。它们没有修改你原有的 `hook_runner.cmd` 或 `evidence.py`。

最重要的 Runner 就五行：

```bat
@echo off
setlocal
REM New opt-in runner, does NOT overwrite the old hook_runner.cmd
if not defined WATCHDOG_PYTHON set "WATCHDOG_PYTHON=python"
"%WATCHDOG_PYTHON%" "%~dp0execution_v2.py" hook
exit /b 0
```

`%~dp0` 指 Runner 所在目录。它能减少“Codex 从 A 项目运行，Python 却相对路径寻找 B 脚本”的错误。`exit /b 0` 是观察者原则：日志采集失败也不应阻止 Codex 的工作。

但是别把 `exit /b 0` 想成万能保证：Hook 解析太慢、输出格式不合法、权限被拒绝，仍需要在真实环境中按 /hooks 检查。Python 只打印 `{}`，不会提供 `decision:block`、`updatedInput` 或其他干预项。

## 五、为什么先让 GitHub Actions 跑一次 Windows 测试？

之前的教程一直强调 Windows，但多数代码先在隔离 Linux 环境验证。我们为本轮增加了 [Windows + Ubuntu 的 GitHub Actions 回归](.github/workflows/round1-ci.yml)，执行：

```bat
python --version
git --version
python -m unittest discover -s examples\v04\tests -v
python -m compileall -q examples\v04\watchdog
```

这一步还意外暴露了真问题：旧测试使用的 SQLite 连接没有被明确关闭。在 Windows，仍占用的 `backup.sqlite3` 会让临时目录清理失败；另一个测试在 Windows Git 可能报告不同规范化路径时找不到保护文件的基线。我们修补了 `journal.summary`、`operations.archive/check` 的连接关闭以及对应测试中 `repo = evidence.root_for(repo)` 的路径规范化。**修复后的托管 CI 结果可以证明该环境下的回归测试，不是你自己的 Codex 真机接入。**

这就是先工程后博客的好处：文章要教会读者处理真正遇到的失败，而不是要求读者默默相信所有命令都会成功。

## 六、在你自己的 Windows 11 上操作：分三个终端

我们把具体的可复制命令完整集中在 [真实 Codex 验收工作单](docs/REAL_CODEX_E2E_RUNBOOK.md)，以免正文与 Runbook 两份路径长期分叉。下面解释每一步背后的理由。

**终端 A（Anaconda Prompt / CMD）**：不要覆盖旧 `watchdog`，先检出一个新 `Agent-Watchdog-v2-eval` 目录：

```bat
conda activate torch_env
where python
codex --version
git clone --branch feature/aw-v2-round1-21-24 https://github.com/colddreamxiaowd/Agent-Watchdog.git D:\program\agent_watchdog\Agent-Watchdog-v2-eval
cd /d D:\program\agent_watchdog\Agent-Watchdog-v2-eval
python -m unittest discover -s examples\v04\tests -v
```

如果目标目录已经存在，先检查或换名字，别再执行可能覆盖资料的操作。注意上面是 **CMD** 命令；下一步看日志要用 PowerShell 语法。

**终端 B（在新建的临时 `hook_demo_v2` 仓库）**：人工创建已审核的 `.codex/hooks.json`，配置到绝对路径 `hook_runner_v21.cmd`，再从该仓库启动 `codex`。在交互界面运行 `/hooks`，按界面检查 Hook 是否已加载、是否得到你自己的信任。不要用跳过权限的选项。

**终端 C（PowerShell）**：用 `Get-Content -Tail 12 -Wait` 观察刚才那个 Runner 的 `logs/events.jsonl`。让 Codex 按明确约束创建一个小的 `add.py` 并执行验证；时间与实际工具操作必须对应。随后在另一终端执行 `bridge.py --repo ... --once` 检查 Git 可见文件变化。

对比两份事实：Hook 事件说明某工具可能被触发；Git 快照说明某时刻文件发生变化。**没有可见执行上下文时，我们不能断言该文件一定由那个 Hook 所指的工具改动。**

## 七、做一次故意失败，才能知道系统会不会撒谎

反例 A：自己向 `execution_v2.py hook` 送一条伪造的 `PostToolUse`。它会写日志，测试会通过，但你必须把它标成 `SYNTHETIC`，不能填入真实 Codex 的工作单。这就是“程序可用”和“来源真实”的区别。

反例 B：让 Codex 安静两分钟，然后去看监控。没有新事件并不意味着任务卡死；它可能推理中、使用未覆盖的工具、电脑休眠或发生了记录器故障。

反例 C：另开 Notepad，手工修改 `demo.txt`。Git 确实会发现变化，但不能因此说 Codex 越权。原始设计中的“文件差异”和“修改者归因”必须始终分开。

反例 D：`doctor_v21.py` 找到了 `codex`，仍输出 `NOT_VERIFIED`。这不是实现失败，而是证明就绪探测器没有错误地给自己开绿灯。

## 八、你最可能遇到的四类问题

| 现象 | 首先检查 | 不应采取的捷径 |
|---|---|---|
| `codex` 不在 PATH | `where codex`、安装与终端环境 | 不乱改全局系统变量 |
| `/hooks` 无 Hook | 项目文件、信任、JSON 语法和 CLI 版本 | 不关闭信任审核 |
| Logger 有行但 Bridge 没刷新 | `cwd` 是否与被监控 Git 根目录对应；是否读同一个日志 | 不把任意项目事件算作当前项目 |
| `PostToolUse` 没有成功状态 | `tool_response` 是否有**明确数值**结果 | 不从“有结束事件”猜成功 |

## 九、第 21 篇算完成了吗？

工程交付物：源码、静态检查、CI、Runbook 都可以独立审阅。真机门 G1 只有在你确认当次 Codex CLI 版本、可信 Hook、对应事件、独立 Git 变化和安全回退之后才能打勾。

**第 21 篇的正确结论是：我们有了严格的现场验收方法和可运行的接入准备，但没有替你完成 Windows 现场见证。**

下一篇就要解决一个更细的问题：即使真实收到了 `PostToolUse`，它到底表示“工具退出成功”“工具失败”还是“仅知道工具给出了输出”？这个区别决定 Watchdog 是否能真正理解执行结果。

延伸阅读：[Codex Hooks](https://developers.openai.com/codex/hooks) · [本地工作单](docs/REAL_CODEX_E2E_RUNBOOK.md) · [能力矩阵](docs/CAPABILITY_MATRIX.md)。

