# Run-Split Breadth Pareto Falsification v1：Post-Push 回执

日期：2026-08-29

公开结果提交 `a38b6f2f299b09a384f2f4a1edc290f97548d82d` 已从远端 `fork/phase1-value-critic` fetch 到 fresh detached Linux worktree，并完成独立 post-push 复验。remote root：

`/research/d7/spc/yzyang4/historical-run-split-breadth-pareto/postpush-a38b6f2-r1`

## 精确回执

- fetched commit 与请求 commit 均为 `a38b6f2f299b09a384f2f4a1edc290f97548d82d`；
- 正式结果包 `SHA256SUMS` 的 13 个成员全部通过；
- aggregate result SHA-256：`f1d8054ccc3e0d50f77a3ff4be29480f99ab0dbc51a6e1e510853da63c06e042`；
- independent verification SHA-256：`9025f2e5f3254421a6e1015ef4218fb60cec6ce6c5723307863c505c403f991b`；
- focused tests：`37 passed in 0.69s`；
- full tests：`1588 passed, 47 warnings in 91.41s (0:01:31)`；
- changed files：16；credential filename/blob hits=`0/0`；
- post-push root manifest 共 11 个成员，其 `SHA256SUMS` SHA-256 为 `8aca13de388810b7f3f935b886256462d1c236259852404be59d703f225b8cf1`；本地回收后再次计算得到同一值；
- `prospective_values_read=false`、`senior_test_rows_used=false`、GPU/API/model-fit/base-update=`0/0/0/0`；
- 完成时间：`2026-08-29T01:44:45Z`。

`COMPLETE` 存在、`FAILED_RC` 不存在，PID 已退出；本地重新执行远端 `SHA256SUMS` 的 11 项校验全部通过。该回执只确认公开提交可复现，不改变 0IQ 的科学裁决：fold0 两个固定 yield gate 失败，强 free-Pareto 主张不成立。
