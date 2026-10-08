# 从零开发 Agent Watchdog（18）：给监督器做一张真正能用的 Web 面板——从 Rich 到 Streamlit

系列教程 · 第 18 篇｜Python · Streamlit · SQLite · 本地只读界面

> **本篇目标**：不再要求你一直盯着多个终端，给已有的事件账本、合同验收和风险提示加一个本地 Web 控制台。本章不是重新写一个独立的 AI Agent，也不会让网页自动执行危险操作。交付文件为 [dashboard.py](examples/v04/watchdog/dashboard.py)，对应上一章已经完成的 `supervision.py`。

## 一、我们为什么还要做一个面板？第 02 篇不是已经有 Rich 了吗？

第 02 篇我们用 Rich 完成了第一块终端面板。那一步非常重要：你第一次不需要看 Codex 原始聊天记录，就能在另一个窗口看到工具事件。第 04 篇又让 Bridge 把事件变化和 Git 证据关联起来。

但是当你真的长期同时运行 Codex、Anaconda Prompt、VS Code 和实验程序时，一个问题出现了：你已经有多个终端，却还要在它们之间切换才能判断任务进度。比如你需要知道：任务有几个验收项？哪些依然是 `NOT_TESTED`？哪些变成了 `STALE`？刚出现的风险事实有没有对应文件？

Rich 面板不是错误的选择。它的优势是轻量、依赖少、SSH 和纯终端适用。Web 面板则能把状态分区显示，用表格筛选事件，也更容易给以后多个项目提供统一入口。

我们本篇选择 Streamlit，而不是从零手写 React + FastAPI + WebSocket，原因与你之前开发 AI 通知雷达的经验一致：**先把可以验证的监督信息呈现出来，而不是先造一个复杂前端系统。** 你之前安装过 Streamlit 1.51.0，但是否仍在当前 `torch_env` 里可用，需要本次运行前检查。

## 二、架构上最容易犯的错误：把“显示状态”写成“改变状态”

思考一个危险的情景：用户打开网页，页面自动运行一次 `pytest`。他只是想看任务进度，却触发了会写缓存、访问数据库乃至连接远端服务的代码。又或者用户每刷新一次页面，后台都把旧证据改写成“最新通过”。

**监督界面必须尽量是读的一端，而不是执行的一端。**

```text
         Codex / 你的手动验收
                    │
                    ▼
     Hook Logger / Bridge / Contract
                    │
                    ▼
            本地日志及状态
                    │
          ┌─────────┴──────────┐
          ▼                    ▼
   Rich monitor04.py     Web dashboard.py
          │                    │
          └──────────┬─────────┘
                     ▼
         仅显示观察到的状态与限制
```

这里我们不调用旧的 `watchdog_cli.report()`，因为它在没有保存的 Bridge 报告时可能主动触发一次 Git 扫描并写报告。第 18 篇的 `snapshot()` 直接读取已存在的 `bridge_report.json`，并通过第 17 篇的监督器查询合同和脱敏事件。**页面本身不会创建新的 Bridge 报告，不会运行测试，不会发送 Agent 控制命令。**

不过，`scope_guard.check()` 的证据计算需要读取 Git 工作树并可能在仓库外准备状态目录；因此这里说的是“只读监控目标仓库与不执行 Agent 操作”，并非承诺完全没有文件系统副作用。要实现更严格的只读沙箱，还需要权限隔离与专门的查询 API。

## 三、先设计你真正需要看到的界面

设想一个本地页面，在屏幕上方显示三个数字：

```text
┌─────────────────┬──────────────────┬─────────────────┐
│ 任务验收阶段     │ 独立风险事实      │ 待复核弱信号     │
│ IN_PROGRESS     │         1        │         0       │
└─────────────────┴──────────────────┴─────────────────┘

验收项
A1  PASSED
A2  STALE
A3  NOT_TESTED

事实提醒
ACCEPTANCE_STALE: A2
建议：由用户检查并显式运行已批准的验收项

最近事件（脱敏）
时间    session_id   event        tool
...     ...          PostToolUse  Bash
```

这是**目标效果示意**，不是你真实 Codex 的截图。界面重点不是做复杂动画，而是让你进入页面时，先看到最值得行动的信息。

注意三个数字的含义：`独立风险事实=1` 不等于“项目失败一次”；`待复核弱信号=0` 不等于“Agent 没有风险”；`IN_PROGRESS` 也不是根据 Agent 自己说了什么推出来的。

## 四、用 Streamlit，但不要把每个模块都塞进一份文件

项目目录保持不变：

```text
D:\program\agent_watchdog\watchdog\
├── evidence.py              # 第 03 篇
├── bridge.py                # 第 04 篇
├── task_contract.py         # 第 05–06 篇
├── journal.py               # 第 09 篇
├── scope_guard.py           # 第 16 篇
├── supervision.py           # 第 17 篇
└── dashboard.py             # 第 18 篇新增
```

本篇完整源码见 [examples/v04/watchdog/dashboard.py](examples/v04/watchdog/dashboard.py)。用“数据层”和“显示层”分开，是为了让你以后更换 Streamlit 页面设计时不必修改任务验收规则。

### 第一层：一个无前端依赖的快照函数

```python
def snapshot(repo, db=journal.DEFAULT_DB):
    repo = evidence.root_for(repo)
    current = evidence.read_json(
        evidence.state_dir(repo) / 'bridge_report.json'
    ) or {}
    safe_events = supervision.recent_events(db, limit=20)
    assessment = supervision.diagnose(repo, db=db, events=safe_events)
    return {
        'repo': str(repo),
        'git': current,
        'assessment': assessment,
        'events': safe_events,
    }
```

它接收受监控 Git 仓库和事件数据库路径，返回普通 Python 字典。这样我们就可以不启动浏览器直接写单元测试，证明“调用一次状态读取不会创建新的数据库、不会产生 Bridge 扫描报告”。

为什么要把 `snapshot()` 放在 `main()` 外面？因为 `streamlit` 只在启动网页时才是必要依赖。只想运行风险规则、导入事件、执行后台测试的同学，不应因此强制安装整个 Web 框架。

### 第二层：Web 页面只负责展示

```python
import streamlit as st
st.set_page_config(
    page_title='Agent Watchdog',
    page_icon='🛡️',
    layout='wide',
)

st.title('🛡️ Agent Watchdog · 本地监督面板')
st.caption('只显示独立观察到的证据与风险提示；不执行测试，不控制 Codex。')
```

`st.metric()` 用来显示状态与数量，`st.table()` 显示逐项验收，`st.json()` 用来让高级用户查看结构化风险证据，`st.dataframe()` 展示事件。先不加入任何“重试”“终止”“自动改代码”按钮。

### 第三层：为什么用 st.fragment 定时刷新？

如果没有刷新机制，Web 页面只会展示打开时的数据；如果每秒完整重跑所有代码，对于逐渐扩大的页面不划算。Streamlit 的 `st.fragment` 支持 `run_every`，可以让特定区域按间隔更新。

```python
@st.fragment(run_every='5s')
def live():
    data = snapshot(args.repo, args.db)
    # 更新显示区域
```

本例选择每五秒更新一次。它不是“严格实时事件流”，因为 Bridge 本身会节流，浏览器也可能暂停或断线。**五秒刷新代表页面的查询频率，不代表工具事件到页面的最大端到端延迟。**

官方文档明确支持片段刷新机制；你当前的 Streamlit 1.51.0 已高于官方教程要求的 1.37.0。但版本不等于已验收，我们仍应先用 `python -c` 检查运行环境再启动。参见 [Streamlit st.fragment 文档](https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment)。

## 五、安装和启动：Windows 11 两个终端

先打开 Anaconda Prompt，确认虚拟环境：

```bat
conda activate torch_env
python -c "import streamlit; print(streamlit.__version__)"
```

若出现 `ModuleNotFoundError`，再执行：

```bat
python -m pip install "streamlit>=1.37,<2"
```

本篇不需要再安装 CUDA、PyTorch、Transformers 或 StepWise。对于一般 Web 面板，CPU 已经足够。

**第一个终端：**运行已有 Bridge 监控器，负责在事件触发或巡检时更新独立 Git 证据：

```bat
cd /d D:\program\agent_watchdog\watchdog
python bridge.py --repo "D:\program\agent_watchdog\hook_demo"
```

**第二个终端：**运行 Streamlit（这里的 `--` 表示后续参数传递给 `dashboard.py` 而不是 Streamlit 本身）：

```bat
cd /d D:\program\agent_watchdog\watchdog
python -m streamlit run dashboard.py -- --repo "D:\program\agent_watchdog\hook_demo"
```

如果你把 SQLite 放在了自定义目录：

```bat
python -m streamlit run dashboard.py -- --repo "D:\program\agent_watchdog\hook_demo" --db "D:\program\agent_watchdog\watchdog\data\journal.sqlite3"
```

通常浏览器会打开一个本地地址（如 `http://localhost:8501`，具体端口以终端实际输出为准）。请**只在你自己受信任的电脑上运行**。Web 页面中可能显示项目路径、会话 ID、文件相对路径和测试状态，虽然不包含完整命令和密钥，仍不应直接暴露到公网或通过未授权网络分享。

## 六、实验 A：没有数据时，页面应该是什么样？

假设你忘记启动 Bridge，而且事件数据库还没创建。错误的实现会偷偷初始化一个新数据库，然后面板显示一切正常；正确的实现会明确告诉你没有观察到事件，现有报告为空。

本篇测试了两项很具体的行为：调用 `snapshot()` 不应创建不存在的事件 SQLite 文件；也不应生成不存在的 `bridge_report.json`。对应自动测试位于 [test_release_round.py](examples/v04/tests/test_release_round.py)。

这项实验提醒我们：**界面的漂亮程度，绝不能高于信息的真实性。** 空白不是失败，冒充有数据才是失败。

## 七、实验 B：制造一次 STALE，观察网页更新

这个实验要有已经批准的合同和一项已运行的验收。你可以按照第 05–06 篇教程先在独立仓库完成合同批准和测试。随后故意修改被测试覆盖的 Git 可见文件，但不重跑测试。

现在在 **Anaconda Prompt** 中检查：

```bat
python task_contract.py --repo "D:\program\agent_watchdog\hook_demo" status
```

如果看到某一项由 `PASSED` 变为 `STALE`，说明证据过期规则生效。切回浏览器，在下一个刷新周期观察页面。如果 `st.table` 对应行没有变化，先检查当前界面传入的是不是同一 `--repo`；再确认 Bridge 是否正在更新本地快照，最后才排查 Streamlit 的定时刷新。

注意：网页**不会**自动重新执行那项测试。你必须根据第 06 篇的规则显式运行自己已经确认安全的命令。

## 八、实验 C：关闭网页会停止 Codex 吗？

尝试按 `Ctrl+C` 退出 Streamlit。你会发现页面进程结束，但它不会因此向 Codex 发送 stop 或 kill。Codex CLI、Hook Logger、Bridge 是不同组件，有各自的生命周期。

这个实验看起来简单，却切中了“独立监督”的定义：**观察窗口的故障不应当自动变成被观察者的控制命令。**

在未来 V2.0，如果你确实需要人工确认的暂停或恢复，那也必须设计明确的权限、审批和审计机制，而不能把页面按钮直接绑定到任意子进程操作。

## 九、我们为什么不在这一篇使用 WebSocket？

你可能见过大型监控系统使用 WebSocket、事件总线、前后端分离。那是一种合理架构，但它不是当前用户体验问题的必要条件。我们已有 JSONL 和 SQLite，可以低成本地每几秒查询一次。只要事件总量和并发不大，这种方式足以验证产品价值。

当用户真正需要毫秒级延迟、几十个同时在线客户端或跨机器监督时，再对采集、存储和前端传输层做压力测量。不要因为未来可能扩展，就提前承受今天并不需要的架构复杂度。

### 一个更深层的设计问题

为什么不能简单从数据库 `SELECT *`，然后把所有原始内容直接给 Web 页面？因为你的目标是监督 Agent，而不是建设第二份保存密码、个人消息和工具输出的高风险数据库。当前默认仅保存少量事件元数据，Web 页面也只使用这份脱敏视图。

只要后续要保存更多内容，就应考虑字段级别脱敏、日志保留周期、访问控制、存储加密、备份位置和泄露风险。安全边界是产品能力的一部分。

## 十、常见问题及排查

| 现象 | 可能原因 | 优先处理 |
|---|---|---|
| `No module named streamlit` | 当前 Conda 环境未安装 | 检查 `where python` 与 `python -m pip` |
| `st.fragment` 不存在 | Streamlit 版本太低 | 查看版本，再在正确环境升级 |
| 面板一直空 | 没有日志、没有合同、Bridge 未生成快照 | 先运行第 13 篇的集成检查 |
| 明明有 `events.jsonl` 却没显示事件 | SQLite 尚未同步 JSONL | 运行 `python journal.py sync` |
| 一次浏览器刷新导致文件状态变化 | 需要排查 UI 是否错误调用写入 API | 用本篇只读测试检查 `dashboard.snapshot` |
| 同学能从外网打开你的页面 | 绑定或网络设置不安全 | 立即停止共享，仅在本机运行 |

## 十一、这一篇到底做成了什么？

- [ ] 可以在浏览器里查看已保存的验收状态、事实提示、启发式弱信号和最近事件。
- [ ] 页面刷新不会自动执行测试、创建新的 Bridge 扫描报告或控制 Codex。
- [ ] 当文件变化使验收从 `PASSED` 变为 `STALE` 时，页面能够显示相应状态（以你本机实验为准）。
- [ ] 无数据时明确显示缺少证据，不冒充系统已连接。
- [ ] 能解释为什么这里是“定期刷新视图”，而不是严格实时事件流。
- [ ] 已检查本地访问范围，没有直接向公网开放页面。

**小结**：第 18 篇使 Watchdog 开始拥有便于日常使用的前端，但界面并不等于可靠运行。电脑重启、日志断档、数据库损坏、备份失败这些问题会直接影响它值不值得托付长期任务。第 19 篇我们就来处理这件事。

### 参考资料

- [本篇完整代码：dashboard.py](examples/v04/watchdog/dashboard.py)
- [监督数据源：supervision.py](examples/v04/watchdog/supervision.py)
- [Streamlit 官方 st.fragment](https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment)
- [Streamlit 安全与部署文档](https://docs.streamlit.io/deploy)
- [第 13 篇：联调与证据边界](从零开发%20Agent%20Watchdog（13）.md)

> **实际状态**：本篇 `snapshot()` 的只读行为已有隔离测试，但浏览器 UI 需要在你的 Windows + Streamlit 环境中人工测试，不能把 Python 单元测试当成界面端到端通过。
