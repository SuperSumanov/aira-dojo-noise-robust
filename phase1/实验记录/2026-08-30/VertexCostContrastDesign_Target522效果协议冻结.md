# Vertex-Cost Contrast Design：Target-522 效果协议结果前冻结

日期：2026-08-30
状态：`FROZEN_BEFORE_TARGET522_CANDIDATE_PROFILE_OR_VALUES`

## 1. 正方向主张现在具体到什么程度

真实成本是执行 endpoint，而不是随后物化出的 pair rows。同一 parent 执行 k 个 siblings 会给出 `k(k-1)/2` 条依赖 pair，
但其 contrast rank 至多 `k-1`。VCCD 因而用代码特征的 centered contrast 做 D-opt endpoint acquisition，并在后续 critic fit 与
主指标中都用 `2/k` 降低 clique 二次膨胀。要检验的不是 D-opt 本身是否新，而是这套“付费顶点→依赖标签→run-clean 外推”的完整
MLE acquisition contract 是否在同成本下提高 critic transfer。

## 2. 已冻结的 Stage A

唯一 cohort 是已有自动 Target-522 选择器第一次稳定捕获的 snapshot 887 之后增量。完整 physical runs 在每个 task 内按固定 salted
hash 分成 acquisition/evaluation；两边 run、endpoint、parent 必须零交叠。Stage A 只允许读取 outcome-blind manifest 中的
card/task/run/parent/code 与精确 sibling topology，比较：

- `exact_b_uniform_edge`：256 seeds 中按六个 checkpoint 的 integrated closed-edge yield 取 nearest-rank median，再取最小 seed；
- `yield_guarded_breadth`：在 acquisition graph 上重算既有 exact-B、yield 非劣与 task/run breadth 证书；
- `vertex_cost_contrast_design`：固定 128D Unicode char 3--5 gram hash、D-opt gain/endpoint、terminal task/run caps。

轨迹 checkpoint 为 `[3,4,5,6,7,8]/32`，实际 fit 只用 `4/32` 与 `8/32`。三臂 exact budget、nested；VCCD caps 明确只约束
terminal `8/32`，不偷换成每个 prefix 都过 cap。public 只写 aggregate 与 hashes，raw selection/run IDs 仅在 mode-0600 private
witness。

producer=`freeze_vertex_cost_contrast_target522_selection.py`；verifier 不导入 producer，重新构造 split、graph、uniform/VCCD 顺序，
并把 yield 选择当证书重验约束。focused synthetic + outcome-blind end-to-end=`14 passed`。协议、source 与 tests 全部 SHA 绑定在
`vertex_cost_contrast_target522_effect_v1.json`。

## 3. Stage B 为什么现在绝不能跑

`first-960 + accrual-closure` 是更高优先级的揭盲门。Target-522 到达只允许固定 selection escrow，不能打开 grade/outcome/pair
orientation/gap/prediction，也不能算 accuracy 或 fit critic。只有 first-960 one-time closure receipt、Stage-A public/private/verifier
hash、label-release exporter 与 fresh access audit 全部通过，才允许一次性读数。

闭合后的固定模型是 char-wb TF-IDF 3--5 gram + LR（C=0.5、lbfgs、seed0），不做 Target-522 调参，不加历史 labels。每个 selected
parent clique 的 unordered pair weight=`2/k`、两个方向各=`1/k`。evaluation 使用所有非平局 sibling pairs；主指标是
rank-normalized task-macro accuracy，另报 proper scores、task/run clustered 95% CI、drop-dominant-task、raw micro/parent/run macro
和固定 gap buckets。

最大矩阵为三 selection arms × 两 budgets + full-acquisition reference，共 7 个 CPU fits；yield 不可用时为 5 个。预计单 CPU
35--90 分钟，GPU/paid API/base update=`0/0/0`。这只是以后闭合时的固定矩阵，不是现在启动长实验。

## 4. 冻结时证据与不能说的话

`2026-08-30T02:32:51Z` 的结构盲观测：LATEST=`98f2cba9ca4b3ac6404305da2528a4e8c391ba795f74438a5e4cca1a162765fa`，
physical runs=`468`、snapshot dirs=`117`；Target-522 candidate/COMPLETE/FAILED 均不存在，config-v2 count=`0`，prospective
values 未读。因此 split、graph profile、code features、selections 和效果都尚未见过。

当前不能宣称 accuracy 或 utility 有提升。协议预先定义 strong/directional/mixed/no-gain/limited-support/integrity-fail 并要求所有
支持充分的 arm×budget 全报；不得在看到结果后删预算、加 OpenRouter、恢复历史 single-fold、换 metric 或用 full-data reference
救结果。

工程核心 commit=`c57bbbf14d9e7415452b404d373674c768a67cce` 的 GitHub fresh-checkout 回执为 secret hits=`0`、
full=`1691 passed, 48 warnings in 96.72s`、worktree clean、prospective values unread。第一次 preflight 因共享仓库缺 baseline commit
以 rc=128 停止，r2 只增加 fetch 后通过；失败证据原样保留。
