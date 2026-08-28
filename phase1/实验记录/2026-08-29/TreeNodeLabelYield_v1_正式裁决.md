# Tree Node → Sibling Label Yield v1：正式裁决

日期：2026-08-29

正式分类：`HISTORICAL_GRAPH_AWARE_FULL_EXECUTION_LABEL_YIELD_NOT_ESTABLISHED`

## 1. 一句话结论

图拓扑分配在低 endpoint 预算下出现了清晰但尚不能推广到全预算的正信号：均衡 closure greedy 在 512 与 1,024 次完整
执行时，闭合 sibling labels 的中位数分别比强 `uniform_edge` 基线高 48.070175% 与 28.343949%；但在预注册 headline
预算 2,048 时只高 4.154930%，没有达到固定的 20% 门。因此 v1 总门失败，不能称“graph-aware full-execution label
yield 已建立”。

## 2. 正式结果

人口与冻结时相同：historical v11 `train:b0`，4,263 lineage-direct sibling edges、5,499 endpoints、2,293 parents、
333 physical runs、23 tasks。所有 acquisition 只读无向拓扑、parent、task 与 run。

| endpoint budget | balanced median edges | uniform-edge median edges | balanced / uniform | 相对差 | 固定 yield 门 |
|---:|---:|---:|---:|---:|:---:|
| 128 | 102 | 65 | 1.569230769 | +56.923077% | 非 headline |
| 256 | 206 | 135 | 1.525925926 | +52.592593% | 非 headline |
| 512 | 422 | 285 | 1.480701754 | +48.070175% | 通过 |
| 1,024 | 806 | 628 | 1.283439490 | +28.343949% | 通过 |
| 2,048 | 1,479 | 1,420 | 1.041549296 | +4.154930% | **失败** |
| 4,096 | 3,163 | 3,222 | 0.981688392 | -1.831161% | 非 headline |

六个预算中 balanced median 在五个预算上严格更高，trajectory consistency 门通过。三个 headline 预算的 task/run breadth、
最大 task share≤2/5 与最大 run share≤1/10 全过；唯一决定总分类的失败是 2,048 预算的 `6/5` yield 门。最差 tie seed
在该预算闭合 1,470 edges，仍不足 `1.2 × 1,420`。

## 3. 允许与不允许的解释

允许说：

- 512 和 1,024 两个预注册预算同时通过 yield、breadth 与 anti-dominance 单预算门；
- 优势随执行预算增加而衰减，提示 topology reuse 可能主要改善 label-scarce regime；
- 非均衡 `closure_greedy` 的描述性中位数在 2,048 时为 1,974，对 uniform-edge 的 1,420 高 39.014085%，说明 v1 的
  高预算损失来自“收益与均衡的权衡”而不是 topology 完全无用。

不允许说：

- 不得删除 2,048 headline、把 headline 改成 512/1,024 或降低 6/5 门；
- 不得用非均衡 secondary 替换预注册 primary；其 concentration 没有按 primary contract 获得确认；
- 不得把闭合 label 数直接替代 critic accuracy、calibration、search utility 或真实节省的 GPU·时；
- 不得声称 active learning、graph acquisition、set cover 或 verifier-guided allocation 的方法首创。

## 4. 完整性与复验

exact commit=`ecce9702591b5950a63f1e58f4d56fb46cb6289a`。producer A/B 逐字节一致，result SHA-256=
`dad4197b8172bd8e7a7ff785f35cddc722397574c680bd587d42fbcf7dfb1e2a`；不 import producer 的 verifier A/B 也逐字节一致，
SHA-256=`82d2008268aea3607d4c0ab41b53e4f1525ad10a48a08c29ab4e4c5342e453cc`，并报告全部 aggregate fields exact。
focused/full=`7/1558 passed`（47 warnings）；network、forbidden prospective opens、row identities=`0/0/0`；
GPU/API/model-fit/base-update=`0/0/0/0`。

发布包：`phase1/results/tree_node_label_yield_v1_20260829_ecce970/`。

## 5. 后续裁决

v1 到此终止，不做结果后 rescue。若继续，只允许把 b0 当 discovery：在尚未读取 acquisition curves 的 historical
`train:b1/b2` 上，先冻结按 endpoint fraction 的低预算外部确认，并先证明 b0 与确认集的 endpoint/parent/run overlap
边界；门、算法和确认集均须在 readout 前固定。即使确认成功，也仍是 benchmark/resource-allocation extension，后续
critic data-efficiency 需另立不读 frozen test 的训练协议。
