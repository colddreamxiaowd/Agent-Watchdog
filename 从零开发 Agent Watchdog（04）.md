# 从零开发 Agent Watchdog（04）：让 Codex 的 Hook 事件自动触发 Git 证据检查

> **系列教程 · 第 4 篇（与原 V0.1–V0.3 连续）**  
> Windows 11 · Conda · Python · Codex Hooks · Git · Rich  
> **本篇不是一套新的项目。** 我们继续使用 `D:\program\agent_watchdog\watchdog` 中前三篇的文件，给已有的证据检查器增加事件桥接层。

前三篇做了三件相互独立的事：第 01 篇让 Hook 事件写入 `events.jsonl`；第 02 篇用 `monitor.py` 看事件；第 03 篇用 `evidence.py` 判断文件是否变化、保护文件有没有被碰过、最后一次测试结果是否过期。

看起来已经有点像一个监督系统了。可实际使用时，你会碰到一个不舒服的体验：**明明 Codex 已经编辑完代码，你还是得打开另一个终端，手动运行 `evidence.py ... scan`。**

这意味着我们得到的是三个工具，而不是一个连贯的软件。今天的任务就是把它们接起来。

---

## 一、本篇完成后的效果：你操作 Codex，监督器自己更新

假设我们正在让 Codex 修改 `hook_demo/hello.py`。先前运行过的测试已经通过；Codex 后来又修改代码。理想的监督器不需要它汇报“我改过了”，而应自己得到下列事实：

```text
Codex 执行工具
       │
       ▼
PostToolUse Hook
       │（接收事件，不执行重活）
       ▼
logs/events.jsonl
       │
       ▼
bridge.py
       │ 识别 cwd、合并密集事件、定期扫描
       ▼
evidence.py 的已有函数
       │
       ├── Git 工作区与基线比较
       ├── 保护文件检查
       └── 上次测试对应的文件指纹
       │
       ▼
state/<仓库标识>/bridge_report.json
       │
       ▼
monitor04.py 实时展示
```

这里的 `Stop` 只是一个**回合事件**，不是“整个项目完成”。`PostToolUse` 只能说明一个受到 Hook 覆盖的工具操作已经产生输出，不能证明结果正确。微软或 Python 测试真正返回什么，仍由第三篇的证据检查器独立记录。

### 为什么不直接在 Hook 里调用 `evidence.py`？

想象 Codex 需要写十个文件，每写一个就触发一次 Hook。如果每个 Hook 都遍历几千个文件并计算 SHA-256，监控软件反而可能拖慢被监控者。

我们把职责拆分：

| 部件 | 做什么 | 故意不做什么 |
|---|---|---|
| `hook_logger_v04.py` | 接收 JSON，提取最少元数据，快速追加一行日志 | 不扫描 Git、不跑测试、不保存工具输出 |
| `bridge.py` | 按仓库挑出有关事件，合并触发，再调用 `evidence.py` 中的现成函数 | 不判断语义目标、不重试任务、不控制 Codex |
| `monitor04.py` | 每秒读取报告和最近事件，显示 Rich 面板 | 不终止进程、不代替验收 |

**这是一个工程上的“松耦合”：** Hook 异常时，Bridge 不该把整个 Codex 任务拖垮；面板关闭时，监督系统也不应该让 Codex 停止。

---

## 二、先检查你电脑真实存在的文件

你发来的截图显示，原本的目录已经包含：

```text
D:\program\agent_watchdog\
├── hook_demo\
├── StepWise\
├── watchdog\
│   ├── logs\
│   ├── state\
│   ├── evidence.py
│   ├── hook_logger.py
│   ├── hook_runner.cmd
│   ├── monitor.py
│   ├── test_stuck.py
│   └── watchdog_rules.json
└── watvhdog_blog\
```

我们要保护这份已有成果，而不是另建一棵与它无法兼容的代码树。

打开 **Anaconda Prompt（CMD）**，执行：

```bat
conda activate torch_env
cd /d D:\program\agent_watchdog\watchdog
dir
python --version
git --version
```

如果没有 Rich，再安装：

```bat
python -m pip install rich
```

**不要重装 PyTorch、不要重新下载 StepWise。** 本篇完全不需要 GPU。如果 `python`、`git` 和原来第三篇的 `evidence.py` 能运行，核心前提就够了。

### 先保存原文件，再复制新增源码

本次实际配套源码放在仓库的 [`examples/v04/watchdog/`](examples/v04/watchdog/) 目录中。需要新增：

```text
hook_logger_v04.py
bridge.py
monitor04.py
hook_runner_v04.cmd
```

同一目录也保留了你上传的**第三篇原版** `evidence.py` 与 `watchdog_rules.json`，供逐行对照；它们的作用是参考原接口，**并不要求你覆盖本机文件**。

如果要将新源码复制到你自己的 `watchdog` 文件夹，请先在 CMD 中保存旧版 Runner：

```bat
copy hook_runner.cmd hook_runner.backup.cmd
```

`hook_runner_v04.cmd` 用新名称保留，真实连接成功前不要直接覆盖旧版 Runner。通过这个小技巧，我们以后有了问题，还能无损退回 v0.3。

---

## 三、Hook Logger v0.4：最小权限事件采集

第三篇后，我们需要给原事件增加一个非常实用的字段：`cwd`。因为你完全可能同时打开多个 Codex 会话，分别在 `AI比赛通知雷达`、课程作业和 `Agent Watchdog` 里工作。

旧事件：

```json
{"event":"PostToolUse","tool":"Bash","session_id":"demo"}
```

我们期望的安全记录形式：

```json
{
  "source":"hook_input_unverified",
  "received_at":"2026-10-08T18:00:00+00:00",
  "event":"PostToolUse",
  "session_id":"demo",
  "turn_id":null,
  "tool":"Bash",
  "cwd":"D:\\program\\agent_watchdog\\hook_demo",
  "tool_use_id":null
}
```

`cwd` 只是当前工作目录；**不能证明文件变化一定由该会话造成**。比如你同时用 VS Code 修改了文件，Bridge 仍可能在下一次扫描中观察到变化。

打开 [`hook_logger_v04.py`](examples/v04/watchdog/hook_logger_v04.py)。建议你先读 `prepare()`：

```python
return {
    "source": "hook_input_unverified",
    "received_at": datetime.now(timezone.utc).isoformat(),
    "event": event,
    "session_id": clean(payload.get("session_id"), 120),
    "tool": clean(payload.get("tool_name"), 120),
    "cwd": clean(payload.get("cwd"), 700),
}
```

这里只提取元数据。`tool_input`、`tool_response`、用户提示词、环境变量、命令本体等内容都没有写入日志。这样做是刻意的：我们要先建立一个**够用而不是贪多**的采集器。

`source` 取值是 `hook_input_unverified`，因为一个人手工通过 `echo` 给脚本输入 JSON，也能模拟 Hook。**本地日志出现事件本身无法证明它真的来自 Codex**；真实身份还必须结合 `/hooks` 配置和现场实验核对。

### `stdin` 从哪里来？

Codex 的 command Hook 会将 JSON 输入发送到脚本的标准输入（stdin）。

```python
raw = sys.stdin.buffer.read(MAX_STDIN + 1)
```

接着解析 JSON、删除不需要的字段，向 JSONL 追加一个换行记录。和第一篇的原理完全一致，只是更加严格地限制了输入大小和字段范围。

程序的 `stdout` 最终输出 `{}`，意味着这个 Hook 不提出阻止、替换或其他控制要求。它是一个**观察者**。

### Windows Runner 为什么要使用绝对 Python 路径？

你在 Conda Prompt 激活了 `torch_env`，不代表 Codex 的 Hook 子进程也有完全相同的 PATH。新 Runner 默认使用 `WATCHDOG_PYTHON` 环境变量；实际接入时应将它设置为你 `where python` 查到的解释器完整路径，或在 Runner 中写死你自己的 Python 路径。

参考文件：[`hook_runner_v04.cmd`](examples/v04/watchdog/hook_runner_v04.cmd)。

```bat
@echo off
setlocal
if not defined WATCHDOG_PYTHON set "WATCHDOG_PYTHON=python"
"%WATCHDOG_PYTHON%" "%~dp0hook_logger_v04.py"
```

`%~dp0` 表示“当前 `.cmd` 文件所在目录”。这样无需担心 Hook 的工作目录与 Python 文件路径不一致。

---

## 四、认识 Bridge：理解防抖、节流和最大等待

写 Bridge 之前，先做一道推理题。

Codex 在下列时间完成工具操作：

```text
13:00:01 PostToolUse
13:00:02 PostToolUse
13:00:03 PostToolUse
13:00:04 PostToolUse
13:00:05 PostToolUse
```

如果每条事件扫描一次，你会扫描五次。但如果一味等待“事件彻底停止”，一个持续不断操作的 Agent 又可能让我们永远不扫描。

我们引入三个不同的时间约束：

| 术语 | 本篇默认值 | 用处 |
|---|---:|---|
| `debounce` | 2 秒 | 最近一条事件之后安静 2 秒，再考虑扫描 |
| `min_interval` | 5 秒 | 避免两次扫描挤得太近 |
| `max_delay` | 10 秒 | 连续有事件时，累计约 10 秒就尝试扫描 |

这三个规则不是同一个东西。`debounce` 解决“成串的事件”；`min_interval` 控制扫描频率；`max_delay` 避免持续活跃导致永远等待。

看看 [`bridge.py`](examples/v04/watchdog/bridge.py) 中这段逻辑：

```python
should_scan = (
    pending_since is not None
    and now - last_scan >= min_interval
    and (
        now - last_event >= debounce
        or now - pending_since >= max_delay
    )
)
```

我们保存的是**本批事件第一次出现时间** `pending_since`，而不是每次新事件都把它清零。这是最大等待能够生效的关键。

> **边界：** 这里的 10 秒是“尝试触发扫描的时间阈值”，不是扫描结果 10 秒内必然完成的严格保证。磁盘繁忙、Git 扫描卡住、操作系统调度都可能让显示延迟。本章不宣称实时硬保证。

### 为什么还有 30 秒兜底巡检？

因为有些文件变化并非 Codex 造成，或者某些工具调用根本没有经过我们接入的 Hook。如果只靠事件触发，就可能永远漏掉这些修改。每 30 秒重新扫描一次，是降低漏检的工程折中；它**仍不代表完整捕获了所有外部变化**。

---

## 五、Bridge 没有重新造 Git 轮子

这里刻意复用了你第三篇真实的 `evidence.py`：

```python
files = evidence.snapshot(repo)
base = evidence.read_json(state / "baseline.json")
changed = evidence.diff_files(base["files"], files) if base else []
current = evidence.fingerprint(files)
```

它们分别负责：枚举 Git 可见文件；读取初始基线；找出内容变化的路径；计算当前整体指纹。

Bridge 再读取第三篇已经保存的 `last_test.json`，判断：

```text
没有测试记录                  → NOT_TESTED
测试前后指纹不一致            → INCONCLUSIVE
现在的工作区指纹与测试后不同   → STALE
测试退出码为 0 且指纹一致     → PASSED
测试退出码非 0 且指纹一致     → FAILED
```

注意 `PASSED` 的完整说法是：**第三篇记录的那一个测试命令，在相应的文件快照上返回了退出码 0**。它不是“所有需求都已实现”，也不是“AI 自己写的测试一定可信”。

Bridge 将报告保存到你已有的 `state/<repo-hash>/bridge_report.json`，即监督器自己的目录，不把运行状态写进被监控仓库。

### 一处容易忽略的 Bug：路径要按仓库区分

如果在项目 A 中启动 Codex，它发来的 `cwd` 是 `D:\\projectA`；Bridge 正在看项目 B，那么这条 Hook 不该让 B 的 Git 扫描误以为是 B 的执行事件。

我们使用 `Path.resolve()` 和路径包含判断做过滤，而不是简单的字符串 `startswith`。否则 `D:\\work\\project` 与 `D:\\work\\project-other` 可能被错误归到同一仓库。

但必须再强调：**事件归属和文件修改者归属是两件事。** 仅凭 `cwd`，我们无法做强审计归因。

---

## 六、动手实验 A：先手动扫描，不连接 Codex

这一步故意不依赖 Hook。你若连单次扫描都跑不通，就没有必要怀疑 Codex 配置。

第一个终端：

```bat
conda activate torch_env
cd /d D:\program\agent_watchdog\watchdog
python bridge.py --repo "D:\program\agent_watchdog\hook_demo" --once
```

可能得到：

```text
{
  "trigger": "manual",
  "has_baseline": true,
  "changed": ["hello.py"],
  "protected": [],
  "test_status": "STALE"
}
```

输出值以本机为准，不能照抄。尤其是你的 `hook_demo` 在第三篇做过保护文件实验：若 `GOAL.md` 当时还没复原，这里也可能显示它已被修改。

如果 `has_baseline: false`，说明本教程没有在该 Git 根目录识别到第三篇基线。需要检查 `--repo` 是否指向同一仓库；**不要未经检查就重新 baseline，因为那相当于重新定义什么叫初始状态。**

---

## 七、动手实验 B：打开双终端，让文件变化自动显示

### 第一个窗口：启动 Bridge

```bat
cd /d D:\program\agent_watchdog\watchdog
python bridge.py --repo "D:\program\agent_watchdog\hook_demo"
```

会显示监控仓库路径、开始读取新事件，以及“不自动运行测试”的说明。

### 第二个窗口：启动 Monitor 04

```bat
cd /d D:\program\agent_watchdog\watchdog
python monitor04.py --repo "D:\program\agent_watchdog\hook_demo"
```

Rich 会展示“Git / Test 独立证据”和“最近 Hook 事件”。如果还没有报告，它会显示未扫描；这是**程序状态的诚实表达**，而不是失败。

### 第三个窗口：模拟一个文件修改

```bat
cd /d D:\program\agent_watchdog\hook_demo
notepad hello.py
```

在末尾添加：

```python
# Experiment for chapter 04
```

保存后，先观察面板是否在兜底巡检中发现变更；然后手工发送一条模拟的 `PostToolUse`：

```powershell
$payload = @{ hook_event_name='PostToolUse'; tool_name='Bash'; session_id='manual-v04'; cwd='D:\program\agent_watchdog\hook_demo' } | ConvertTo-Json -Compress
$payload | & 'D:\program\agent_watchdog\watchdog\hook_runner_v04.cmd'
```

**上面两行是在 PowerShell 执行，不是在 Anaconda Prompt 的 CMD 语法中执行。** 请另外打开 PowerShell，避免把 `$payload` 当成 CMD 命令。

如果 Hook Logger 追加了事件，Bridge 读取它并触发扫描，面板就会看到相应更新。到这里证明的是**模拟链路**，并非真实 Codex 连接。

### 另一项必须做的反例

在第三个窗口手工修改 `GOAL.md`，观察保护文件栏是否能出现 `GOAL.md`。这一步证明我们不是仅仅在“显示 Hook 发生了”，而是真正根据 Git 内容判断违规情况。

---

## 八、动手实验 C：最后才接入真实 Codex

把 [`hook_runner_v04.cmd`](examples/v04/watchdog/hook_runner_v04.cmd) 中的 Python 解释器路径配置正确，并在测试仓库的 `.codex/hooks.json` 中将 `PostToolUse`、`Stop` 映射到这个 Runner。

参考的项目 Hook JSON：

```json
{
  "hooks": {
    "PostToolUse": [{
      "hooks": [{
        "type": "command",
        "command": "cmd.exe /d /c D:\\program\\agent_watchdog\\watchdog\\hook_runner_v04.cmd",
        "timeout": 10
      }]
    }],
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "cmd.exe /d /c D:\\program\\agent_watchdog\\watchdog\\hook_runner_v04.cmd",
        "timeout": 10
      }]
    }]
  }
}
```

如果原来的 `.codex/hooks.json` 已经配置并仍然有效，**不要追加重复定义**；在备份之后调整对应的 `command` 即可。确保 Codex 从 `hook_demo` 启动：

```bat
cd /d D:\program\agent_watchdog\hook_demo
codex
```

进入 CLI 后使用 `/hooks` 查看加载与信任情况。项目 Hook 只有在项目级配置受信任、对应 Hook 被审核之后才能运行。我们不使用任何跳过信任的参数。

给 Codex 一个小任务：

> 在 `hook_demo` 内新建 `feature_v04.py`，写一个 `add(a,b)` 函数，运行 Python 验证 `add(2,3)==5`。不要修改 `GOAL.md`，不要访问别的仓库。

**只有当现场能观察到真实 Codex 工具操作引发的日志变化、Bridge 扫描和 Monitor 更新，才能标记真实端到端验收成功。** 单独手工运行 Logger 不够。

---

## 九、常见问题：用证据定位，不要靠猜

| 现象 | 真正应该先检查什么 |
|---|---|
| 手工 JSON 能写入，Codex 没有事件 | CLI `/hooks`，项目是否受信任，命令是否指向新 Runner |
| Bridge 能单次扫描，但不自动刷新 | `bridge.py` 是否持续运行，事件 `cwd` 是否属于目标 repo，日志是否写入同一路径 |
| 日志显示 `Stop`，但工具事件很少 | 工具是否经过普通 Hook 路径；不能推断 Agent 没有工作 |
| 文件变化被发现，但无法确认是谁改的 | 这是设计边界，不是 Python 异常。Git 快照没有作者归因 |
| `STALE` 一直不消失 | 检查第三篇的 `last_test.json` 是否属于旧文件快照；明确重跑可信测试 |
| 终端显示 `python` 找不到 | 配置 `hook_runner_v04.cmd` 中的绝对解释器路径 |
| 源码运行时报 `ModuleNotFoundError: rich` | 只在 `torch_env` 中安装 Rich，确认运行时 `python` 路径一致 |

### 本篇的安全边界

- `evidence.py` 原版扫描 Git 跟踪文件和未忽略的文件；`.gitignore` 排除项与外部数据库不在范围内。
- Bridge 只读取新日志事件。重启和历史补采的问题留到第 09 篇处理。
- Hook 调用失败应让 Codex 正常继续；不能用监督器绑架执行器。
- `Monitor 04` 上的“最近事件计数”不是完整历史统计。
- 本版不自动测试、不 rollback、不自动 kill、不根据“无新事件”判定 stuck。

---

## 十、给自己做一次真正的验收

不要只看程序有没有打印绿色文字。自己回答这五个问题：

1. 事件为什么需要 `cwd`？它为什么又不能证明是谁修改了文件？
2. 为什么不能每个 `PostToolUse` 直接全量扫描 Git？
3. `debounce=2s` 与 `max_delay=10s` 分别解决什么问题？
4. 为什么测试通过后再改一行注释，也会保守地得到 `STALE`？
5. 关掉 Rich 面板，Codex 是否应该受到影响？

本篇通过条件：模拟日志链路可以刷新；保护文件变化能被独立观察；真实 Codex 接入有独立的终端记录；关闭面板不影响 Codex 运行。未通过的项目请如实打叉，不要因为我们写了教程，就将其改为“完成”。

**下一篇：**《从零开发 Agent Watchdog（05）：任务契约——把“修复功能”变成机器可以验收的条件》。那时监督器才开始知道，用户究竟要它监督什么。

**进一步阅读：** [Codex Hooks](https://developers.openai.com/codex/hooks) · [Rich Live](https://rich.readthedocs.io/en/stable/live.html) · [Git ls-files](https://git-scm.com/docs/git-ls-files) · [本篇完整源代码](examples/v04/watchdog/)。
