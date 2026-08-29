# Independent Label-Scarce Yield Confirmation v1：结果前预注册

日期：2026-08-29

状态：独立 residual 的所有 acquisition yield、breadth 和 method curve 均未读取。

## 1. 假设如何从 discovery 收窄

v11 train:b0 的全局 v1 没有过总门：balanced closure greedy 在 endpoint budgets 512/1,024 相对强 `uniform_edge`
基线有清楚正信号，但在 2,048 未达固定 6/5，4,096 还发生反转。该失败完整保留，不能再声称“全预算普遍优越”。
b1/b2 的 physical runs 又 100% 嵌套于 b0，不能确认。

0IO 已在任何新曲线前认证一个四层零重叠的 senior-0819 train residual：539 pairs、1,036 endpoints、505 parents、
190 physical runs、36 tasks；与 v11 的 pair/endpoint/parent/run overlap=`0/0/0/0`。该图有 505 components，最大 degree=4，
结构复用机会有限。因此本轮明确是一个 **post-discovery、result-blind、label-scarce confirmation**：只检验前 6/32 endpoint
预算内的完整执行标签产出，不允许高预算结果救回，也不把它伪装成原始全局预注册。

## 2. estimand 与预算

一次 oracle action 是完整执行一个 endpoint 并获得一个外部 scalar grade；当且仅当 sibling pair 两端都执行后，该训练 label
闭合。primary estimand 是每条 nested trajectory 在六个等间距 checkpoints 的累计 closed-edge 之和，即截至 6/32 的离散
yield-area approximation。

预算按总 endpoints=1,036 的 `[1,2,3,4,5,6]/32` 逐点向下取整，固定为 `[32,64,97,129,161,194]`。这覆盖 b0 已发现的
约 3%–19% 稀缺区间，但没有把 b0 的具体最优点移植成单点 headline。所有方法每个 seed 只生成一条 nested trajectory，
checkpoint 取不超过预算的最后一个完整 action，禁止按 budget 单独重优化。

## 3. 方法、基线与固定门

primary method 是 task/run-balanced closure greedy；primary baseline 是会利用 shared endpoint 的强 `uniform_edge`，不是弱
`uniform_node`。另完整报告 unbalanced closure greedy 和 uniform node。uniform baselines 固定 256 个 SHA-256 randomizations，
greedy 固定 32 个 SHA-256 tie trajectories；这些 seed 只是算法随机化，不冒充独立科学样本。

所有门必须同时通过：

1. 每条 trajectory 先求六点 closed-edge sum；最差 balanced tie trajectory ≥ uniform-edge trajectory-sum 中位数的 6/5。
2. 六个 checkpoints 至少 5 个满足 balanced median > uniform-edge median。
3. 在终点 6/32，最差 balanced yield ≥ uniform median 的 11/10。
4. 终点最差 balanced parent/task/run breadth 分别 ≥ uniform median 的 2/3、3/4、3/4。
5. 终点每条 balanced trajectory 的最大 task/run share 分别 ≤1/3、1/10。

任一失败即分类 `HISTORICAL_INDEPENDENT_LABEL_SCARCE_FULL_EXECUTION_YIELD_NOT_CONFIRMED`；全过才允许
`...YIELD_CONFIRMED`。结果后不得改 threshold、budget、population、primary method/baseline；额外高预算诊断不能 rescue。

## 4. 完整性与独立实现

机器协议绑定 0IO qualification protocol/result/verifier/package manifest、producer/independent graph decoders 和两套既有
acquisition engines。producer 重建旧 direct-sibling core 并应用原 strict residual；verifier 不 import 新 producer，使用先前
独立 Card/decision decoder 和独立 acquisition implementation 重建全部 trajectory、summary 和 gates，要求整份 aggregate
JSON exact。只允许 unordered endpoint、parent、task、physical-run identity；禁止 orientation、gap、grade/outcome、code、
prediction、runtime、senior test rows 和所有前瞻值。输出不含任何 row/node/parent/task/run identity。

- protocol SHA-256：`69db0331c92f5912dfb5fcd6ebc3dfeb0838eff090f80390e2137c91bd489581`
- producer SHA-256：`3195b7499a1a10ad8e4e3f8faa586d3bc92314589dcb88c7e4f6157be912a78d`
- independent verifier SHA-256：`ea72412b072f693045089daef1f37bfcdd672f563d6cd7ff1392bbe1e00ccfa7`
- synthetic test SHA-256：`18077de7f67ffe957f1d774f0b1aeb17dcbb283a4ff676c0c808530e7816f2fd`
- formal runner SHA-256：`3d9e07ff69259fdf467983aa1cb4d379231aa894c5ec12120e4c455e2108d99e`
- focused synthetic：`29 passed`（其中新测试 7 passed）

## 5. 13 项预飞

1. 方向：仅 Decision Corpus + Predictor Benchmark + Audit Protocol；pass。
2. 问题：独立图的 label-scarce full-execution yield；pass。
3. 上下文：b0 discovery 与 independent qualification 均完整披露；pass。
4. 已知/未知：旧曲线和 residual census 已知，新 residual curve 全未知；pass。
5. 人口：固定 539-pair residual，senior test 禁用；pass。
6. estimand：六点 trajectory-level discrete yield area；pass。
7. 公平：同图、同 endpoint budget、同 nested contract，强 uniform-edge baseline；pass。
8. 门：6/5、5/6、11/10、breadth、anti-dominance 全冻结；pass。
9. 随机性：256/32 固定 SHA-256 seeds，双 hash-seed 重跑；pass。
10. 资源：CPU single-thread；GPU/API/model-fit/base-update=`0/0/0/0`；pass。
11. 泄漏：orientation/label/code/prediction/runtime/test/prospective 全禁；pass。
12. 安全：credential-first safe Cards，raw archives 禁止；pass。
13. 停止：任一 hash/certificate/manifest/independent exact/scanner 失败即无 COMPLETE；pass。

## 6. 防撞与允许的贡献表述

active learning、graph acquisition、active ranking、densest-subgraph optimization 和 branch-return critic 都不是本项目首创；
不得宣称一般方法 novelty。若确认通过，允许的窄表述是：在固定 MLE generator 的真实 execution-derived sibling graph 上，
把执行预算记到 node 而不是 pair，并利用已知 lineage topology，可以在独立 historical runs 的明确 label-scarce 区间提高
可审计 pair-label yield，同时保持 parent/task/run breadth。critic accuracy 与 search utility 仍需各自的新协议。
