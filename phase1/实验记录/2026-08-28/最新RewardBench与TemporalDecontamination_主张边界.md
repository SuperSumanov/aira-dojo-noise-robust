# 最新 reward benchmark 与 temporal decontamination：主张边界

日期：2026-08-28

## 直接相关先例

1. [AgentRewardBench（arXiv:2504.08942）](https://arxiv.org/abs/2504.08942) 已把 1,302 条 web-agent
   trajectories、5 个 benchmarks、4 个生成模型和专家标注组织成自动 evaluator benchmark，并比较 12 个 LLM
   judges。因而“首个 agent evaluator benchmark”不能主张。
2. [Plan-RewardBench（arXiv:2604.08178）](https://arxiv.org/abs/2604.08178) 已直接研究 trajectory-level
   preference/reward modeling，含多模型自然 rollout、规则扰动与 minimal-edit hard negatives，并报告长轨迹上的明显
   退化。因而“首个 trajectory reward-model benchmark”也不能主张。
3. [LiveCodeBench（arXiv:2403.07974）](https://arxiv.org/abs/2403.07974) 已用持续收集的新竞赛题构造
   contamination-free、随时间更新的 code benchmark。因而“首次使用时间前瞻收集避免污染”不能主张。
4. [How the Misuse of a Dataset Harmed Semantic Clone Detection（arXiv:2505.04311）](https://arxiv.org/abs/2505.04311)
   指出把 BigCloneBench 的弱 Type-3/Type-4 标签当 semantic ground truth 会产生严重误导；其人工样本中 93% 被判为
   不具相似功能。该结果直接支持我方继续把 token/Jaccard 审计限定为 syntactic Type-2/partial Type-3 sensitivity，
   不把零链接写成 semantic clone absence。
5. [BigCodeArena / BigCodeReward（arXiv:2510.08697）](https://arxiv.org/abs/2510.08697) 已从 14K+ 真实
   code-centric 会话中整理 4.7K+ 多轮人类偏好，并比较 reward model 在有/无执行结果时的一致性。因此“首个真实代码
   偏好或 practical-code reward benchmark”不能主张。它的对象是多轮会话终答与人类偏好，不是 MLE 搜索树中同一
   parent 下完整候选程序的 pristine 连续外部分数。
6. [Themis-CodeRewardBench（arXiv:2605.00754）](https://arxiv.org/abs/2605.00754) 已覆盖 8 种语言、5 个质量
   维度、约 8.9K 偏好对并系统评价 50+ reward models；其 600M→32B 模型还报告了代码 RM 的正 scaling。因此“首个
   code-specific RM benchmark”“首次发现 code-RM scaling”均不能主张。我们的潜在 scaling 价值只能来自真实
   MLE-agent search distribution、连续 evaluator truth 和严格 temporal/run/config transport，而不是规模趋势本身。
7. [Similar / SRM（arXiv:2503.18665）](https://arxiv.org/abs/2503.18665) 已用 MCTS-P 收集 step-wise、
   multi-dimensional virtual-agent 数据，并把 reward model 用于训练和 inference-time action choice；
   [SWE-TRACE（arXiv:2604.14820）](https://arxiv.org/abs/2604.14820) 又把 rubric PRM 用于长程 SWE agent 的
   动态候选剪枝。因此“首个 agent step-wise RM benchmark”或“首次用 PRM/critic 加速代码 agent 搜索”均已关闭。
8. [CodeScaler（arXiv:2602.17684）](https://arxiv.org/abs/2602.17684) 已将 execution-free code reward model
   用于训练和 test-time selection，并报告约 10 倍推理延迟下降。因此“廉价、无需执行的 code critic”也不是方法
   novelty；我方 query/init/execution 三账本的价值在于统一测量真实 MLE workload，而非提出这一概念。
9. [ML-Agent（arXiv:2505.23723v2）](https://arxiv.org/html/2505.23723v2) 已收集 9 个 MLE tasks、10,000
   条最长 15 步/30 分钟的执行轨迹，做 Qwen2.5-7B SFT 与 step-wise PPO，并显式给出 agentic-ML reward 和成本
   分摊。因此“大规模 execution-grounded MLE trajectory”“MLE step-wise learning/cost”均不是我方首创。
10. [Frontis-MA1 / OpenMLE（arXiv:2607.28568）](https://arxiv.org/abs/2607.28568) 已把四类程序演化 operator
    的 execution-grounded SFT/RL 与长程 evolution search 接通；其官方
    [SFT traces](https://huggingface.co/datasets/FrontisAI/OpenMLE-SFT-Traces) 有 26,259 条公开轨迹、4,891 个
    task names。因此我方不能用训练轨迹规模、operator learning 或 agent 自改进作主 novelty。
11. [MLE Trajectory Dataset v1](https://huggingface.co/datasets/jerryyan/mle-traj-v1) 已发布 15,572 个
    human/agent 逐版本代码节点、逐节点 held-out score 与 state/action/intent 标签；
    [v3](https://huggingface.co/datasets/jerryyan/mle-traj-v3) 又将 13,692 个人类版本以 version/fork/code-sim
    边构成 forest。因此“首个 MLE trajectory/graph dataset”“首个逐版本 score+code+标签”均已关闭。其 agent
    MLEvolve 数据仅来自 13 个 physical runs 并线性化为 189 branches；我方可守差异是保留真实 search parent 与
    sibling choice fragments，并以此做独立 predictor benchmark 和 outcome-blind temporal audit。

## 当前仍可守的差异化组合

当前可守的不是某一个通用首创，而是以下要素在 MLE-agent 完整程序搜索分布上的组合：

- 真实同 parent sibling decision fragments，而非人工扰动的正负 trajectory；
- 候选是可执行的完整 Python ML solutions，truth 是 pristine external evaluator 给出的连续分数；
- physical-run / parent / task / comparison-component / exact-config 多层隔离；
- predictor 初始化、单次 query 与完整执行成本分账；
- gap、regrade noise ceiling、missingness、endpoint degree 与 pair-weighting audit；
- append-only、outcome-blind、time-forward cohort 与独立 closure receipt；
- train→future 以及 future 内部 clone/overlap 证书与逐哈希撤回链。

在完成更系统的检索前，不把上述组合写成“first”。更稳妥的写法是：现有 evaluator benchmarks 主要评价完整
trajectory 的成功/偏好判断；我方 benchmark 的 deployment estimand 是在真实 MLE 搜索节点上、执行前比较同一
decision point 的完整候选程序，并把 pair construction 与有效 benchmark 权重本身作为受审计对象。

新增文献进一步收紧后，最可守的差异不应写成“MLE trajectory dataset”“代码 RM”“agent RM”“execution-free
critic”或“search pruning”本身；
应写成：**对自然产生的 MLE-agent search distribution 做可重建、run-clean、time-forward 的 decision-level
measurement study，并公开 pair graph、隐式权重、执行成本和审计撤回链。** 当前检索未发现同时满足“完整 MLE
solution、真实 sibling choice、连续 pristine external grade、physical-run/config 隔离、outcome-blind temporal
closure、成本/噪声/权重联合账本”的公开 benchmark；这只是基于当前检索的差异化判断，不是形式化的不存在证明。

## 对本轮 full-release overlap 的定位

完整 v11 release→future overlap 证书若通过，是 temporal-release hygiene 与 benchmark-integrity 的正资产；它提高
数据集可信度，但不是 evaluator 方法创新，也不能替代 prospective predictor effect。即使 primary links=0，论文中也
只能写“在固定 identifier/literal-erased 5-token shingle 表示和阈值下未发现链接”，不得写成语义去污染或未知
pretraining corpus 去污染。
