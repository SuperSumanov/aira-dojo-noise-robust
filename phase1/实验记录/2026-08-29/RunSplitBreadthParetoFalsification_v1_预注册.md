# Run-Split Breadth Pareto Falsification v1：结果前冻结

日期：2026-08-29

状态：全图 readout 已知；deterministic hash run split 的两折计数、support profile 和 acquisition curves 均未读取。

## 1. 角色与问题

0IP 的预注册大幅 label-yield 门失败，不能改写。事后描述只显示 balanced closure greedy 在六个低预算 checkpoint 的最差
yield 均不低于 uniform-edge median，同时终点 task/run breadth 较大。这里冻结的唯一问题是：这个
**yield non-inferiority + task/run breadth superiority** Pareto pattern 是否在两个 physical-run-disjoint 子集都存在，而不是由
一个 run/task 子集驱动。

这是看到全图曲线后的内部 falsification，不是外部确认，不得升级 0IP、不得证明 critic accuracy 或 search utility。即使全过，
仍需第三个未见 graph 做结果前确认。

## 2. 固定人口与先过 support

人口是已发布 prior 包绑定的 exact 539-pair strict residual。每个 physical run 由
`sha256(UTF8("PARETO-RUN-SPLIT-V1\\0" + run_id))` 首八字节的最低位确定 fold；同一 run 不可能跨折。曲线前每折必须满足：

- pairs/endpoints/parents/runs/tasks ≥ `200/350/180/70/18`；
- 最大 task/run pair share ≤ `1/3,1/10`；
- 两折 pair/endpoint/parent/run overlap=`0/0/0/0`。

任一 support 失败即固定分类 `...LIMITED_SUPPORT`，不计算 acquisition curve，也不换 salt、比例或阈值。

## 3. estimand、预算与方法

每折 endpoint budgets 固定为该折 endpoint 数的 `[3,4,5,6,7,8]/32` 向下取整。每 seed 只生成一条 nested trajectory；
checkpoint 取不超过预算的最后一个完整 action。primary method=`balanced_closure_greedy`，primary baseline=`uniform_edge`；
uniform/tie seeds=`256/32`，均由 SHA-256 固定，不把算法 seed 当独立科学样本。

每一折都必须同时通过：

1. 六点 yield integral 的最差 balanced ≥ uniform-edge median；
2. 六点中至少 5 点的最差 balanced yield ≥ uniform-edge median；
3. 六点 task-breadth integral 的最差 balanced ≥ uniform median 的 `6/5`；
4. 六点 run-breadth integral 的最差 balanced ≥ uniform median 的 `11/10`；
5. 终点 parent breadth 的最差 balanced ≥ uniform median 的 `9/10`；
6. 终点每条 balanced trajectory 的最大 task/run share ≤ `1/3,1/10`。

只有两折全过才分类 `POSTREADOUT_RUN_SPLIT_BREADTH_PARETO_FALSIFICATION_SURVIVES`；否则为
`...DOES_NOT_SURVIVE`。结果后不允许删除较弱折、换成 median tie seed、改预算或放松任何 gate。

## 4. 双实现、绑定与冻结哈希

producer 使用既有 graph producer/acquisition engine；non-importing verifier 使用先前独立 graph decoder 和独立 acquisition
engine，从 immutable raw inputs 重建同一 split、所有 trajectories、summary 与 gates，要求整份 aggregate JSON exact。
输出只含 aggregate profile/fingerprint，不释放 endpoint/parent/task/run identity。

- protocol SHA-256：`76a6ad30188c53c4f93b1132d45f16608d025057a5624eae7c5b9f13d4544396`
- producer SHA-256：`cac94d9cdce0baf6374b33d6b8daf8306781c6649d868a3ccdc0cdbef7d63636`
- independent verifier SHA-256：`94252e494b021b4fac840b82a441147c1cfdb08b9179d9e8140d9b4a96adbda2`
- synthetic test SHA-256：`29ae8fbe0121b7e93d7ae26d8846cb9dfe50c8f138be2654150e6e3669adc323`
- formal runner SHA-256：`a78591031f99dc488e6c5f61cb91f4e172af17e638b52127398d638a7bfe3d8e`
- 本地新增 synthetic tests：`7 passed`。

## 5. 13 项预飞

1. 方向：只属 Decision Corpus + Predictor Benchmark + Audit Protocol；pass。
2. 问题：两折是否都保留事后 Pareto pattern；pass。
3. 上下文：0IP 失败和 full-graph descriptive pattern 完整披露；pass。
4. 已知/未知：全图 curve 已知，hash split counts/support/curve 全未知；pass。
5. 人口：exact prior residual，只按 physical run hash；pass。
6. estimand：yield noninferiority + breadth superiority，不含 accuracy/utility；pass。
7. 公平：同折、同 endpoint budget、同 nested contract、强 uniform-edge；pass。
8. 门：support 与六个 Pareto gate 在两折全固定；pass。
9. 随机性：256/32 seeds，双 hash-seed producer/verifier；pass。
10. 资源：CPU 单线程；GPU/API/model-fit/base-update=`0/0/0/0`；pass。
11. 泄漏：orientation/gap/grade/outcome/code/prediction/runtime/test/prospective 全禁；pass。
12. 安全：credential-first safe Cards，raw archives 禁止；pass。
13. 停止：SHA/manifest/independent exact/scanner 失败无 COMPLETE；overlap 与 support 失败分别保留固定 integrity/limited-support
    分类且不计算 curves；pass。

## 6. 允许表述

若 survives，只允许称“在同一独立历史 residual 的两个 run-disjoint halves 中，拓扑平衡分配在不降低低预算 pair-label yield 的
同时扩大 task/run coverage，形成内部稳定性证据”。active learning、graph acquisition、balanced sampling 都不是方法首创；
未来 unseen graph、downstream predictor 和 end-to-end search 各自仍需新冻结协议。
