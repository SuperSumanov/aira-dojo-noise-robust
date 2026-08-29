# Yield-Guarded Breadth：Exact-Budget 基线勘误与前瞻冻结

日期：2026-08-29

当前开发分类：**`HISTORICAL_RUN_SPLIT_EXACT_BUDGET_YIELD_GUARDED_BREADTH_JOINTLY_FEASIBLE_DEVELOPMENT_ONLY`**。

## 1. 先修正一个会影响公平性的基线缺陷

旧 `uniform_edge` 把一条尚未选择的 sibling edge 的两个 endpoint 当成原子动作。若 checkpoint 预算落在这两个 endpoint
之间，快照会记录 `selected_endpoints=B-1`，却仍标成预算 `B`。在两折 `256 seeds × 6 checkpoints=3072` 行中，fold0/fold1
分别有 `503/453` 行少用一个 endpoint，总计 `956` 行。

这不等于此前正结果仍然成立。因此在冻结任何前瞻协议前，固定了更强且真正等预算的 baseline：保留原 edge hash 顺序，
同一 edge 的两个 endpoint 用独立 salt 确定顺序逐个加入；最大预算只剩一个位置而该 edge 需要两个 endpoint 时仍按旧规则跳过，
最后用独立 `EDGE-FILL` salt 单点补齐。每个 seed、每个 checkpoint 都强制 `selected_endpoints == budget`。

## 2. 修正后开发结论仍成立

精确预算修正没有改变两折任何 pointwise 或 trajectory-integrated nearest-rank median 门。重新求解后：

| fold | integrated closed edges（witness / exact-B baseline） | integrated tasks | integrated runs | terminal parents |
|---|---:|---:|---:|---:|
| fold0 | 276 / 276 | 138 / 96 | 248 / 191 | 66 / 66 |
| fold1 | 262 / 259 | 167 / 122 | 240 / 198 | 61 / 62 |

逐点 yield、integrated yield、task `6/5`、run `11/10`、terminal parent `9/10` 与 task/run anti-dominance
`1/3,1/10` 七门在两折都通过。因此此前窄正结论对这个公平性修正确实稳健；但它仍是对已读历史图的 development，不能写成外部确认。

## 3. 双实现与资源边界

- producer A/B 原始结果 SHA-256 均为 `86bdcee7005914d6fcdaf2f39be517cf725fed785f7e590f7916c97f11051314`；
- non-importing aggregate verifier A/B SHA-256 均为 `7e3524f260f28a24d6faba6e838270ba48985346832be3fd3ea97f8cd17bd37e`；
- verifier 独立重写 endpoint order、直接重算每个 prefix 的 induced edges、baseline medians、旧 underfill 数和全部 aggregate gates；
- aggregate 结果没有私有 endpoint witness，所以 `private_witness_recomputed=false` 被明确保留；未来确认必须补 mode-0600 witness 双实现；
- A/B 单核 wall=`31.17/29.19s`，max RSS=`160752/160896 KiB`；network/prospective boundary hits=`0/0`；
- prospective values、senior test、GPU、API、model fit、base update 均未使用。

公开 commit=`dfdf8c28e29860f62327403e83f6bf7a3130a282` 的 fresh detached post-push replay 也已完成：focused=
`3 passed in 0.43s`，producer A/B 与 independent verifier A/B 分别再次逐字节得到同一
`86bdcee7...1314` / `7e3524f2...d37e`；network/prospective boundary/credential filename/blob hits=`0/0/0/0`。

r1–r4 都在 scientific readout 前失败并保留：两次显式传输路径错误、一次 `PYTHONPATH` 缺失、一次 import-only preflight
发现历史 falsification worktree 本来就早于 development module。r5 才是首个实际重建图并完成结果的运行；没有覆盖失败证据。

## 4. 前瞻合同

在 Target-522 candidate identity/count/profile 尚未出现、`LATEST` 仍为 `887491a...62697` 时，
`phase1/yield_guarded_breadth_forward_target522_v1.json` 固定同一未见 physical-run increment、六个 `[3..8]/32`
endpoint checkpoints、256 seeds 和原七门，并把 exact-B baseline 算法写成逐项合同。

未来只有完整结构 support 通过后才允许一次运行；公开 aggregate 不泄露 endpoint/task/run/parent identity，私有 mode-0600
witness 由不导入 producer 的 verifier 从 selected endpoint 重算 induced edge。任何 candidate/profile 先于公开冻结、baseline
预算不精确、支持不足、solver timeout 或 witness 双实现不一致都 fail-closed，不改门 rescue。

## 5. 表述边界

可讲的是 MLE-agent tree 的 endpoint-execution → sibling-pair-label accounting：执行 endpoint 才取得绝对分数，只有 sibling
两端都执行才闭合一个 pair label，因此 acquisition 同时需要审计 label yield、task/run/parent breadth 与 anti-dominance。
MILP 只是固定合同的可行性证书；graph active learning、pairwise active learning 和 constrained/fair acquisition 均已有工作，
不能声称一般图采样或约束优化首创。当前也没有 predictor accuracy、sample efficiency 或 search utility 的正面确认。
