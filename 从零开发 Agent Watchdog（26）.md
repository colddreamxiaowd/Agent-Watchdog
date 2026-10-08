# 从零开发 Agent Watchdog（26）：StepWise 不是魔法按钮——在同一批任务上检验小模型是否真的有增益

> 第 26 篇 · 小模型评价 · StepWise · 训练/测试泄漏 · 预注册 · Windows 离线评估  
> 当前状态：**已实现可运行的评分比较协议，不代表已经执行 StepWise 模型、更不代表在 Codex 上证明其有效。**

## 一、为什么以前跑通了 ModernBERT，现在却不能直接说“卡住检测已实现”？

你最早开发 Agent Watchdog 时，已经在本机跑过 StepWise 的示例检测代码。那时候的直觉很自然：既然模型能检测“卡住”，拿它分析 Codex 的终端执行记录不就好了？

问题是，**模型学过什么、我们能提供什么、我们要判断什么，可能是三件事**。

[StepWise 官方仓库](https://github.com/yale-nlp/StepWise)的 Stuck Monitor 读取近期若干步骤的动作与解释文字，在 GUI Agent 轨迹里检测局部无进展现象；其 Milestone Monitor 则接受任务条件，预测是否到达某个值得验证的里程碑。官方 [ComputerRouter](https://github.com/yale-nlp/StepWise/blob/main/ComputerRouter/README.md) 使用 OSWorld 类型的环境、模型检查点以及 GUI 步骤轨迹；[build_stuck_dataset.py](https://github.com/yale-nlp/StepWise/blob/main/ComputerRouter/bert/build_stuck_dataset.py) 中可以看到把最近多个步骤的文本拼成训练样本。

而我们目前的 `execution_v2.py`，恰恰**为了保护隐私**默认不保存命令、解释文本、屏幕内容或提示词，只留下工具类别和结构化结果。如果把“Bash, Bash, Bash”当作 StepWise 熟悉的动作/解释窗口，这样的输入分布与训练阶段并不等价。

另一个差别是目标。StepWise 原本的“GUI stuck”标签，不等于我们第 25 篇定义的“重复失败是否需要用户干预”；两个标签不能因为英语里都有 stuck 就直接替换。

所以本篇不是“把 StepWise 加载起来，看到一个 0.83 的概率就宣布成功”。我们要先把*能进行可信比较的条件*写成可机械执行的契约。

## 二、最容易制造假进步的三种研究方式

**第一种：拿不同数据各算一个准确率。** 例如规则基线用真实 Codex Bash 事件，StepWise 用作者发表的 OSWorld 测试结果。这不是公平比较。数据、任务、标签和输入都不同。

**第二种：结果出来后再调整阈值。** 用留出的测试集找最有利的 `threshold=0.42`，然后用相同测试集报告它的高 F1。这是在测试集上开发方法，不能再把它当作未见数据。

**第三种：随机按行拆分而不按任务/会话隔离。** 同一个 Codex 会话有上百步高度相似记录。把前 50 步随机分给训练、后 50 步分给测试，模型很可能记住任务独特细节。最起码要按会话隔离；跨会话重开同一任务时，最好进一步按项目和任务身份分组。当前脚本只自动检查 session 级，不能冒称更严格的任务隔离已经完成。

一个科学的比较可以很小，但所有这些门槛都必须事先规定。

## 三、我们准备了怎样一套独立评价接口？

[stepwise_compare_v26.py](examples/v04/watchdog/stepwise_compare_v26.py) 并不连接云服务，不加载 Transformer，不要求 PyTorch，也不从 Hugging Face 下载东西。它接收两个明确输入：

```text
用户自己批准的数据与分割
            │
            ├── protocol.json
            │   ├─ 本次标签定义
            │   ├─ 人工审核和冻结状态
            │   ├─ 阈值 threshold
            │   └─ 门槛 min_test_positives
            │
            └── samples.json
                ├─ sample_id
                ├─ session_id / split
                ├─ label            人工判定的真值
                ├─ rule_alarm       固定规则基线
                └─ model_score      另一个已实际运行的模型的分数
                         │
                         ▼
                   成对评价报告
```

这叫“评价接口”和“输入验证器”，**不是 StepWise 真实推理引擎**。如果没有真正从 StepWise 产生过可比较的分数，`model_score` 就应该是 `null`，程序明确返回 `external_model=NOT_EVALUATED`。

为什么这样做？你有 RTX 5060 8GB / 16GB RAM，但我们这一轮真正缺的不是显卡算力，而是对应的数据与验证协议。强行下载安装模型只会产生一个貌似完成的演示，不会解决能不能用的问题。

## 四、protocol 文件为什么必须在看测试标签前冻结？

你可以打开 [协议示例](examples/v04/watchdog/stepwise_protocol.example.json)：

```json
{
  "schema_version": 1,
  "task": "repeated_failure_review",
  "data_kind": "synthetic",
  "annotation_frozen": true,
  "threshold": 0.5,
  "min_test_positives": 2,
  "label_definition": "Explicitly reviewed repeated-failure episode requiring user intervention, not every long or failed command."
}
```

这是**教学示例**，不是已经完成的研究预注册。`data_kind=synthetic` 明确告诉任何看报告的人，这里的样本仅用于测试公式与边界，不得用来宣传检测模型。

这里的 `threshold` 是固定的分数分界；`min_test_positives` 是本问题自己定义的正例最低门槛，并非来自某篇论文的普遍常数。没有提前冻结的阈值，代码直接拒绝。正例不足、负例不存在时，也不会给出“模型赢了”的结论。

当然，任何人都可以编辑 JSON 后声称 `annotation_frozen=true`。这是普通文件，**不能当密码学证明**。真实比较还需要独立的时间戳、版本/摘要、谁标注、谁打开了测试标签以及可复核的运行记录。脚本不会替代这一层治理。

## 五、要算什么指标？为什么准确率经常误导我们？

我们的试验目标不是“模型总能猜对大多数正常任务”，而是在不刷屏的条件下发现值得人工介入的失败。例如 100 个窗口只有 5 个真正需要介入，模型全部预测正常，仍有 95% 的所谓准确率，却完全没有帮助。

因此至少记录四格：

| | 真正需要介入 | 不需要介入 |
|---|---:|---:|
| 发出提醒 | TP | FP |
| 不提醒 | FN | TN |

`Precision=TP/(TP+FP)` 衡量你收到提醒时有多少值得看；`Recall=TP/(TP+FN)` 衡量真实异常被捕获多少；`F1` 是精确率和召回率的调和平均。分母为零时结果为 `null`，不能神奇地变成满分。

程序同时计算**同一批 held-out 测试窗口**的规则基线和外部模型表现，并在都可定义时给出 `paired_difference_f1`。但这还不是统计显著性，更没有置信区间或时延比较；真实准入还需要在前瞻性协议里写好这些要求。

另外：第 26 篇的代码没有收集未判定比例的充分真实观测来源。那些 `UNKNOWN` 无法随意强改成负例，否则模型可能因跳过最难的场景而显得非常优秀。

## 六、Windows 上做第一次实验：模型分数缺失时会发生什么？

在本轮仓库根目录运行：

```bat
conda activate torch_env
cd /d D:\program\agent_watchdog\Agent-Watchdog-v2-round2-eval
python -m unittest discover -s examples\v04\tests -p test_round2.py -v
cd examples\v04\watchdog
python stepwise_compare_v26.py --protocol stepwise_protocol.example.json --samples stepwise_samples.example.json
```

示例数据没有运行过 StepWise，故所有 `model_score` 是 `null`。预期出现：

```json
{
  "status": "SYNTHETIC_ONLY",
  "external_model": "NOT_EVALUATED",
  "model_execution": "NOT_RUN_BY_WATCHDOG",
  "reason": "external model scores missing on held-out rows"
}
```

这里截取的是**关键字段的预期含义示意**，完整 JSON 还包含 `n_test`、类别计数和规则指标。看到这个结果不是失败；相反，它说明工具不会把“没有真实模型运行”包装成已经评估。

若要真正比较，需要你明确授权使用的模型权重和符合其实际输入要求的轨迹，再另建私有评分文件。不允许在公开视频或公共仓库中上传模型需要的原始提示、完整工具命令或用户私人代码。

## 七、四个必须故意制造的错误

**反例 A：把同一个会话拆进 train 与 test。** 代码应该拒绝，报 `session leakage between splits`。这只是最低防线，同一任务跨多个会话的泄漏还要在正式协议另行审查。

**反例 B：把阈值删掉。** 程序应拒绝。这样不能看到某个分数不错之后再偷偷选一个最漂亮的阈值。

**反例 C：用文字代替标签。** `label="1"` 并不等于 JSON 数值 1；`rule_alarm="true"` 也不是 JSON 布尔值。程序不做方便却危险的隐式转换。

**反例 D：只有一个真阳性，没有达到事先设定的正例门槛。** 即使 F1 计算出了数值，状态仍为 `INSUFFICIENT_FOR_PREDECLARED_GATE`。这时展示诊断指标可以，但不能宣称模型已经通过评价。

还可以追加第五个反例：在样本 JSON 中填一个你手工捏造的 `model_score=0.99`，程序确实能算出指标，但输出仍不会变为 `VALIDATED/GO`，因为文件本身不能证明来源是 StepWise。整个评估工具的“不会过度声称”，和指标本身同样重要。

## 八、为什么现在不直接复制整套 StepWise 训练框架？

官方 ComputerRouter 所需的 OSWorld、GPU、多个代理模型及环境依赖，并不等于单独部署 Watchdog 时必需的组件。直接复制大仓库会让我们承担大量 Windows 兼容、权重许可、环境搭建与数据分布问题，但第 25 篇连真实“重复失败”标签都还没有。

我们复用的是公开发表的任务理解：Stuck Monitor 与里程碑监测是不同的问题，检测可以用轻量模型，只有在具体风险触发时再做更昂贵的分析。**不复制未经确认适用的实现，也不把论文指标照搬到我们的场景。**

一旦获得真正的、经过许可的对应数据，下一步可以在私有工作环境中构造与 StepWise 原始训练输入一致的窗口、记录模型 revision/hash，然后与元数据规则在同一批样本上比较。只有出现明确的增量价值、误报可接受、性能代价可承受，才值得考虑把它接到实时链路。

## 九、本篇做成了什么，留下了什么？

完成的是：不下载模型也能运行的离线配对评价接口；预先冻结的阈值；跨会话隔离；缺模型分数、缺真实数据、正例不足的显式状态；对规则基线和模型预测的可检查指标计算。

尚未完成的是：真实运行 StepWise 在 Codex 任务上的模型输出、确认任务标签吻合、测量实际误报/漏报/延迟、真实 Windows 长期验证。**这条候选目前是“评估基础设施可用，StepWise 是否适用还没有证据”。**

下一篇处理另一种更棘手的监督：Agent 可能一切命令都成功，却已经偏离原始目标。这个问题绝不可以仅凭一个模型的直觉对用户贴“越权”标签。

代码：[stepwise_compare_v26.py](examples/v04/watchdog/stepwise_compare_v26.py) · [工程证据门槛](docs/ROUND2_EVIDENCE_PROTOCOL.md) · [StepWise 官方仓库](https://github.com/yale-nlp/StepWise)。
