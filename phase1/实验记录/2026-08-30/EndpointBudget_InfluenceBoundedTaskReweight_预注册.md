# Endpoint Budget：Influence-Bounded Task Reweight 预注册

日期：2026-08-30

## 裁决

本实验只在已经反复用于开发的 historical fold0 上回答一个机制问题：旧 `yield_guarded_breadth` 选样留下的全部训练 pair 能否
通过任务密度校正，在不丢信息的前提下改善 critic。它不是新 cohort confirmation，不会改写 distribution-matched selection
的正式失败分类。

机器协议：`phase1/endpoint_budget_influence_bounded_task_reweight_v1.json`。冻结状态是
`FROZEN_AFTER_STRUCTURAL_WEIGHT_DIAGNOSTICS_BEFORE_ANY_REWEIGHTED_MODEL_FIT_OR_PREDICTION`。

## 冻结前已知

- 旧 yield 对 uniform 的 pooled accuracy delta 在 budget 96/192 为
  `+0.021739130434782608/+0.036231884057971016`，但 task-macro 为
  `-0.0382983682983683/-0.10402097902097902`。
- distribution-matched selection 在两个预算相对旧 yield 的 pooled accuracy delta 为
  `-0.050724637681159424/-0.07971014492753623`，且正式不晋级。
- 直接 density ratio 的结构权重在 budget96 只有 `0.4291236656381884` ESS fraction，最大单 pair 份额为
  `0.12987012987012989`，不安全。
- 结果前提出的平方根 ratio 在 budget96 的 ESS fraction 为 `0.7850387062365991`，但最大单 pair 份额仍为
  `0.05810467312403285 > 1/20`；它在任何 model fit 前终止。
- 当前规则的任何 `lambda`、新 prediction、accuracy、loss、Brier、task sign 或 bootstrap 尚未计算。

## 唯一处理

对每个 budget 和每个 yield-induced train pair (i)：

1. (a_t) 是该任务在全部 outer-train pairs 中的可用数；(s_t) 是该任务在当前 yield-induced pairs 中的数；
2. (r_i=(a_t/s_t))，并在当前 induced pairs 上归一为均值 1；
3. (w_i(\lambda)=1+\lambda(r_i-1))；
4. 在 `[0,1]` 内闭式取最大 `lambda`，同时满足 Kish ESS/原 pair 数至少 `7/10`、最大单 pair weight/总 weight 至多
   `1/20`；
5. pair 的正向与 antisymmetric 反向训练行使用完全相同的 `w_i`。

这不是权重网格。没有 clipping 候选、温度候选、结果后预算选择或任务删除。结构 gate 还要求所选任务覆盖至少 `19/20` 的
outer-train availability，且 weighted task-distribution L1 在两个预算都严格低于 unweighted L1；否则不拟合模型。

## 固定比较

- endpoint budgets：`96/192`；旧 yield selections 和 induced pair sets 原样使用；
- 模型：与旧 smoke 相同的 char-wb TF-IDF 3--5 gram、30k features、`min_df=3`、`sublinear_tf=true`；
- pair representation：better-worse 与严格反向；
- LR：`C=0.5, lbfgs, max_iter=1500, random_state=0`；
- eval：同一 138 条 held-physical-run fold0 historical pairs；
- 旧 yield/uniform predictions：只重用已绑定 mode-0600 witness，不重训 baseline；
- inference：2,000 次 task-clustered pair-micro、run-clustered pair-micro、task-macro bootstrap，seed=`20260830`。

## 七门

1. 两个预算的 ESS、单 pair influence 与 availability-support 结构门全过；
2. 两个预算的 weighted task L1 都严格下降；
3. 两个预算 task-macro accuracy delta（new-old yield）都严格为正；
4. terminal pooled accuracy（new-old yield）不退化；
5. terminal log-loss 与 Brier（new-old yield）都不退化；
6. terminal 对 uniform 的 pooled、task-macro、drop-dominant accuracy 都不退化；
7. 两个预算内，改善 task 数不少于变差 task 数。

全过也只分类为 historical single-fold promising，并要求 rule-frozen 新 physical runs confirmation；任一失败即停止，不在 fold0 上
修改公式。两个预算无论好坏全部报告。

## 资源与安全

- 两个 CPU critic fits；预计 20--45 分钟；原子 mode-0600 checkpoint/resume；
- GPU、付费 API、agent/base-model update：`0/0/0`；
- source formal、firewall、旧 selection/prediction witness、safe cards 与 security receipt 全部逐 SHA 绑定；
- 13 项 preflight、focused/full `phase1/tests`、strace network/forbidden-path、commit/blob credential scan；
- 独立 verifier 不 import producer、0 refit，重建 task weights、pair metrics、bootstrap、七门与分类，并做 A/B 逐字节复现。
