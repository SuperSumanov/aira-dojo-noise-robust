# Pair graph：文献边界与正方法候选

日期：2026-08-14。本文晚于 `PairGraphIntervention_裁决.md`，但不改变其中已经冻结的
`VERIFIED_PAIRGRAPH_EFFECT_NOT_SUPPORTED` 裁决。当前稳定主线仍是 run-clean、decision-local 的
MLE-agent 搜索树数据集/benchmark；旧 HCE、多保真、TD/RL 和 probe 均不恢复为主线。

## 1. 已被既有工作覆盖的命题

下面这些一般性命题不能再写成本文首创：

1. **偏好对的生成分布会改变 reward model 学到的目标。** Pukdee、Balcan 与 Ravikumar 的
   [Best-of-N preference-data analysis](https://arxiv.org/abs/2605.30619) 已把 comparison distribution
   写进诱导目标，并明确讨论 margin 与 connectivity 的权衡以及让 base distribution 覆盖测试时真正重要比较的
   设计原则。
2. **换一组有争议的比较对会重排 reward-model 排名。** [PMDC](https://openreview.net/forum?id=SN7NJzrref)
   主动选择模型分歧最大的 pair，并报告相对静态 benchmark 的显著 rank reshuffling。
3. **pairwise accuracy 不是唯一的下游指标。** [RMB](https://arxiv.org/abs/2410.09893) 同时做 pairwise 与
   Best-of-N 评测；[RewardBench 2](https://arxiv.org/abs/2506.01937) 也把 reward-model benchmark 与
   inference-time scaling / RLHF 下游表现联系起来。
4. **comparison graph 的拓扑会影响学习。** feature-BTL 工作
   [A Graph Theoretic Approach for Preference Learning with Feature Information](https://openreview.net/forum?id=qb0Iuax67O)
   从样本复杂度分析特征与图结构；[DPO convergence analysis](https://openreview.net/forum?id=QdeVcEX8y2)
   的收敛界显式依赖 response comparison graph 的代数连通度和最大度。
5. **NAS predictor 使用 pairwise ranking，或主动挑 pair 训练，也已有先例。** Sun 等人的
   [NAS performance-predictor training protocol](https://arxiv.org/abs/2008.13187) 已使用 pairwise target、
   logistic regression 与 differential instances；更一般的
   [active pair sampling](https://proceedings.mlr.press/v29/Shen13.html) 也早已研究如何从大量候选 pair 中挑选
   训练子集。因此 TGCA 若有效，其新意也不能写成“首次以 pairwise/active sampling 训练 predictor”。

因此，我们不能声称“第一次发现 pair distribution / graph 会影响准确率或模型排序”，也不能把当前
outcome 后观察到的 `static_lr` 与 `char_tfidf` 排序反转包装成确认性因果结论。

## 2. 仍可防守的论文差异

当前可防守的贡献组合不是一个抽象的 preference-learning 定理，而是一个此前文献没有直接覆盖的测量对象：

- 真实 MLE agent 搜索树中的 **sibling decision graph**，候选是自由形态代码，标签来自 pristine 外部 grader；
- physical-run provenance、run-clean split、父节点/兄弟节点结构以及被剪枝后产生的 fragment 泄漏诊断；
- 在同一 endpoint scorer 上同时报告真实 sibling、task/fold-matched cross-run、gap-transport 三种 estimand，
  并使用 task/run clustered inference；
- 将 pair accuracy 与 complete-parent top-1、parent-equal grade utility、推理成本和标签噪声上界并列；
- outcome 前冻结 scorer，并在冻结之后产生的首 240 个合格 physical runs 上作前瞻确认。

论文措辞应是“把 comparison-distribution 问题落实到 MLE-agent 的真实搜索决策，并提供可前瞻复核的数据与
协议”，不是“首次提出 comparison graph”。

## 3. 一个允许继续验证的正方法：Target-Graph Connected Augmentation（TGCA）

### 3.1 假设

真实 sibling pairs 最贴近部署目标，但每个 parent/run 内形成许多小而断开的比较分量。训练集同时已有每个
endpoint 的外部标量 grade；在不新增 LLM 调用、不新增 grader 成本的前提下，可以只在 outer-train 内构造
少量跨 run、同 task、gap-matched 的桥接边。假设是：**保持目标 gap/task 分布的同时提高训练 comparison graph
连通性，能改善未见 physical runs 上真实 sibling 的 top-1/utility，而不是只抬高跨-run pair accuracy。**

这只是 MLE-agent 场景中的待验证工程假设；上述图论工作不保证 feature-based char/static scorer 一定获益。

### 3.2 一次性发现实验（不得调门）

在既有五个 outer physical-run folds 上，对每个 fold 独立构造训练集，并始终只在该 fold 未参与训练的真实
sibling parents 上评测。endpoint universe、特征、scorer、solver、seed 与既有 heterogeneous OOF 保持不变。

四臂固定为：

1. `sibling_only`：原始 sibling 训练边；
2. `sibling_reweight_control`：额外抽样与 TGCA 数量相同的原 sibling 边，作为纯样本权重/训练步数控制；
3. `uniform_crossrun_control`：额外加入同 task、不同 physical run 的均匀跨-run 边，数量相同；
4. `tgca`：额外加入同 task、不同 physical run 的桥接边，逐 task 严格匹配原 sibling 的预注册 gap bins，
   并以确定性最小度数优先规则连接当前不同分量。

固定 augmentation ratio 为 `1.0`：每条原 sibling 训练边最多对应一条新增边。禁止调 ratio、gap edges、任务、
正则、C、特征、seed 或按任务选臂。若某 task×gap bin 候选不足，只取有限总体，不跨 bin 回填，并在四臂共同
支持分析中剔除相应缺口。所有跨-run边的方向只由 outer-train endpoint 的 pristine grade 决定；grade tie 对称
排除。任何 outer-valid/frozen/future label 访问均使实验无效。

### 3.3 必报量与完整性门

- 每 fold/task：节点数、原边数、新边数、连通分量数、最大分量占比、归一化代数连通度；
- 每臂：真实 sibling pair accuracy、complete-parent top-1、parent-equal grade utility；
- TGCA 相对三个控制的 paired run/task bootstrap CI，及逐任务方向；
- train/valid physical-run、node-id、raw-code 三层零交集；所有输入/候选/选择结果 SHA-256；
- producer 与不 import producer 的独立 verifier 必须逐行复算；不打开论文 frozen set。

### 3.4 预先裁决

只有同时满足以下条件，才记为 `TGCA_DISCOVERY_UNLOCK`：

1. 相对 `sibling_only` 的 parent-equal utility 增量 `>= 0.02`，run-clustered 与 task-clustered 95% CI 下界均
   `> 0`；
2. 相对 `sibling_reweight_control` 的 utility 增量 `>= 0.015`，两种 CI 下界均 `> 0`；
3. complete-parent top-1 相对 `sibling_only` 增量 `>= 0.02`，两种 CI 下界均 `> 0`；
4. 至少 15 个支持任务，dominant-task share `<= 0.25`，至少 60% 支持任务的 utility 增量非负；
5. TGCA 的跨-run pair accuracy 上升但真实 sibling utility 不升，不算通过；任何完整性门失败均为 `INVALID`。

`uniform_crossrun_control` 用于判断“连边”是否优于无目标的跨-run扩充，不作为通过门的替代。发现门通过后也只
授权把 TGCA scorer 在前瞻 first-240 cohort 中作为**事先冻结的新增 arm**；若赶不上该 cohort 激活时间，则必须
另开后续 cohort，不能追溯打分。

## 4. 风险与停止条件

- 跨-run grade 可能让模型学到 task-level absolute shortcuts，而非 parent-local preference；因此必须同 task、
  run OOF，并以真实 sibling utility 裁决。
- 加边改变的不仅是 connectivity，也改变了训练权重；`sibling_reweight_control` 与等边数控制不可省略。
- gap-bin 匹配只能控制粗粒度 margin composition，不构成 pair graph 的因果识别。
- 如果任一主要门失败，关闭 TGCA，不换阈值、不挑任务、不在同一 OOF 上搜索第二种连接启发式。该负结果只记录
  为方法筛选，不改变 benchmark/data 主线。

## 5. 执行顺序

1. 先完成并归档 `prospective_decision_v1` 固定 scorer 的独立验证与激活；
2. 再把本节具体化为 outcome 前的机器可读协议、13 项预检和零 GPU CPU 实验；
3. 只有 `TGCA_DISCOVERY_UNLOCK` 才投入前瞻确认；否则资源回到新 physical-run 数据、provenance 与 benchmark
   发布物。
