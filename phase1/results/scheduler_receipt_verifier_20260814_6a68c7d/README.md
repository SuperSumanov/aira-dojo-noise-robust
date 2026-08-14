# Scheduler receipt consistency verifier：远端验收

## 裁决

在精确 source commit `6a68c7dd7cdcf2fe5faf25017b3ef8bcb3a1d4b5` 的全新 Linux worktree 上：

- 相关聚焦测试：`19 passed in 0.39s`；
- 完整 `phase1/tests`：`275 passed in 25.48s`；
- 验收前安全扫描：3 个文件，可疑文件名 0、高置信凭据文件 0；
- 下载后按 `artifact_manifest.sha256` 复核：5 个文件，hash mismatch=0。

状态：`VERIFIED_SCHEDULER_RECEIPT_CONSISTENCY_IMPLEMENTATION`。

这是 0 GPU、0 API、0 outcome 的实现验收。它不代表 scheduler 已接入，也不代表生产因果数据已经采到。

## 实现真正验证的内容

`verify_randomized_sibling_production_receipts.py` 不导入 assignment producer，而是先借助独立 assignment verifier
重建 frozen assignment，再验证：

1. 每个声明 eligible set 的 SHA-256 top-m 无放回随机化精确重建 selected parents；
2. parent 的 receipt hash 与 `m/n` propensity 精确匹配；
3. committed budget receipt 精确绑定 assignment manifest/summary；
4. 每个 assignment ID 一对一替换一个标准生产 slot，并占用一个唯一 randomized slot；
5. 标准 slot 减少量、随机 slot 增加量与总 slot 守恒同时成立；
6. outcome-bearing key、凭据形状、非 canonical JSON、重复 parent/slot、时间逆序与哈希漂移均 fail-closed。

## 仍未关闭的两道生产门

即使 synthetic receipt 一致，输出仍强制：

- `eligible_stream_completeness_verified=false`；
- `external_scheduler_receipt_authenticity_verified=false`；
- `upstream_selection_probability_verified_by_assignment=false`；
- `actual_production_budget_decrement_verified=false`；
- `production_activation_authorized=false`；
- `causal_claim_allowed=false`。

当前只允许称：从 scheduler **声明的** eligible sets 重建了概率，且 committed receipt 的预算账内部守恒。
必须先取得实际 scheduler 的 append-only 事件流与预 outcome sealing 证据，才能考虑真实接入。

## 本地环境差异

同一提交在 Windows 本地完整测试得到 `268 passed, 5 skipped, 2 failed`；两项失败均为
既有 `task_topcenter_rank` 测试导入 SciPy 时发生 `ModuleNotFoundError`。新增与相邻协议聚焦测试均通过。
Linux 完整环境的 `275 passed` 排除了代码回归；本地失败没有被删除或写成通过。

## 证据

- `focused_tests.txt`；
- `full_phase1_tests.txt`；
- `runtime_context.txt`；
- `safety_audit.txt`；
- `artifact_manifest.sha256`。
