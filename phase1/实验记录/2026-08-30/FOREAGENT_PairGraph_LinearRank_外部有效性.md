# FOREAGENT public pair graph：linear incidence-rank 外部审计

## 状态与输入

状态：**post-disclosure deterministic descriptive audit**。18,361 rows、895 solutions、26 components 在本项前已知；
rank 数值也在正式代码冻结前由 development probe 看过，所以不是预注册 effect，也不做 p-value/CI。

唯一输入是 FOREAGENT / PredictBeforeExecute 官方 Hugging Face 自动转换 parquet：

- revision=`6b322cb88bdbcb2b2d3897ec7d0ded94a5bb2d06`；
- bytes=`8,456,690`；
- SHA-256=`79363b7ef0b6154061f18e81f6c6fdf380e71ae3f1d7b9a262cc79acb08f0b5f`；
- 只读取 `paths`；scores、best index、官方 predictions、solution code 均未读。

## 精确 estimand

对 undirected comparison graph 定向后，其 endpoint-edge incidence matrix 在实数域的秩为：

```text
rank(B) = |V| - connected_components
cycle-space dimension = |E| - |V| + connected_components
```

这是 endpoint scalar potential 可表示的线性 contrast 数，不是 effective sample size、独立 labels 或 Shannon information。
若 pair judge 把两份 code 联合编码，它的 feature rank 也不必受这个数限制。

## 独立重建结果

Union-find producer 与不导入 producer 的 adjacency+DFS verifier 逐字段一致：

| 量 | 精确值 |
|---|---:|
| unique unordered pair rows `E` | 18,361 |
| solution vertices `V` | 895 |
| tasks | 26 |
| connected components `C` | 26 |
| task graphs connected | 26/26 |
| endpoint-edge incidence rank `V-C` | 869 |
| cycle-space rows `E-V+C` | 17,492 |
| rows / rank | 21.128883774453396 |
| redundant-row share | 0.95267142312510211 |
| min / max endpoint degree | 2 / 49 |
| degree sum | 36,722 = 2E |

development focused=`7 passed`；A/B producer byte-exact，independent DFS status=
`INDEPENDENT_DFS_RECONSTRUCTION_EXACT`；结果与 receipt mode=0600。正式 exact-commit/post-push package 仍是发布门。

## 正向意义

这证明 pair-row inflation 不是我方真实 sibling corpus 的偶然特性。FOREAGENT 公开图多数 task 接近穷举 50-solution pool，
同一 solution 最高进入 49 条 edges；18,361 rows 对 endpoint-potential contrast 只覆盖 869 个 incidence dimensions。

因此可以提出一个跨 MLE preference benchmark 的报告标准：

1. raw pair rows；
2. unique endpoints、connected components 与 incidence rank；
3. endpoint degree reuse；
4. pair 的真实 parent/trajectory/run/task grouping；
5. split 是否切开 graph components；
6. 训练是否按 ranking group/clique 成组或 rank-normalized；
7. task/run/endpoint-cluster uncertainty；
8. execution/query/init 成本单位。

这与 InstructGPT 的已知经验一致：同一 `K` 个 outputs 的 `K choose 2` comparisons 高度相关，逐 pair shuffle 会过拟合；其实现
按一个 ranking prompt 成组训练。我们的贡献不能写成“首次发现 comparison dependence”，而应写成：为 MLE-agent search-tree
数据给出统一、精确、可自动复验的 graph-linear audit，并与真实 decision、run-clean split、noise/coverage/cost 审计合并。

## 禁止外推

- 不能说 FOREAGENT 只有 869 个独立样本；
- 不能据此否定其 61.5% judge accuracy 或系统 utility；
- 不能说 rows/rank 导致 global-vs-local accuracy gap；
- 不能拿 21.13× 与我方 historical 1.33× 直接作算法优劣，因为配对机制不同；
- 不能把图 incidence rank 冒充任意 pair encoder 的 feature rank；
- 不能宣称 graph rank 或 grouped preference training 首创。

一手来源：

- FOREAGENT: https://arxiv.org/abs/2601.05930
- InstructGPT: https://arxiv.org/abs/2203.02155
