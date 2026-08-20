# I-MCTS / ML-Tool-Bench / CUARewardBench：防 scoop 补充
baseline completeness，不因这一轮检索增加 arm 或启动新 GPU/API 实验。
baseline completeness，不因这一轮检索增加 arm 或启动新 GPU/API 实验。
日期：2026-08-20。口径：只核查一手论文页；不读取 v11 frozen、0812 label vault、prospective outcome 或
WL support margins。

## 新增直接边界

### I-MCTS

[I-MCTS](https://arxiv.org/abs/2502.14693) 是 EACL 2026 Findings 工作。它在 agentic AutoML 的 MCTS 中让
生成器显式分析 parent/sibling solutions and results，并在完整 computational rollout 前用 LLM-based value
model 直接评分节点；hybrid reward 再从估计值过渡到真实 performance score。最新 arXiv v5 摘要报告相对强开源
AutoML agents 的 4% absolute improvement。

因此“首次在 MLE/AutoML 树搜索中执行前预测节点价值”“首次把预测 reward 与真实执行 reward 混合”均不可申新。
I-MCTS 摘要没有提供我方所需的 physical-run-clean sibling predictor benchmark、连续 hidden-score gap/noise
分层、query/init/execution 成本或 outcome-blind prospective confirmation；这些仍是不同的评测贡献。

### ML-Tool-Bench

[ML-Tool-Bench](https://arxiv.org/abs/2512.00672) 在 15 个 Kaggle tabular challenges 上组织 61 个专用工具与
in-memory named objects，直接评估 ML agents 的复杂规划。论文报告 ReAct 的 tool sequence validity 困难，也报告
tree search + LLM evaluation 因 state scoring 不一致而表现不佳；其 shaped deterministic reward 与 task
decomposition 相对 ReAct 的 median 提升为 16.52 percentile positions。

因此“首次发现 ML-agent tree evaluator 不稳定”“首次建立 ML-agent planning benchmark”均不可申新。其公开摘要
描述的决策单位是结构化 tool state/action，而不是自由形态完整 Python solution 的实际同-parent sibling choice
set；我方可比较的是这种结构化工具空间结论能否迁移到真实 MLE program-search 节点，而不是重复宽结论。

### CUARewardBench

[CUARewardBench](https://arxiv.org/abs/2510.18596) 已系统评估 computer-using agents 的 ORM/PRM：10 个软件类别、
7 种 agent architectures、7 个 VLM 与 3 种 prompts，并同时覆盖 trajectory-level 和 step-level 评价；其
unanimous prompt ensemble 还给出正面 precision/NPV 结果。

因此“首个 agent reward-model benchmark”“首次同时评估 process/outcome reward”不可申新。它是 GUI/CUA
轨迹与专家标注体系，不是 MLE 连续 external grader 下的 sibling 排序；但它说明我们的 benchmark 必须和成熟
RM benchmark 一样报告模型家族、prompt/coverage、统计单位与错误模式，不能只发布一张 pair accuracy 表。

## 对当前正面主张的裁决

三篇工作进一步关闭宽方法 novelty，但没有找到与以下组合等价的直接资源：真实 MLE agent physical run 中的完整
Python sibling choice set；同 budget/run/task 的无交集切分；连续 hidden external score 的 gap 与 repeatability；
query/init/execution 分账；以及 activation 后新 runs 的 outcome-blind prediction escrow。这个“没有找到”不是
无人做过的证明，论文仍不得使用 first/only；允许做的是逐项可核对差异。

因此最稳的正面叙事仍是 Decision-Corpus benchmark + Audit Protocol + prospective confirmation。I-MCTS、
ML-Tool-Bench、CUARewardBench 与 Guided Evolution 应进入强相关基线/related-work 表；WL graph extension 仍只作
baseline completeness，不因这一轮检索增加 arm 或启动新 GPU/API 实验。
