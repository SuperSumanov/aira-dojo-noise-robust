# Tree Node → Sibling Label Yield v1：预注册与防撞

日期：2026-08-29

状态：真实 acquisition curves 未读；先冻结结构 estimand、算法、预算、正门和失败分类。

## 1. 为什么值得测，但不能夸大 novelty

主动选择 pair、图节点或测试标签本身都有充分先例：active top-k ranking 直接选择 comparison；graph active learning
选择节点标签；active testing 选择昂贵 test labels 并纠正选择偏差；NAS predictor 文献也长期研究用少量完整训练结果学习
performance predictor。因此本项目不能声称首创 active learning、active ranking、图 acquisition 或昂贵评测选择。

相关原始工作：

- [Active Learning for Top-K Rank Aggregation from Noisy Comparisons](https://proceedings.mlr.press/v70/mohajer17a.html)
- [Algorithms and Hardness for Active Learning on Graphs](https://proceedings.mlr.press/v267/cohen-addad25a.html)
- [Active Testing: Sample-Efficient Model Evaluation](https://proceedings.mlr.press/v139/kossen21a.html)
- [How Powerful are Performance Predictors in Neural Architecture Search?](https://arxiv.org/abs/2104.01177)
- [Active Code Learning](https://arxiv.org/abs/2306.01250)

当前窄差异是 oracle 与 supervision 的组合：固定 generator 已给出树拓扑；花一次真实成本完整执行一个 endpoint，得到一个
绝对 external grade，并同时闭合该 endpoint 与已执行 siblings 之间的多个 pairwise training labels。它既不同于直接购买
一次 comparison，也不同于普通 node classification label。即便结果为正，也只能作为 MLE tree benchmark 上的结构化
label-allocation extension，而不是宽方法首创。

## 2. 冻结人口与已知信息

唯一人口是 historical v11 `train:b0`，input normalized SHA-256=
`bd31b4679c7b4405703b976921df0bc63acba4fc0c4a002f4b8f36d171251fca`，4,263 rows。0HY 的独立 lineage
certificate 已知这些 rows 全是 lineage-direct sibling；已知 aggregate topology 为 2,293 parents / 5,499 endpoints /
333 physical runs / 23 tasks。冻结时没有读取任何 acquisition yield、breadth 或 concentration curve。

算法只允许读取 unordered endpoint、parent、task、physical run、train partition 和 budget=0。better/worse orientation、
gap、grade/outcome、代码、predictor/judge、自报分、runtime 或执行反馈一律不得进入 acquisition。

## 3. 四个固定 acquisition

成本单位始终是一次完整 endpoint execution；没有 partial run、提前停止或低保真。

1. `uniform_node`：对 endpoint 做 seeded SHA-256 随机顺序。
2. `uniform_edge`：对 sibling edge 做 seeded SHA-256 随机顺序；共享 endpoint 自动复用。这是强随机基线。
3. `closure_greedy`：只用图拓扑，最大化“新闭合 edges / 新执行 endpoints”。
4. `balanced_closure_greedy`：在 closure gain 上固定加入已闭合 task/run edge counts 的乘性惩罚，防止收益来自单一密集簇。

每个方法只生成一条到 4,096 endpoints 的 trajectory，在 `[128,256,512,1024,2048,4096]` 读取不超过预算的最后完整
动作，禁止每个预算重新优化。随机基线 64 seeds；greedy 只把 8 个 seed 用作 exact tie sensitivity，不把它们当科学独立样本。

## 4. 正门与杀死条件

primary 是 balanced greedy 对 uniform edge；headline budgets=`512/1024/2048`。

- 最差 greedy tie seed 的 closed-edge yield 在每个 headline budget 均须达到 uniform median 的 `6/5`。
- 最差 greedy tie seed 的 task/run breadth 均须达到 uniform median 的 `3/4`。
- 最差 greedy tie seed 的最大 task/run edge share 均须不超过 `2/5`、`1/10`。
- 六个预算中至少五个，greedy median closed edges 严格高于 uniform median。

全过才允许分类为 `HISTORICAL_GRAPH_AWARE_FULL_EXECUTION_LABEL_YIELD_FEASIBLE`；否则固定为
`HISTORICAL_GRAPH_AWARE_FULL_EXECUTION_LABEL_YIELD_NOT_ESTABLISHED`，不得结果后改预算、阈值、人口或 primary。

## 5. 结论边界

本轮不读前瞻 cohort，不调用 API，不启动 GPU，不训练任何模型。即使结构门全过，也只证明 full-execution label closure
的历史可行性；downstream critic data efficiency 必须另立 result-blind 协议，不能用本轮 pair count 直接替代准确率或
search utility。未来若加入 full-context evaluator uncertainty，也必须在读取新 execution labels 前另冻 acquisition rule。
