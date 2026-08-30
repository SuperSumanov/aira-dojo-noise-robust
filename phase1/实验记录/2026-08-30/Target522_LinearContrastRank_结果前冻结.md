# Target-522 Linear Contrast Rank 审计：结果前冻结

## 结论状态

截至 `2026-08-30T03:48:16Z`，本项仅为**结果前冻结的确认协议**，不是正结果。冻结检查只看 marker：

- Target-522 `candidate.tsv` / `READY` / `COMPLETE` / `FAILED_RC` / `CONTINUITY_GAP` / `TIMEOUT_RC` 均不存在；
- VCCD Stage-A formal output 不存在，原 Stage-A monitor PID live；
- 未打开 Target-522 candidate profile、endpoint/task/run/parent identities、private selection；
- 未读 label、grade、gap、outcome、prediction、accuracy、runtime 或 utility；
- GPU / 付费 API / model fit / agent-base update = `0 / 0 / 0 / 0`。

## 为什么值得做

pair benchmark 常把每条 sibling pair 当成一条数据行。但同一 parent 下执行 `k` 个 endpoints 后，完整两两比较会产生
`k(k-1)/2` 条 rows；这些 rows 对 endpoint scalar contrast 的 incidence rank 只有 `k-1`。在 Stage-A 冻结 source semantics
保证的互不共享 endpoint 的 exact sibling cliques 上：

```text
pair rows = Σ_j k_j(k_j-1)/2
incidence rank = Σ_j (k_j-1) = endpoints - parents
redundant rows = pair rows - incidence rank
```

若两个未来 run-clean 分区都存在明显 row inflation，这会给数据集论文一个可复验的正审计结论：报告 pair rows 时必须同步
报告 endpoint incidence rank，并在训练/推断中处理 clique dependence。它也直接解释 VCCD 为何把执行 endpoint 而不是派生 pair
作为成本单位，以及为何使用每条 clique pair 的 `2/k` 权重。

## 已披露的历史开发读数

历史 `phase1/v11_decision/decision_train_v11_b0.jsonl`（checkout SHA-256=
`6110488201163832f9ae4f95af7de3682152aed9d77e413ca72538b203691c59`）给出：

| 量 | 数值 |
|---|---:|
| unique unordered pair rows | 4,263 |
| parents | 2,293 |
| within-parent endpoint memberships | 5,499 |
| endpoint-edge incidence rank | 3,206 |
| redundant rows | 1,057 |
| rows / rank | 1.3296943231441047 |
| redundant-row share | 0.24794745484400657 |
| complete / incomplete parent groups | 2,259 / 34 |

这批数据在阈值之前已经被看过，且有 34 个不完整 parent groups，所以只能是 descriptive threshold development，绝不能
冒充预注册确认。Target-522 确认只接受 Stage-A 公开聚合，且 Stage-A 必须给出 exact observed sibling-clique certificate。

## 冻结确认门

唯一材料性阈值为 `pair rows / incidence rank >= 6/5`。等价的 redundant-row share `>=1/6` 只作另一种展示，**不作为
第二道独立门**。两个互不重叠的 partition 都要单独通过：

| partition | minimum pairs | minimum physical runs | minimum tasks | max single-task pair share |
|---|---:|---:|---:|---:|
| acquisition | 100 | 40 | 12 | 7/20 |
| evaluation | 80 | 25 | 10 | 7/20 |

并且 Stage-A 自身全部 support gates 必须为真。分类固定为：

- 两图全部通过：`TARGET522_LINEAR_CONTRAST_ROW_INFLATION_CONFIRMED`；
- Stage-A support 完整但任一确认门失败：`...NOT_CONFIRMED`；
- Stage-A 任一 support gate 失败：`...AUDIT_LIMITED_SUPPORT`。

这是冻结图上的确定性 census arithmetic，不是标签性能抽样估计，因此不制造没有意义的置信区间。不得事后修改 threshold、
partition、tasks 或 graph。

## 解释边界

即使确认，也只允许说“两个未来 run-clean 图中，物化 pair-row 数相对这一特定 endpoint-incidence rank 有材料性膨胀”。
明确不声称：

- labels 统计独立；
- effective sample size 或 Shannon information；
- 任意 critic 的 feature-matrix rank；
- predictor efficacy 或 model scaling；
- D-opt / graph vertex sampling 的算法首创。

## 实现与复验

- 科学协议：`phase1/target522_linear_contrast_rank_audit_v1.json`，SHA-256=
  `3c8b8f87b43cae74a57c28d78e3428d824f54969051fadf5086810da467ad323`；
- execution：`phase1/target522_linear_contrast_rank_execution_v1.json`，SHA-256=
  `50baf5c7a31c9be8786e8f1cabce1f3b9d89834a0a0a508d6a76b5e4e99b41ac`；
- analyzer SHA-256=`120e55269fde767cdbe3f036bc28a6293788e72c83972529fbef9c48e0274c41`；
- independent verifier SHA-256=`92ab4533d72d8bd73b75e7ef266798ecf7d25ca4d454ada0571488028695ff93`；
- focused tests SHA-256=`a4e82a14b4f8d3e05174bc2639bafe22e46fec1d3ef5c3c05b7c0b8019818205`，
  当前 `17 passed`。

formal chain 在 Stage-A `COMPLETE` 前只检查 marker。激活后只打开公开 aggregate `producer_a/b.json`，不读取或整体 hash
Stage-A private files；随后 fresh exact-commit full tests、analyzer A/B、独立 verifier A/B、逐字节一致性、mode-0600、
file/network trace 和 manifest 全部必须通过。Stage-A 完成后本审计本身预计少于 10 秒，fresh full tests 约 2 分钟；真正 ETA
主要取决于 Target-522 还差的 physical runs。

本机全量测试在 collection 阶段因环境没有 `scipy` / `sklearn` 而出现 11 个既有 import errors；本项 focused 仍为
`17 passed`。这不是科学或代码通过门，正式部署必须使用远端固定 venv，并要求 fresh exact-commit 的完整
`phase1/tests` 全通过后才允许 monitor 启动。
