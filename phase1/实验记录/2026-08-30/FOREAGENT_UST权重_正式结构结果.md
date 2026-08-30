# FOREAGENT UST/rank 权重：正式结构结果

时间：2026-08-30。状态：`DESCRIPTIVE_UST_PAIR_WEIGHTING_AUDIT_COMPLETE`。

## 结论先行

这条结果是正面的，但它首先是 **benchmark audit 的正结果**，不是 predictor accuracy 的正效果。

FOREAGENT 公开 comparison graph 的 18,361 条 pair rows 只有 869 个 endpoint-incidence contrast
dimensions。把每条 edge 的权重设为其 effective resistance，也就是该 edge 进入 uniform spanning tree
的概率后，权重总和按 Foster/Kirchhoff 恒等式精确回到 869。正式双实现的总和分别只留下约
`1.85e-11` 与 `1.84e-11` 的浮点残差。

相对于“每条 row 权重相同”，这个权重并非近似无变化：

- edge probability distribution 的 total variation 为 `0.11721717545274284`；
- task weight distribution 的 total variation 为 `0.11712428448024467`；
- 最大 task share 从 `0.066608572517836723` 降为 `0.056386651323360182`；
- Herfindahl 对应的 effective task count 从 `17.066060493372625` 增为
  `20.574912132523227`；
- 12 个 task 被上调，14 个被下调；task identity 没有输出或选择；
- edge 权重中位数为 `0.040416666666666635`，最大值为 `2/3`，最大 edge 是全图均值的
  `14.085922516302263` 倍。

这说明 pair-row inflation 不仅影响“样本量怎么写”，还会实质改变 benchmark 对 task/edge 的隐式加权。
因此我们已经冻结的 sibling clique `2/k` 不是我方数据特有的 ad-hoc 修补：在任意 comparison graph
上，它自然推广为 edge effective-resistance / UST-inclusion weight；对完整 `K_k`，该标准严格退化为
每条 edge `2/k`，对树则每条 edge 权重严格为 1。

## 方法与复验

结果前协议在任何 per-edge leverage、task edge count 或 task redistribution 读数前冻结为
`1ad29a9568421a2a864d279a5cb71f67ec74e99f`，协议 SHA-256 为
`220d2b580b5faa968a3b230032e754b17186221b9f2565468373dc97757eb5db`。

正式根：
`/research/d7/spc/yzyang4/foreagent-ust-pair-weighting/formal-1ad29a9-v1`。

- producer：Laplacian eigendecomposition + Moore–Penrose pseudoinverse；
- independent verifier：DFS components + grounded reduced-Laplacian inverse；
- 合成控制：`K_5`、path、triangle+bridge 的显式 UST 枚举；
- focused/full：`10 / 1747 passed`，48 个既有 warning；
- producer A/B 与 verifier A/B 各自逐字节一致；
- result / verification / manifest SHA-256 分别为
  `a1a948ee...23efdb` / `b17e7a53...23ff8` / `d94fd0e8...97bce`；
- 只读 `paths`；score、best index、ranking、prediction、solution code 与 raw identity 均未读或输出；
- file/network forbidden hits 为 0；GPU/API/model-fit/base-update=`0/0/0/0`。

## 查重后的主张边界

effective resistance、Foster 恒等式、UST edge inclusion、spectral sparsification、graph-resistance ranking
以及 pairwise D-optimal design 都已有成熟先例。参考包括
[Spielman–Srivastava](https://arxiv.org/abs/0803.0929)、
[Graph Resistance and Learning from Pairwise Comparisons](https://arxiv.org/abs/1902.00141)、
[Accelerated Experimental Design for Pairwise Comparisons](https://arxiv.org/abs/1901.06080) 与
[Enhanced Statistical Rankings](https://proceedings.mlr.press/v28/osting13.html)。

所以禁止宣称新图定理、首次 graph-aware pair learning、ESS 或独立标签数。允许的贡献是：

1. 把标准图论量变成 MLE predictor benchmark 的公开、可复验审计字段；
2. 给 arbitrary comparison graph 定义与 sibling `2/k` 一致的 UST-averaged pair metric；
3. 与 task-macro、run/parent clustered inference、query/init 成本和 leakage audit 一起报告；
4. 用 FOREAGENT 外部数据证明该审计会造成非平凡的隐式权重变化，而不是我方 corpus 特例。

## 尚未跨过的门

当前没有读取 FOREAGENT 的 score/prediction，也没有声称任何模型 accuracy 被改变或失效。下一步只能在
另行冻结的历史 outcome-bearing sensitivity protocol 中，对同一 931-pair、同支持池的 11 个 static/heuristic
predictors 与固定 TF-IDF 做 UST-weighted 复算。无论结果是否漂亮，都必须同时报告原始 task-macro、UST task-macro、
parent/run clustering 和模型排序稳定性；不得用新 metric 事后换 champion。
