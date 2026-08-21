# Source Retention：run-cluster robustness v1 冻结

日期：2026-08-21。状态：`POST_RESULT_ROBUSTNESS_PREREGISTERED_NOT_RUN`。

## 为什么必须补这一刀

v1 已按结果前协议在 15 个任务上得到 train→frozen parent-equal retention profile rho=`0.8151043`。该结论的
task bootstrap 处理了任务间不确定性，但 task 内先按 parent 平均；同一 physical run 可贡献多个 parent，因而
reviewer 可以合理质疑 parent-rich runs 是否影响 task profile。本文档在读取 per-run retention profile 之前冻结，
只做对 v1 的 cluster 强度压力测试，不修改、替代或追救 v1 headline。

## 固定输入与集合

- 输入仍是 v1 使用的 3,252-parent `per_parent.csv`，SHA-256=
  `75c02200d1f9b8d87614762a9f2b71ba3c678d598ff28bc237c8a46a4bc36d03`；
- 固定 task universe 恰为 v1 结果前门选出的 15 个任务，完整名单写入 protocol；不得新增/删除任务追结果；
- 进一步的 run 支持门在看 run counts 前固定为 train≥5、frozen≥3 distinct physical runs；至少 10 个任务过门；
- extension 不进入任何效果量；不读取 code、numeric outcome、pair orientation、prediction 或 prospective vault。

## Run-equal headline

每个 `(role,task,run)` 内先平均 parent-level `finite_source_retention`，然后对该 task 的 runs 等权平均。headline
为 train/frozen 两个 run-equal task profiles 的 Spearman rho。

推断固定为：

1. 100,000 次 frozen task-profile 双侧置换，seed=`20260824`；
2. 20,000 次 task×run hierarchical bootstrap，seed=`20260823`：先按 task 成对重采样，再在每个被抽中的
   task 内分别对 train/frozen runs 有放回重采样；不在 run 内把 parents 当独立样本；
3. 报告 bootstrap 有效率与 percentile 95% CI；
4. 对点估计逐任务 leave-one-task-out；
5. v1 task 集按本轮 train run-equal profile 定义 top/bottom tertiles，报告 frozen run-equal 差，只作解释。

## 冻结裁决

只有以下全部成立，才允许 `RUN_CLUSTER_ROBUST_TASK_RETENTION_TRANSPORT`：

- robust tasks≥10；
- rho≥0.50；
- permutation p<0.05；
- hierarchical bootstrap 有效率≥0.90 且 95% CI 下界>0；
- 所有 leave-one-task-out rho>0。

否则为 `TASK_RETENTION_TRANSPORT_NOT_RUN_CLUSTER_ROBUST`；不得改 run 门、task universe、metric、seed、
bootstrap 层级或改回 parent weighting 追救。若失败，v1 仍作为 parent-weighted描述性结果保留，但正文不得写成
run-cluster robust。

通过也只支持：在当前 release roles 中，task-conditioned source retention 对 run 等权和 task×run 不确定性稳健。
仍不支持 MAR/非 MAR 的个体机制、task 因果效应、完整 choice set、missing numeric outcome、预测器或搜索收益。

正式矩阵为 producer×2 + 不 import producer 的 verifier×2；CPU-only、GPU/API/base-LLM update=0；focused 与
全套测试、逐字节复跑、syscall forbidden-path 与两类秘密扫描全部必须通过。
