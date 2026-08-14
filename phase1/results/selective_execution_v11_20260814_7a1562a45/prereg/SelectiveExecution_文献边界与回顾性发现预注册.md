# Disagreement-triggered selective execution：文献边界与回顾性发现预注册

日期：2026-08-14。协议：`selective_execution_v11_retrospective_discovery_v1`。

## 0. 证据等级先说清楚

本协议冻结时，`heterogeneous_oof_v11_discovery_v1` 的**全覆盖**结果已经看过：`char_tfidf_lr`
在 4,263 个 run-OOF pairs 上只有弱信号，原 frozen/ensemble gates 均未通过。我们尚未计算下述
selective-risk、committee agreement 或 cost--regret 结果，但它仍是同一 v11 outcome 的二次分析，故只能称
**retrospective registered discovery**，不能称独立确认。即使通过，也只授权在尚未解封的 prospective
cohort 上预先冻结一个 policy；不得读取 `decision_frozen_v11_b*` 或 first-960 outcome 来追认。

## 1. 问题与候选策略

对恰好两个、且两者最终都已执行的真实 sibling，完整策略要执行两个候选。拟议策略只在三个异构、执行前
OOF critic 一致且置信度最高的少数 decision 上执行共同预测的 winner；其余仍执行两个。若任务 `t` 有
`N_t` 个合格 parent，则最多接受 `floor(0.20 N_t)` 个。候选执行数因此从 `2N` 降为 `2N-A`，按候选数计
的节省率为 `A/(2N)`；不把候选数节省冒充实测 GPU·时节省。

三个固定 vote 为：

1. `char_tfidf_lr`；
2. `static_lr`；
3. `fixed_frozen_global`（frozen Qwen2.5-0.5B@8192 表示上的既有 OOF head）。

三者在 canonical endpoint ID 顺序上的非 tie 方向完全一致，才进入 committee-eligible pool。每个 arm 的
置信度为 `abs(score_hi-score_lo)`；先在其 outer fold 的全部 exact-two parents 内换成 mid-rank percentile，
committee 置信度取三者 percentile 的最小值。每 task 取最高的 `floor(0.20 N_t)` 个 eligible parents；
不足则全部取，绝不从 disagreement 中补样本。数值同分时用
`SHA256(protocol | arm | parent)` 排序，禁止 Python salted `hash()`。

这个 policy 是**批量预算分配**：同一 task 的一批搜索 decision 同时可见，再分配执行名额。它不是单 parent
在线阈值，也没有 conformal 风险保证。若 discovery 通过，未来 prospective 版本必须只用 v11 train
confidence 分布冻结 task-conditional threshold，不能在 first-960 上按 coverage 调阈值。

## 2. 文献边界与 scoop 裁决

这不是一个可单独声称新颖的方法原语：

- [FOREAGENT / Predict Before Execute](https://arxiv.org/abs/2601.05930) 已经在 MLE 解上做执行前
  preference，并把 Predict-then-Verify 接入 agent，报告 6× 收敛加速与 +6% agent-level 收益；
- [CIPHER](https://arxiv.org/abs/2607.14386) 已在 data-science agents 中显式分离候选生成与选择；
- [AgentSwift](https://arxiv.org/abs/2506.06017) 已用 value predictor 与 uncertainty-guided MCTS
  减少 agent evaluation；
- [When to Answer and When to Defer](https://arxiv.org/abs/2605.19369)、
  [NeuroSym-Cal](https://aclanthology.org/2026.findings-acl.305/) 与
  [CORA](https://arxiv.org/abs/2604.09155) 已覆盖 code selective prediction、risk--coverage 与
  selective action execution；
- NAS 中 [Laube et al. (AutoML 2022)](https://proceedings.mlr.press/v188/laube22a.html) 已研究 predictor
  指导选择及只验证被选 architecture 的成本收益。

因此允许的贡献边界只有组合证据：physical-run-clean 的真实 MLE sibling decisions、exact decision cost、
task/run-clustered risk--coverage、gap regret、与现有全局 pair benchmark 的分布落差，再加一次真正前瞻
确认。若只得到同一 OOF 上漂亮的 abstention 曲线，它是 benchmark baseline/诊断，不是论文 novelty。

## 3. 冻结输入与结构支持

- 输入：`phase1/results/heterogeneous_oof_v11_20260814/oof_predictions.csv`；
- SHA-256：`fc57c03a1c96ce7be19a4db764a539082258fe4c69a2ec8653b41ff85626cb45`；
- 全池固定为 4,263 rows / 333 runs / 23 tasks / 2,293 parents；
- exact-two pool 由 `parent` 恰出现一次定义，标签无关结构预检为 1,520 parents / 294 runs / 23 tasks；
- dominant task 为 336/1,520=`0.22105263157894736`；fold counts 固定为
  `[285,215,222,373,425]`；
- task-stratified 20% quota 上限合计 295，因此候选数最大节省为
  295/(2×1,520)=`0.09703947368421052`。

程序不得接受另一 pair 文件，不得打开 frozen/test/held/first-960、cards、stdout、runtime、self-report 或
external score 文件。只从 CSV 的 endpoint IDs、task/run/parent/fold、各 arm endpoint score 和 `gap_raw`
重算结果；现成 `*_hit` 只允许做 mismatch audit，不能作为预测输入。

## 4. 固定 comparators 与 controls

Primary policy：`tri_unanimous_q20`。

同 task 精确匹配 primary 实际接受数 `A_t` 的固定对照：

1. `char_margin_matched`：全 task pool 按 fold-normalized char margin 排序，取 `A_t`；
2. `unanimous_crc_matched`：只在 unanimous pool 内按 SHA256 排序，取 `A_t`，隔离“margin 是否比
   outcome-independent subset 更富集正确项”；
3. `char_crc_matched`：全 task pool 内按 SHA256 排序、由 char 预测；
4. `random_on_primary`：primary 选中的同一 rows 上用 SHA256 bit 选 endpoint；
5. `oracle_all` 与 `random_all` 只作实现正/负 control。

另固定报告 `q∈{0.05,0.10,0.20,0.40,0.60,0.80,1.00}` 的 char 与 unanimous descriptive
risk--coverage curve；只有 q=0.20 参与裁决，不得从曲线上改 headline operating point。

## 5. 指标、推断与成本契约

Primary estimand 是 selected parents 上 23-task 等权 accuracy；secondary 为 pair-micro 与 physical-run
等权 accuracy。三者都报 10,000 次 percentile bootstrap，task bootstrap seed=`20260814`，run bootstrap
seed=`20260815`。matched policy 差值先在每 task 内求 accuracy difference，再 task bootstrap；不同
selected rows 不伪装成逐 pair matched test。

同时报告：selected parents/runs/tasks、dominant share、coverage、执行候选数与候选数节省；selected
gap-weighted accuracy；每 task 的
`sum(selected_wrong_gap)/sum(all_exact_two_gap)` 后再 task-macro 的 total-gap-loss ratio。`gap_raw`
只用于 outcome metric，不参与选择。所有 task 指标、leave-one-task-out 范围和逐 task 支持均完整输出，
禁止只报 pooled 数。

## 6. outcome 前冻结的裁决门

所有下列条件同时成立才输出 `SELECTIVE_EXECUTION_DISCOVERY_UNLOCK`：

1. 所有 integrity controls 通过：input hash/row structure/fold consistency/finite scores exact；oracle accuracy
   =1、oracle gap loss=0、random-all micro accuracy∈[0.47,0.53]；
2. primary selected ≥228（coverage≥15%）、≥100 runs、≥20 tasks、dominant selected task≤25%，候选数
   节省率≥7.5%；
3. primary pair-micro、run-macro、task-macro accuracy 均≥0.58，且 run/task bootstrap 95% CI 下界都
   严格>0.50；
4. primary 对 `char_margin_matched` 的 task-macro accuracy delta≥0.02，task-bootstrap 95% CI 下界
   严格>0；
5. selected gap-weighted accuracy≥0.60，task-macro total-gap-loss ratio≤0.08；
6. producer 与不 import producer 的 verifier 对所有 central numbers、selected parent IDs、gates 和 verdict
   完全一致，且 `frozen_or_first960_read=false`。

`unanimous_crc_matched` 的 delta 单独裁决 `MARGIN_ENRICHMENT_SUPPORTED`：point≥0.02 且 task-CI
下界>0。它不是主 unlock 的必要条件；若主门过而本门不过，只能把机制写成 disagreement abstention，不能
声称 margin ranking 有额外作用。

任一主门失败即 `SELECTIVE_EXECUTION_DISCOVERY_NO_UNLOCK`。禁止改 q、删 task、放宽 support、换 vote
集合或从 descriptive curve 挑点救活；可报告失败发生在哪个门，但不能把它写成“selective execution 普遍
无效”。

## 7. 允许的下一步

通过仍不触碰 first-960 outcome。只允许把同一 policy、阈值生成规则、cost/regret estimand 和停止门写入
prospective scorer sidecar，在生产关闭后一次性确认。没有 prospective fixed-budget utility 时，论文仍以
run-clean dataset/benchmark 与分布诊断为主，不把本实验升格为独立方法论文。
