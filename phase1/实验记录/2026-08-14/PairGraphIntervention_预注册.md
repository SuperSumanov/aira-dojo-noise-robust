# Pair-graph intervention：train-OOF 描述性审计预注册

日期：2026-08-14。协议名：`pairgraph_v11_train_oof_descriptive_v1`。本文写在任何新 pair-graph
反事实准确率产生之前，但不是盲确认：用于选择四个固定 arm 的 v11 train-OOF outcome 已经看过。因此本轮
只能形成 benchmark 的机制性/描述性证据；未来若要写“确认”，必须在本协议冻结之后的新 physical runs 上复现。

## 1. 问题与不变量

固定同一批 train-only OOF endpoint 分数、同一 endpoint universe、同一 task 与 outer fold 构成，只改变
pair graph，问全局跨 run 配对相对真实 sibling 决策会把 predictor accuracy 抬高多少，以及固定 gap 分布后
还剩多少差异。禁止重新训练、调参、挑任务、读取 `decision_frozen_v11_b*` 或把结果写成新 critic 的效果。

锁定输入（远端源字节 SHA-256）：

- OOF predictions：`fc57c03a1c96ce7be19a4db764a539082258fe4c69a2ec8653b41ff85626cb45`；
- train b0 pairs：`bd31b4679c7b4405703b976921df0bc63acba4fc0c4a002f4b8f36d171251fca`；
- cards v11：`6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75`；
- task orientation：`e11111a3538c54eb91048b54380466b4dc0f041c2f511a78a85573cbc92b121a`。

预期原始支持固定为 4,263 sibling pairs、333 physical runs、23 tasks、2,293 parents、5,499 endpoints。
cards loader 先从 OOF 收集 5,499 个允许 ID，再单遍只保留这些 ID 的 `task` 与 `label.graded`；不得保留
code、obs、runtime、stdout、self-report 或不在 allowlist 的 card。`frozen_read` 固定为 false。

## 2. 可比较 arms

只使用具有跨 parent 可分离 endpoint score、且已在上一协议完全冻结的四臂：

1. `fixed_frozen_global`；
2. `op_only_lr`；
3. `static_lr`；
4. `char_tfidf_lr`（headline，但明确是按已见 train outcome 选出的描述性 strongest arm）。

每个 endpoint 在同一 arm 的所有原 sibling 行中必须只有一个 OOF score（绝对误差容限 `1e-12`）。
`static_gbm` 的 pair-difference 非线性分数不可分离，`equal_rank_frozen_tfidf` 是 parent-relative rank；二者
均不得用于跨 parent 反事实。

## 3. 三个 pair graphs

所有反事实 pair 必须：同 task、同 outer fold、不同 physical run、finite 且不相等的 raw external grade。
同 fold 保证两 endpoint 由同一个 outer-fold 模型评分；跨 run 模拟全局 solution-pool pairing，并与真实
同 parent/same-run sibling graph 形成干预。

- `sibling`：原始真实 sibling pairs；
- `crossrun_uniform_transport`：在每个 `(task, fold)` 内枚举全部合格跨 run pairs，取该 cell 的有限总体
  平均准确率，再按 common-support sibling cell 计数加权；因此 task/fold 质量与 sibling 完全相同；
- `crossrun_gap_transport`：固定旧 gap 分层边界
  `[0,1e-4,3e-4,1e-3,3e-3,1e-2,3e-2,1e-1,3e-1,∞)`，在每个
  `(task, fold, gap_bin)` 内取跨 run pair 的有限总体平均准确率，再按 sibling stratum 计数加权；因此
  task/fold/gap-bin 分布与 sibling 完全相同。

每个用于 gap transport 的 stratum 至少要有 5 个合格跨 run candidates；否则该 stratum 及对应 sibling
行从三个 graph 的共同支持中同时排除。共同支持必须覆盖至少 80% 原 sibling rows、至少 15 tasks，且 dominant
task 不超过 30%；否则状态为 `INSUFFICIENT_COMMON_SUPPORT`，不解释 predictor accuracy。禁止 outcome 后合并
gap bins 或降低这些门。

raw grade 方向严格读 `task_orientation.json`；gap 定义为 `round(abs(g1-g2), 6)`，恰落边界进入右侧 bin。
预测分数相等计 0.5。所有候选是有限总体全枚举，不做随机 pair 抽样；seed 只用于 task bootstrap。

## 4. 指标与推断

每 arm、每 graph 报：common-support rows/weighted rows、micro accuracy、task-macro accuracy、每任务准确率、
hard share (`gap<1e-2`) 与 gap-bin 权重。主推断使用 10,000 次 task-clustered paired bootstrap，seed=9887，
报告 task-macro 三个差：

1. `total_pairing_inflation = uniform - sibling`；
2. `gap_composition_component = uniform - gap_transport`；
3. `topology_residual = gap_transport - sibling`。

这是有限样本描述分解，不宣称因果 mediation；固定 bins 内仍可能有 residual gap 差异，必须逐 stratum
报告 candidate/sibling 数与均值 gap，禁止把 residual 全归因于 lineage。

## 5. outcome 前解释门

所有门都先要求输入 SHA、pair/OOF 逐行一致、endpoint score consistency、grade orientation/gap、共同支持、
finite、不同 run、同 task/fold、coverage 与独立 verifier 全部通过。

- `PAIRGRAPH_INFLATION_SUPPORTED`：headline char-TFIDF 的 task-macro total inflation `>=0.05` 且 task-bootstrap
  CI 下界 `>0`；四臂至少 3 臂 total inflation `>0`，且至少 2 臂 CI 下界 `>0`。
- `GAP_COMPOSITION_SUPPORTED`：在上一门通过基础上，char-TFIDF gap component `>=0.03`、CI 下界 `>0`，
  且占正 total inflation 的比例 `>=0.50`。
- `TOPOLOGY_RESIDUAL_SUPPORTED`：char-TFIDF residual `>=0.03` 且 CI 下界 `>0`；只能称“固定粗 gap bins
  后仍有 pair-graph residual”，不得称纯 lineage 因果效应。
- 若完整性通过但第一门失败：`PAIRGRAPH_EFFECT_NOT_SUPPORTED`。完整性失败一律 `INVALID`。

无论哪个门通过，都不授权打开 frozen、不授权新模型或 prospective search 效果主张。正面价值只在于把
“critic 本身有多强”与“benchmark 的 pair graph 有多容易”分开，并为数据论文给出可复现的 decision-local
评测协议。

## 6. 资源与验证

单 CPU 进程，0 GPU、0 API；全枚举墙钟 cap 10 分钟，预期 1--4 分钟。输出 `summary.json`、
`stratum_stats.csv`、`per_task.csv`、精确命令/commit/软件版本与输入 SHA。独立 verifier 不 import producer，
从四份锁定输入重枚举候选、重算全部指标、bootstrap 和状态。运行前必须先用 synthetic fixtures 覆盖：
边界 bin、lower-is-better、score tie、跨 fold/run 过滤、低支持共同剔除、score inconsistency fail-closed、
orientation/gap mismatch fail-closed 与 task bootstrap 可重复性。
