# Scoreable Prediction Tap（SPT）防 scoop 文献审计

审计日期：2026-08-13（Asia/Hong_Kong）

结论：**允许进入小规模证伪 pilot，但必须收窄 novelty claim。**

## 预先冻结的重叠门

在判断文献是否构成直接 scoop 前，固定以下五个要素：

- **A — 开放程序插桩**：自动处理自由形式/agent 生成的 MLE 代码，而不是要求固定训练 API；
- **B — 真实预测截获**：取得中间 test-facing prediction 值，而不是只打印“已经 predict”的 milestone；
- **C — 可评分重建**：把该值恢复为 schema-valid candidate，并由外部 hidden-label grader 评分；
- **D — 语义保持干预**：对同一个 base program 做有/无干预比较，并验证输出或分数等价；
- **E — 搜索用途**：用早期 artifact 排 sibling 或分配固定执行预算。

单篇工作达到 4/5 视为直接 scoop、停止；达到 3/5 视为 close baseline，必须围绕它重新定义差异；≤2/5
视为相邻工作。该门在作出 proceed/stop 判断之前固定。

## 检索范围与协议

检索标题、摘要、arXiv HTML/PDF 正文、related work 和可用官方代码页，覆盖四类文献：

1. MLE agents 与 execution feedback：AIDE/AIRA、AIRA_2、MLE-Dojo、RL4MLE、KompeteAI、SandMLE、
   Matryoshka Agent、ML-Agent、MLE-Smith、MLE-STAR；
2. anytime AutoML、multi-fidelity HPO/NAS、early stopping、performance prediction；
3. program instrumentation、trace-driven code repair、ML pipeline observability/provenance、transparent hooks；
4. partial code execution 与 agent-loop early termination。

检索词组合包括 `MLE agent`、`generated ML code`、`instrumentation`、`predict_proba`、
`test predictions`、`submission.csv`、`intermediate artifact`、`hidden grader`、
`candidate selection`、`partial execution`、`anytime AutoML`。另对 “prediction tap”、
“scoreable prediction”、“prediction tapping” 做精确短语检索；未发现本问题设定下的同名方法。

## 最接近工作与固定打分

| 工作 | A | B | C | D | E | 总重叠 | 对主张的约束 |
|---|---:|---:|---:|---:|---:|---:|---|
| [Reinforcement Learning for MLE Agents（ICLR 2026）](https://arxiv.org/abs/2509.01684) | 1 | 0 | 0 | 1 | 0 | 2/5 | 最强 MLE 插桩先例。它用静态 LM 插入 print，并可在 test prediction 后记录 milestone；不截获 prediction 值、不重建/评分中间 submission，也不以该分数选 sibling。它还微调底座 LM，而本项目禁止。 |
| [TraceCoder（ICSE 2026）](https://arxiv.org/abs/2602.06875) | 1 | 0 | 0 | 1 | 0 | 2/5 | 最强 semantic-purity 先例：向 LLM 代码插诊断 probe，并报告 99.32–100% 的经验保持率；没有 MLE prediction、task grader 或候选搜索。 |
| [Data distribution debugging in ML pipelines / mlinspect](https://doi.org/10.1007/s00778-021-00726-w) | 0.5 | 1 | 0 | 1 | 0 | 2.5/5 | 可透明插桩 pandas/sklearn pipeline 并暴露 prediction/provenance；不面向开放生成程序、不恢复 Kaggle submission、不指导搜索。它否定“透明截获 prediction 本身新颖”。 |
| [AutoDL Challenge / anytime learning](https://proceedings.mlr.press/v123/liu20a.html) 与 [Zero-Shot AutoML](https://proceedings.mlr.press/v162/ozturk22a.html) | 0 | 1 | 1 | 0 | 0.5 | 2.5/5 | 固定 AutoDL 接口可交替训练和输出 test predictions，并事后形成 learning curve；不从任意生成程序恢复预测，也没有同代码 identity intervention。它否定“中间 test prediction 可评分本身新颖”。 |
| [KompeteAI](https://arxiv.org/abs/2508.10177) | 0 | 0 | 0 | 0 | 1 | 1/5 | 用缩短 epoch 的 log/metric 加 LLM scoring model 排候选，是效率实验必须比较的 baseline；其信号不是从程序状态恢复的 hidden-grader score。 |
| [AIRA_2](https://arxiv.org/abs/2603.26499) | 0 | 0 | 1 | 0 | 1 | 2/5 | 有外部一致评测和搜索选择，但只在完整 candidate 产生规定输出后评分。 |
| [Matryoshka Agent](https://arxiv.org/abs/2607.25090) | 0 | 0 | 1 | 0 | 1 | 2/5 | 最新且直接相关的长程 MLE agent；subagent 只有创建 valid submission 后才得到分数，失败/未完成尝试没有 task score。 |
| [SandMLE](https://arxiv.org/abs/2604.04872) | 0 | 0 | 1 | 0 | 0 | 1/5 | 用 micro-dataset 缩短反馈，但仍评分显式 submission，并微调 policy。 |
| [AgentExecutor](https://arxiv.org/abs/2608.05959) | 0.5 | 0 | 0 | 0 | 0 | 0.5/5 | 通过合成上下文执行不完整代码；没有 MLE artifact 恢复或评分。 |
| [EET](https://arxiv.org/abs/2601.05777) / [Semantic Early-Stopping](https://arxiv.org/abs/2606.27009) | 0 | 0 | 0 | 0 | 0.5 | 0.5/5 | 依据经验/置信度或语义收敛停止 agent loop，不产生 task-level intermediate prediction score。 |

没有单篇工作达到预先冻结的 3/5 close-baseline 门，更没有达到 4/5 direct-scoop 门。但
**mlinspect + AutoDL 的组合在概念上覆盖 A/B/C/D**，所以 SPT 很容易被审稿人视为已有部件的自然拼接，
不能作为“新的 instrumentation primitive”单独立论。

## 可辩护、但必须由实验支持的主张

禁止声称：

- 首个 runtime ML-pipeline instrumentation；
- 首个 prediction-value capture；
- 首个 anytime test-prediction scoring；
- 首个给 MLE agents 提供 dense/partial feedback。

条件性可辩护主张：

> 开放式 MLE agents 存在 observation mismatch：候选程序常在满足最终 artifact contract 之前已经计算出
> task-relevant predictions，但现有搜索环境直到完成才给 task score。我们研究一个 precision-first、
> semantics-preserving、可 abstain 的 observation adapter，只恢复可识别的 test-facing predictions，物化为
> 外部可评分 candidate，并把该信号用于固定预算 sibling selection；评测 coverage、语义等价、反馈时延、
> ranking fidelity 与端到端 search regret。

因此贡献必须来自：开放程序的 observation mismatch、safe abstention、same-code 因果干预，以及真实
search benefit；不能来自 AST wrapper 本身。

## Pilot 决策与 kill conditions

因没有 4/5 scoop 或 3/5 单篇 close paper，允许进入 train-only 小规模证伪 pilot。以下任一触发即关闭或
根本重写 SPT：

1. tap-eligible execution 的语义保持率低于 95%；
2. 6 张冻结 train-only card 中少于 4 张能在 120 秒前产生 schema-valid、finite-score probe；
3. 相对最终 valid artifact 的 median feedback-time gain 低于 25%；
4. 后续有足够 power 的实验中，probe sibling top-1 不优于 random；
5. 必须引入 task-specific patch，而不能使用冻结、label-blind adapter。

首个 pilot 不能支持论文主张；它只决定是否值得进行 powered experiment。
