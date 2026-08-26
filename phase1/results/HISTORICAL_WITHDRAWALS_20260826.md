# Historical result withdrawals — 2026-08-26

为保持封存 manifest 与历史审计链，以下 result 目录不修改、不覆盖；其 README 中旧 attestation 仅代表当时记录，不再是
当前有效裁决。机器权威为 `phase1/prediction_matrix_downstream_taint_registry_v1.json`，方向权威为
`phase1/CURRENT_DIRECTION.md` 的 0GF/0GG。

撤回 strict-zero-prediction-value provenance：

- `prediction_escrow_coverage_7cda_20260825_6299865`；
- `task_balance_accrual_guard_7cda_20260825`；
- `task_balance_guard_forward_8579_20260826`；
- `task_balance_guard_forward_8579_formal_20260826`。

部分降级（仅受影响 evidence entry/pointer 撤回，其余条目不自动失效）：

- `decision_corpus_evidence_index_v6_20260825`；
- `agentic_benchmark_checklist_crosswalk_v1_20260825`。

替代件：

- common support：`prediction_receipt_common_support_8579_20260826_9f2cbe9`；
- task balance：`task_balance_structural_only_v2_8579_20260826_1b9b836`。

撤回原因是旧 matrix 打开并聚合 prediction-derived fields，却声明 `prediction_values_aggregated=false`。没有读取
prospective label/outcome/accuracy/search utility；旧数值不因此自动判错，但必须由合规替代链重新建立。数值一致也不
追溯修复旧 provenance。
