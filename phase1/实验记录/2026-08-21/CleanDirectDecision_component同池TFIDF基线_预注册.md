# Clean Direct-Decision component split：同池 char-TFIDF 基线预注册

日期：2026-08-21。状态：`PREREGISTERED_NOT_RUN`。本文件写于 component split 通过结构门之后、读取该 split 上
任何 predictor accuracy 之前。本轮是 CPU-only benchmark baseline，不解锁 GPU，也不改变 G0/G1 的模型矩阵或
正向门。

## 1. 固定输入

- Cards SHA=`5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb`；
- train 4,689 rows，SHA=`0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e`；
- dev 551 rows，SHA=`3b3fb53f84277e935c66d3b3d1646d7a7d33624fb916e3f9bcc15f689904cfa4`；
- retrospective held-out test 931 rows，SHA=
  `cb84d78d578e6a3f5378b3396a355fa83880739b4f9af8459d2b960c7ae005da`；
- Draft/Improve identity 继续由 exact-config source 的两个固定 disjoint key sets 决定，不从 code、gap 或预测反推。

## 2. 固定模型与统计

沿用已审计 suite/semantic-mixture 的唯一 char baseline，不调参：每个 endpoint code 截前 20,000 characters；
`TfidfVectorizer(analyzer="char_wb", ngram_range=(3,5), max_features=30000, min_df=3,
sublinear_tf=True, dtype=float64)`，词表与 IDF 只 fit train endpoints；pair feature=`x_better-x_worse`，同时加入其
反向与 0 标签；`LogisticRegression(C=0.5,max_iter=1500,solver="lbfgs",random_state=0)`。不使用 task、parent、
run、gap、grade、stdout/runtime 或 held-out fit。

固定报告 train fit receipt，以及 dev/test 的 merged、Draft、Improve micro、task macro、tie、margin quantiles；
输出每对 margin、task、parent、semantics 和 endpoint runs。task-clustered 与 parent-clustered bootstrap 各 20,000
次，seed 分别 `20260821` / `20260822`；cluster 重采样保留 cluster 内全部 pair，报告 accuracy 的 percentile 95% CI。
不以逐 pair binomial CI 代替 cluster CI。

producer×2 与不 import producer 的 full-refit verifier×2 必须逐字节相同；固定输入、每行 identity、split
receipt、train/dev/test run/Card/pair 零 overlap、收敛、有限 margin、预测反对称性、输出哈希与 credential scan
任一失败即 `BASELINE_INVALID`。本 baseline 没有“效果解锁”阈值：无论高低都如实作为 G1 的同池对照；G1 的
“8B 两 seed 各胜 TF-IDF 且 task-clustered delta CI 下界 >0”等门保持此前原文，不按本次数字修改。

## 3. 证据边界

该 test 已被本项目既往分析看过，因此结果只叫 retrospective same-pool baseline。它不能确认泛化或 search utility；
作用是避免未来 Qwen 与旧 960-row/不同 train pool 的 59.90% 错位比较。GPU/API/model download/base-agent update 与
prospective first-960 vault read 均必须为 0。
