# Tree linearization weight：887 正式结果与防撞边界

日期：2026-08-28。正式分类：`MULTI_AXIS_MATERIAL_LINEARIZATION_REWEIGHTING`。

## 1. 结果前问题与正式答案

固定协议只问：同一 observed MLE search fragment 从“一条物理 edge 一次”改写成“枚举全部 root-to-leaf paths”时，
shared-prefix edges 会被复制多少，task/run empirical weights 会移动多少？

11,906 个 endpoints 恢复 10,895 条同 run、同 task 的 observed edges，parent-present fraction=
`0.9150848311775576`，435 runs / 34 tasks 全有 observed edge，完整性与支持门全过。3,599 条 root-to-leaf paths
产生 26,107 次 edge occurrences，其中 15,212 次是重复，duplicate fraction=`0.5826789749875513`；
`0.3877007801743919` 的 unique edges 重复，mean/p90/p95/max multiplicity=`2.396236805874254/4/7/144`。

task/run TV 分别为 `0.1603376038171571/0.18894421733497543`，均越过预注册 `0.05/0.10`。task 最大
share=`0.25672326755392383→0.3858352166085724`，run 最大 share=
`0.06351537402478201→0.1158693070823917`。这支持一个正面数据/协议主张：tree-native provenance 会改变
benchmark estimand，不是只影响存储格式或可视化。

## 2. 与已有工作的边界

- [Tree Training](https://arxiv.org/abs/2511.00413) 已明确指出把 tree trajectories 拆成独立 sequences 会重复计算
  shared prefixes，并用 tree packing/gradient restoration 消除训练计算冗余；我方不能主张首次发现重复前缀或首次做
  tree-aware training。
- [T-STAR](https://aclanthology.org/2026.findings-acl.229/) 已指出独立 trajectory credit 会给共享 prefix 不一致的
  credit，并通过 Cognitive Tree、value backup 与 divergence-point preference 优化处理；Tree-OPO/TreePO 同样覆盖
  tree-aware advantage 与采样。不能把 tree-aware credit assignment 包装成我方新方法。
- [SPPD](https://aclanthology.org/2025.findings-emnlp.19/) 从共享前缀树采样并收集完整 reasoning paths，理论目标是保持
  policy distribution；这与我方“发布表中路径展开改变 edge/task/run empirical weights”的 estimand 不同，但构成直接
  邻近工作。
- [Dolma](https://arxiv.org/abs/2402.00159) 已对 Reddit thread 的 atomic/partial/full linearization 做下游消融；因此
  “树形数据表示会影响学习”不是一般性首创。

在已核验范围内尚未发现上述工作对真实 Python MLE-agent search corpus 做同人口的 unique-edge↔all-path deterministic
weight audit，并同时绑定 physical run、task、结果前阈值、结果盲 accrual 与独立 postflight。这里只把该组合定位为
MLE-specific benchmark/data contribution，不写“首个一般理论”或“所有 agent trajectory dataset 都有此问题”。

## 3. 对论文主线的正面作用

论文叙事可从“我们审计了很多风险”提升为：

1. tree-native Decision Corpus 保存 stable node/parent/run identity 与真实 choice fragments；
2. 正式实证显示常见 path linearization 会把物理边按 descendant leaves 隐式重采样，并在 task/run 两轴产生材料变化；
3. Predictor Benchmark 因此预先固定 task→parent→pair headline、run sensitivity 与 pair-micro compatibility view，而不是
   在结果后选一个有利数字；
4. 发布物应同时给 node/edge/choice-set tables、path compatibility view 和可逆 multiplicity/weight ledger。

第 4 项是下一步的工程正贡献：实现 tree-native release validator 与 path-compatibility exporter，证明每个 path
occurrence 按该 edge 的 inverse multiplicity 加权后精确还原 unique-edge measure。这个等式本身不是算法 novelty；价值是
把它做成可验证的 benchmark contract，并在 closure 后与 predictor estimand sensitivity 联合报告。

## 4. 复现与限制

协议/source commit=`95b49fd...a697feb` / `e9f4fb9cf495d6751fb77d061095f6dca312728c`；formal focused/full=
`19/1299 passed`，full 有 47 warnings。producer、同工作树 verifier 与 fresh-worktree postflight 均 A/B 逐字节一致；
formal/postflight manifest=`d8972749...d46a` / `725566a5...2961`。两次预科学/封装失败均保留且未用于裁决。

限制：snapshot 仍为 435/960、closure=false；只研究 observed fragments，不补缺失 parents、不证明完整 source tree；
不输出身份值；未读取 prospective truth/prediction，未计算 accuracy/effect/search utility，未使用 GPU/API/model fit。
