# Yield-Guarded Breadth Feasibility v2：开发裁决

日期：2026-08-29

固定分类：**`HISTORICAL_RUN_SPLIT_YIELD_GUARDED_BREADTH_JOINTLY_FEASIBLE_DEVELOPMENT_ONLY`**。

## 1. 结论

在 0IQ 已经 readout 的两个 physical-run-disjoint folds 上，都存在一条六 checkpoint、nested endpoint trajectory，同时满足此前固定的全部门：

- 每个 checkpoint 的 closed sibling-edge 数不低于 256-seed `uniform_edge` nearest-rank median；
- integrated task/run breadth 分别不低于 baseline 的 `6/5` 与 `11/10`；
- terminal parent breadth 不低于 `9/10`；
- terminal 最大 task/run edge share 不高于 `1/3,1/10`。

这把 0IQ 的“小 yield 代价换大 breadth”描述推进为一个更窄但明确的开发正结论：在这两张历史图上，yield 与 breadth 的固定合同是**联合可行**的；0IQ 中 fold0 的两项失败不是拓扑上不可避免，而是先前 soft-penalty heuristic 没有显式执行 yield floor。

它仍不是未来确认，不恢复 0IQ 被拒绝的“原 heuristic free Pareto”，也不证明 predictor accuracy、downstream sample efficiency 或 search utility。

## 2. 结果前工程勘误

v1 在没有生成 `result.json` 时发现 HiGHS 进程有 20 个线程，违反 single-CPU preflight；于 `2026-08-29T02:00:04Z` 主动终止并保留 `FAILED_RC=143`。wall=`5:49.62`、max RSS=`567648 KiB`，scientific fold result 未读。

v2 在任何 scientific readout 前把已经固定的通过门直接编码为 feasibility constraints，移除全局最优方法主张；同时显式设置 HiGHS `threads=1, random_seed=0` 并把整个进程树 pin 到一个 CPU。合法 synthetic graph 上，MILP 与 86 条可行 nested trajectories 的穷举 oracle 一致，并正确拒绝已知 infeasible 负控。

## 3. 双折精确结果

| fold | integrated closed edges | integrated tasks | integrated runs | terminal parents |
|---|---:|---:|---:|---:|
| fold0 witness / uniform median | 276 / 276（0%） | 138 / 96（+43.75%） | 248 / 191（+29.8429319372%） | 66 / 66（0%） |
| fold1 witness / uniform median | 262 / 259（+1.1583011583%） | 167 / 122（+36.8852459016%） | 240 / 198（+21.2121212121%） | 61 / 62（-1.61290322581%） |

两折逐点 yield floor 均为 6/6；terminal task/run anti-dominance 与全部七个开发 gate 均通过。注意这些百分比是一个可行 witness 相对 baseline aggregate 的描述，不是随机重复上的 effect estimate 或置信区间。

## 4. 复验与资源

- executed producer SHA-256：`0e62c9c3bf15b689caf98ee73b2f22d1134e99b6c212960c958bd7021570942e`；
- preflight SHA-256：`3d3c5fa54877ef830c9fff67ae06a93330bbcfcd12448c8cbc6639deb5ad900b`；
- result A/B SHA-256：均为 `e43831946643d60654bb10b834278fd480c97292fcf91ea6dfa95962c77c191d`，逐字节一致；
- non-importing aggregate verifier SHA-256：`5079a6350a5f4e83a028f43cfa99e8217abeb486acab8ae345d371f607a9610c`；
- independent verification SHA-256：`c3680fb2a767ad51a3b3c1109f102ec56556d17ec33e041d248cdb9e22f06a2d`；
- A run wall=`27.33s`、CPU=`99%`、max RSS=`159320 KiB`；A/B 均 single-CPU exact；
- file/network trace 的 boundary/network hits=`0/0`；prospective values 与 senior test 未读；GPU/API/model-fit/base-update=`0/0/0/0`。

独立 verifier 重新绑定 prior/result/A-B hashes，并从 aggregate 逐项重算 baseline、floor、积分与七门；它明确没有私有 endpoint witness，因此 `private_witness_recomputed=false`。未来正式确认必须补 private witness escrow 与不导入 producer 的 graph-level verifier，不能把本 aggregate verifier 写成完整双实现。

## 5. 新颖性边界

graph active learning、batch active learning、fair/constrained acquisition 都已有成熟工作；例如 Ji & Han 研究图上的 offline batch node selection，Chen & Krause 研究 batch active learning 与 adaptive submodularity，FAIR 研究科学发现中的公平协同 acquisition。因而本轮不能声称“一般图采样”或“约束 active learning”首创：

- https://proceedings.mlr.press/v22/ji12.html
- https://proceedings.mlr.press/v28/chen13b.html
- https://proceedings.mlr.press/v206/xu23e.html

可争取的 MLE-specific 正贡献是：把“执行一个 tree node 才得到 score、只有两个 sibling 都执行才得到 pair label”形成的 endpoint→edge label accounting 明确定义为 benchmark acquisition contract，并同时审计 label yield、task/run/parent breadth、anti-dominance、run-disjoint stability 与未来冻结。MILP 在这里是可行性证书，不是论文唯一 novelty。

## 6. 下一步

在下一张真正未见、与当前 graph endpoint/parent/physical-run 全隔离的 stable sibling graph 出现前，冻结同一六 checkpoint、256-seed baseline、七门、single-CPU solver 与 private-witness verifier。只有该 graph 在任何 acquisition curve/profile readout 前通过 support gate，才运行一次确认；不得在新图上调比例、删 checkpoint 或以 feasibility-by-construction 偷换成 downstream predictor 收益。
