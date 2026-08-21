# M-DESIGN 修改增益图：防 scoop 与当前正面边界

日期：2026-08-21。状态：`EDIT_GAIN_METHOD_NOVELTY_CLOSED_DATASET_BOUNDARY_RETAINED`。
本记录只做一手文献核查与主张收紧；没有读取 prospective outcome、没有训练模型，GPU/API/base-LLM
update 均为 0，也不改变 first-960、closure 或 transition future escrow 的统计门。

## 1. 直接先例

[M-DESIGN / Beyond Model Base Retrieval](https://arxiv.org/abs/2507.15336) 已被 ICML 2026 接收。它在 22 个
图数据集、67,760 个 GNN 模型上构造 architecture modification-gain graph：节点是候选架构，边是一跳细粒度
架构修改，边标签是性能增益。其方法进一步用历史 edit-effect evidence、动态任务相似度和 predictive task
planner 选择后续修改，并报告在 33 个 task--setting 中 26 个达到给定设计空间最优。官方实现与知识库也已发布：
[M-DESIGN GitHub](https://github.com/jilwang84/M-DESIGN)。

这是一项比泛泛 NAS predictor 更直接的先例。它明确覆盖了：

1. 把候选模型历史组织成“修改--增益图”；
2. 学习/检索一跳 edit effect；
3. 跨任务复用修改收益并在线校准 task similarity；
4. 用预测的多跳 gain 指导有限预算搜索。

## 2. 必须关闭的主张

- 不得声称首次提出 modification-gain graph、edit-effect predictor 或用父子改动收益指导模型搜索；
- 不得把当前 68 维 parent-relative transition arm 包装成新的 NAS/AutoML 方法；
- 不得仅凭“我们的候选是代码而不是 architecture tuple”主张算法首创；
- 不得在已见的 5,240-pair retrospective 数据上改 transition feature、检索器或 task weighting 追救。

`TreeTransitionStatic` 的正式 `NO_ROBUST_TRANSITION_GAIN_VERIFIED` 不变；已经锁定的 strict-future scorer
仍可作为 benchmark extension 一次性验证，但即使未来为正，也只能说明该类已知 edit-effect 思路能否迁移到
自然 MLE-agent 决策，不是方法首创。

## 3. 仍然可守且更清楚的正面差异

M-DESIGN 的候选来自固定、结构化的 GNN architecture design space，模型库可重复查询完整候选性能；我方资源的
测量对象不同：

1. 候选是 LLM agent 在开放式 Python workspace 中产生的自由代码修改，而不是有限 architecture tuple；
2. 比较单位来自同一 physical run、同一 parent 下自然发生的 sibling fragment，不是预先枚举的双向架构邻边；
3. 标签来自外部 pristine execution evaluator，并保留 true-score gap 与独立 regrade noise；
4. source opportunity、execution failure、retention 与 unknown missingness 显式入库，不把 complete-case fragment
   冒充完整搜索空间；
5. physical-run/exact-config/component closure、endpoint reuse、pair graph 与父上下文复用都有机器可验证审计；
6. predictor initialization/query cost 与一次候选执行成本同表核算；
7. 冻结 prediction 在 outcome 前托管，并要求 activation 后 strict-future cohort 与独立 closure 同时过门。

所以最稳的表述不是“新修改增益算法”，而是：**把已在受控 AutoML 空间成立的 edit-effect/predictor 问题，
迁移到开放式 MLE-agent 自然搜索轨迹后，建立第一个可审计的领域测量实例之一，并检验其在真实 sibling deployment
distribution 上是否仍成立。** 正文仍避免 first/only；以逐项 comparison table 和 release contract 支撑差异。

## 4. 对下一步的约束

- transition future escrow 的 arm、哈希、门槛和 stopping rule 不变，不因该论文增删 arm；
- M-DESIGN 进入 related-work 与 benchmark comparison table，定位为 controlled-space edit-gain upper precedent；
- 当前最值得做的效果实验仍是 clean direct-decision Qwen scaling，以及已经结果盲锁定的 strict-future
  transition transport；二者回答“数据可学/容量是否重要”和“历史 edit signal 能否时间外迁移”，都不申新 loss；
- 若未来要实现 M-DESIGN-style retrieval，只能作为明确标注的已知方法 comparator，使用新的 train/dev 与新的
  未触碰 future cohort；不得回填当前 retrospective test，也不得覆盖 frozen primary。
