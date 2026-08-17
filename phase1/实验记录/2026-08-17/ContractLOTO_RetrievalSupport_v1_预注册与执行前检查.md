# Contract LOTO Retrieval Support v1：预注册与执行前检查

日期：2026-08-17。状态：`NOT RUN`。本文件冻结在计算 20 个 public-contract 任务的最近邻之前，
不改变 score-channel 唯一主实验，不授权 GPU/API 或付费三臂实验。

## 问题与主张边界

公开 artifact contract 的**去名称结构**是否足以在 leave-one-task-out 条件下，把新任务连到同类型且有
run-clean evaluator-verified 成功经验的其他任务？通过只支持“存在 task-held-out retrieval 素材”，不支持
memory/contract 提高 coverage、分数或搜索速度。

## 十三项执行前检查

1. Goal：20 个有 public contract 的任务逐一 held out，另 5 个 contract 缺失任务必须 abstain。
2. Inputs：contract audit SHA `166eaa6770b4abd6118f0168abc2b6e8afb5633847af48628f3f637ad9b56bdb`；
   memory audit SHA `769acc3d198dadb5643e3557f57c738967806546e212c258d0de51ad794a53f0`。
3. Fingerprint：只用 `log1p(row_count)`、`log1p(column_count)`、各 placeholder type 的列占比和
   empty-cell 比例；不用任务名、列名、description、代码或 score。
4. Evaluation label：task type 只作事后标签，绝不进入 fingerprint 或距离。
5. LOTO：每个 query 的缩放范围只由另外 19 个任务确定；query clip 到训练范围。
6. Distance：各维 train-range scaled L1 的算术均值；最近距离 `1e-12` 内全部视作 tie，等权计分。
7. Null：固定 seed `20260817`，保持 7/9/4 类型数的 100,000 次标签置换，单侧加一 p 值。
8. Primary：mean same-type nearest-neighbor credit >=0.55 且 permutation p<=0.05。
9. Heterogeneity：至少 2/3 task types 的 credit >=0.50；至少 5 个不同任务被检索；任一任务检索质量占比 <=0.25。
10. Memory availability：至少 90% query 的最近邻集合合计有 >=5 个 writer-marked best episodes。
11. Controls：5 个 unsupported image tasks 必须 abstain；ties 不按 task ID 破坏；测试验证改任务/列名不改 fingerprint。
12. Resources：CPU-only，预计 <2 分钟；GPU=0，API=0，前瞻 outcome=0，底座更新=0。
13. Stop：任一门失败即写 `INSUFFICIENT`，不在结果后增加特征、改距离、改阈值或引入列名救结果。
