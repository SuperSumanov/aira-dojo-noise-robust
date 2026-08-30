# FOREAGENT UST outcome sensitivity v1：结果前冻结

## 为什么值得做

FOREAGENT / *Can We Predict Before Executing Machine Learning Agents?* 明确把 895 个 curated solutions 在 task 内穷举成
18,438 pair rows，并把 pair-row micro accuracy 作为 primary metric；论文报告 DeepSeek/GPT=`61.5%/58.8%`。我方已经在
其自动 parquet 上验证 18,361 rows 只有 endpoint-incidence rank=`869`，但该 parquet 与 18,438-row official alignment
不是同一网格，不能把旧 UST weights 直接乘到 alignment predictions 上。

因此本实验只问一个窄问题：在 exact official alignment grid 上重建共同 comparison graph 后，raw pair micro、task macro
和 DeepSeek−GPT 差值在 UST/rank weighting 下移动多少。它直接服务 Decision Corpus + Predictor Benchmark + Audit Protocol，
不恢复 HCE、多保真、Probe、score-channel 或 K≥1 lookahead。

## 结果前状态

截至 `2026-08-30T05:36:11Z`，旧 raw outcome 已公开，但 exact common-support graph rank、UST weights、UST accuracy、shift、
paired delta 和 LOTO 均未计算或读取。科学协议 SHA-256=
`7d47b1aa6ef3ffb61c47f1fe3d6631a5bb7b2c97228de8a7c9192b9fc557a425`；状态严格为
`FROZEN_AFTER_RAW_OUTCOMES_DISCLOSED_BEFORE_GRAPH_WEIGHTED_OUTCOME_COMPUTATION`，不是 outcome-blind confirmation。

固定输入：

- 156-file manifest SHA-256=`3df2715b2d2e5f3cc6193c07c99eb682e042e8aa6cb724b046b2469b35773a4e`；
- 110,620-row compact primitive master，34,910,546 bytes，SHA-256=
  `480616317ddebb249084dbc8b36b4060fac4b77353fce16b436351eab9c235fe`；
- DeepSeek 三轮 exact grid；GPT task 内三轮 intersection；再取 cross-model intersection；
- 移除共同支持中的 nonfinite truth / exact ties 后，固定 common finite directional pairs=`18,381`、tasks=`26`；
- confidence 不读取、不作 inclusion；prediction index 缺失按旧审计记 0 correctness。

## 四个固定估计量

1. `raw_pair_micro`：共同支持的每条 materialized pair row 等权；
2. `ust_rank_micro`：每条边按 `b_e^T L^+ b_e` 加权，task 总权重等于其 incidence rank；
3. `raw_task_macro`：task 内 uniform pair average，再对 26 tasks 等权；
4. `ust_task_macro`：task 内 UST-weighted average，再对 26 tasks 等权。

DeepSeek 和 GPT 先分别算四项，再在同一 pair 上算 DeepSeek−GPT。每个 model×task×pair 的三个 release correctness 先平均；
20,000 次 task bootstrap seeds=`20260830/20260831`，ratio estimand 在每个 bootstrap 内重算分子分母；固定 1e-10 LOTO
sign tolerance。pair-iid inference 禁止。

没有 success threshold：无论 shift 正、负或为零都完整报告。prior alignment v2 的 `INSUFFICIENT-SUPPORT` 裁决不可被本实验
重写；UST rank-micro 是随机 spanning basis 的 alternative sensitivity，不是“唯一正确 accuracy”。

## 实现与预检

- producer：Laplacian eigendecomposition / pseudoinverse，SHA-256=
  `ac8db1ef0f913eb9d5f7d4a87c6109d29a27dbc9693c9726846a9989fbe90ba5`；
- independent verifier：adjacency/DFS + grounded inverse，SHA-256=
  `3cc166303a6684ff2183684a410fff3922630e32c3f247fedeb08fa1ba12590a`；
- synthetic/end-to-end tests SHA-256=
  `06f132393b0b791185d6d1e60833a96a06505f3eaa16092dc682592c9a727c88`；
- formal runner SHA-256=`43fa08bba3cd5f553ee7d1a1be293c2968dba96a76e2515a685cfec9c1bc267a`；
- focused=`11 passed`；合成门覆盖 K4、tree、triangle+bridge、位置反转、missing prediction、GPT incomplete
  triplicate、nonfinite truth、重复/真值漂移与 near-zero sign；
- formal 必须 fresh exact commit、full `phase1/tests`、producer A/B、verifier A/B、file+network trace、只读 manifest；
- 单 CPU，预计 formal 中除 full tests 外 2–20 分钟；GPU/API/model fit/base update=`0/0/0/0`。

## 查重与主张边界

FOREAGENT 官方论文已定义 Data-centric Solution Preference、发布 corpus 并报告 61.5% micro accuracy 与 agent-level 6×；
effective resistance、UST inclusion、Foster identity、graph-resistance ranking 与 pairwise optimal design 也都有成熟先例。因此禁止：

- 宣称新 graph theorem、首次 graph-aware comparison 或有效样本量；
- 把 UST 数写成“校正后的唯一真 accuracy”；
- 用本敏感性否定 FOREAGENT 的 6× acceleration 或 +6% gain；
- 把 postdisclosure sensitivity 冒充 prospective confirmation。

允许的贡献只有：给直接竞品的公开 MLE preference corpus 做可复验的 graph-aware metric audit，并判断 combinatorial pair-row
weighting 是否 outcome-material。正式执行只能在该协议与代码推送后，用 exact commit 开始。

来源：

- https://aclanthology.org/2026.acl-long.182/
- https://github.com/zjunlp/predict-before-execute
- https://huggingface.co/datasets/zjunlp/PredictBeforeExecute
- https://arxiv.org/abs/0803.0929
- https://arxiv.org/abs/1902.00141
- https://arxiv.org/abs/1901.06080
