# Agent RM 与 AutoML ranking：防 scoop 及主张收紧

日期：2026-08-21。作用域：只做一手文献核查和论文主张边界更新；未读取 prospective outcome vault，未运行
模型，GPU=0，API=0，底座模型更新=0。本记录不授权给当前 first-960 增加 arm 或 metric primary。

## 1. 新补齐的直接先例

| 工作 | 已明确覆盖 | 因而关闭的泛化主张 |
| --- | --- | --- |
| [Plan-RewardBench](https://arxiv.org/abs/2604.08178) | 复杂多工具环境中的整轨迹 preference benchmark；自然 rollout、规则扰动和最小编辑 hard negatives；统一比较 generative、discriminative RM 与 LLM judge | “首个 agent trajectory preference/RM benchmark” |
| [AgentRewardBench](https://arxiv.org/abs/2504.08942) | 1,302 条 web-agent trajectories，跨 5 benchmarks / 4 agents；专家标注 success、side effects、repetitiveness，并评测 12 个 LLM judges | “首次系统评估 agent trajectory evaluator” |
| [ExeVRM / ExeVR-53K](https://arxiv.org/abs/2603.10178) | 53k instruction–execution-video–reward triplets；训练 execution-grounded 8B RM，并做长轨迹 token pruning 与错误时刻定位 | “首次以真实执行轨迹训练大规模 reward model” |
| [The Ranking Trick](https://openreview.net/forum?id=HsQrl2og2h) | 将 AutoML pipeline score target 改为 rank target；用 NDCG/MRR 评估，并接入 Bayesian optimization 与 MCTS | “首次把 AutoML 候选选择改写成 rank/listwise 问题” |

这些工作与已有 CUARewardBench、FOREAGENT、FLORA/Agentic Predictor、Guided Evolution 一起说明：agent RM、
pairwise judge、graph predictor、rank target、selective execution 都不能作为算法名词层面的 novelty。

## 2. 没有被等价替代的窄边界

本项目不能再写“我们首次评估 agent reward model”。可以防守的是一组同时成立、逐项可验证的差异：

1. 单位是 MLE program-search **physical run** 中自然发生的同-parent sibling，而不是人为正负 trajectory、不同
   agent 的完整 rollout，或任务内全连接 pipeline pair；
2. 发布边界诚实限定为带 missing registry 的 **labeled sibling fragment**，不恢复已撤回的完整 source
   choice-set 主张；
3. 标签是 pristine evaluator 给出的连续 Kaggle performance，可显式计算 true-score gap、复测噪声与近平局；
4. train/test 按 physical run 隔离，并单列 endpoint reuse、pair graph、task concentration 与 source provenance；
5. 同时核算 predictor initialization/query cost、candidate execution cost 与选择性缺失，而不是只报 judge accuracy；
6. first-960 预测在 outcome 之前托管，且只有 960-run cohort 与独立 accrual closure 同时满足后才允许揭盲。

这仍不是“无人做过”的证明，正文不得写 first/only；应把差异做成 comparison table 和 machine-readable audit card。

## 3. 当前最强的正面概念主张

最值得完善的不是“我们训练了最强 critic”，而是：

> **Benchmark pair construction defines the deployment estimand.** 在全局/合成 preference pair 分布上测得的
> reward-model accuracy，不能未经 transport 审计就解释为 agent 在线 sibling selection 能力。

现有直接证据已经互补：FOREAGENT 官方 parquet 的 `gap<1e-2` share 为 0.096400，我方真实 sibling b0 为
0.501335；限制同名任务后差异仍在；官方 solution 组合复用中位数为 49，而我方单位绑定 physical run/parent；
此前从易的 value/all-pair 协议逐步收紧到真实 sibling/run-clean 时，headline 明显下降。这里的新意不在“排序会受
采样影响”这一统计常识，而在真实 MLE-agent 数据上把 deployment distribution、泄漏、gap/noise、成本和时间外
确认做成同一个可执行 benchmark contract。

这是一条正面 D&B 主张：即使所有 predictor 都没有巨大绝对提升，资源仍能揭示哪些公开 headline 不对应线上
决策，并给后续 critic 提供正确训练/测试单位。但最终必须依赖 first-960 + closure 的 outcome-blind confirmation，
不能用当前支持前缀提前宣称。

## 4. 对实验路线的约束

- 当前 pair primary、WL 单列 extension 与 first-960 停止规则不变；不因本次文献核查增加比较次数。
- parent-macro top-1、NDCG/MRR 或 rank correlation 可作为 secondary reporting，但不申方法 novelty。
- Ranking Trick 是值得纳入 benchmark completeness 的已知 baseline；若做，只能先在 train-only、run-disjoint
  资格门比较 score-target 与 rank-target，再于新的严格 post-activation cohort 一次性确认，不能回填当前 cohort。
- Plan-RewardBench 的 synthetic/minimal-edit hard negatives 不应被复制为本项目 primary；primary 继续保持自然
  sibling fragment，合成 pair 只能明确标作 stress test。
- 当前最有价值的近期工作仍是安全累积 first-960、冻结 closure、完成 predictor family coverage，并让学长未来
  exact-stratum critic 使用独立 train/dev/one-shot test 协议。
