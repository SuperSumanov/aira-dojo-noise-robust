# CPRD / pair distribution：防 scoop 与主张二次收紧

日期：2026-08-21。作用域：一手文献核查和主张边界修订；未读取 prospective outcome，GPU=0，API=0，
base-LLM update=0。本记录不改变 first-960、WL extension、closure 或揭盲条件。

## 1. 直接先例

1. [What Does Preference Learning Recover from Pairwise Comparison Data?](https://arxiv.org/abs/2602.10286)
   （ICML 2026，v3 更新于 2026-08-10）从 triplet distribution 定义 CPRD 和 comparison distribution；给出
   BT representability/KL projection，并证明 margin 与 comparison connectivity 控制有限样本学习。
2. [Reward Learning from Best-of-N Preference Data](https://arxiv.org/abs/2605.30619) 把上述框架专门化到
   Best-of-N，证明 candidate-set size 同时改变 margin 与 connectivity，并明确用任意 target test distribution
   定义训练分布相对测试分布的 connectivity；base distribution 应覆盖测试时真正关心的比较。
3. [RewardBench 2](https://arxiv.org/abs/2506.01937) 已把 RM benchmark accuracy 与 113 个 RM 的下游 BoN
   联系起来，并显示 PPO 还依赖 policy/RM lineage 和 prompt distribution；一般 benchmark-to-deployment 讨论已有。
4. [Reward Model Underspecification in Language Model Alignment](https://openreview.net/forum?id=ecufIfDNn0) 已说明
   即使简单 BoN reranking 也会诱导 RM 更易分歧的分布，进一步关闭泛化的“首次发现 offline RM 分布漂移”主张。

## 2. 必须撤回/禁止的表述

- “首次指出 pair construction 决定 reward model 学到什么”；
- “首次把 comparison graph、margin 或 connectivity 与 preference learning 联系”；
- “首次证明通用 RM benchmark accuracy 不能直接代表部署”；
- 把既有 PairGraphIntervention 的描述性排序变化写成新的理论或确认性 universal effect。

`benchmark construction determines the deployment estimand` 仍可作论文叙事句，但必须紧邻 CPRD/BoN 理论引用，
并明确我方贡献是 MLE 领域的 measurement/resource instantiation。

## 3. 仍可守的正向差异

一般理论没有替代以下联合资产：

1. 比较来自 MLE-agent physical run 内自然发生的同-parent labeled sibling fragment，而非合成 BoN 正负样本；
2. 有 pristine evaluator 的连续 execution score，可同时观察 preference、真实 gap 和复测噪声；
3. 显式发布 source opportunity/missing registry，避免把 execution failure 后的 complete-case fragment 冒充原 choice set；
4. physical-run-clean split、endpoint reuse 和 pair graph 都有机器可验证收据；
5. predictor init/query cost 与 candidate execution cost在同一资源中核算；
6. frozen scorer 的 first-960 prediction 在 outcome 前托管，并要求独立 accrual closure 后一次性确认。

因此最稳的 D&B 定位是：**CPRD 理论在真实 MLE program-search 决策中的可审计数据实例、压力测试与时间外确认**。
这不是算法首创，但比只发布又一个 RM accuracy 表更完整，也让负/正模型结果都能回答一个已被理论明确化、但尚未在
MLE sibling execution 数据上系统测量的问题。

## 4. 对下一步的约束

- 不新增 rank loss、connectivity regularizer 或第五个 WL arm；这些都需要新的 train-only 资格门和未来 cohort。
- 现有 gap-stratification 对应 margin；PairGraphIntervention/endpoint reuse 对应 comparison connectivity；不得改名
  后重复做同一实验。
- first-960 主结果应把 natural sibling comparison distribution 与 global/FOREAGENT pair distribution 分栏，不能
  把两者 accuracy 当同一总体直接排榜。
- PairGraphIntervention 的 universal-inflation 门已失败；可报告 3,921 common-support rows 上的描述性 decomposition
  和 model-ranking interaction，但 CI 跨零必须同表出现。
- 真正新的强证据仍来自 activation 后 strict cohort 的冻结 predictor transport，而不是结果后扩分析自由度。
