# Status-Certified Edge Manifest v1

正式状态：`VERIFIED_STATUS_CERTIFIED_EDGE_MANIFEST`。控制 commit：
`c9bfc21c1e8428787caf4e70db404a18990910bc`。

这是 0DC 已确认 aggregate partial-order 结果的结果后发布导出，不是第二次确认性实验。三份 v11 b0 pair 文件只用于
恢复每个 `(role,parent)` 的 finite endpoint ID 集合；`better/worse` 被立即视为无向集合，方向、gap、numeric score、
candidate code 与 prospective outcome 均不参与边生成。

## 可直接使用的边

`producer_a/edges.jsonl` 显式列出 2,079 条
`valid_child_id VALIDITY_DOMINANCE invalid_child_id` 关系，覆盖 902 个精确认证的 invalid children、1,498 个 finite
children、658 个 parents 和 14 个 tasks。每条边同时携带 role、task、run、parent、invalid category 与 source-journal
SHA-256。category 分解为：

- `EXECUTION_ERROR`：2,060 edges；
- `OFFICIAL_GRADE_ABSENT`：19 edges。

producer 逐 parent 复核 pair-row 数、无向 unique-edge 数、endpoint union 数与既有 source census；禁止 invalid child
出现在 finite endpoint 集，并要求全局 edge identity 唯一。独立 verifier 不 import producer，从固定输入重新构造全部
2,079 条边，最大差为 0。

## 强敏感性

结果后固定删除全部 `OFFICIAL_GRADE_ABSENT` edges，只保留更窄的 execution-failure 语义。剩余 2,060 条关系仍把
source coverage 从 5,897/9,755 提升到 7,957/9,755=`0.815684264479754`；绝对 gain=
`0.21117375704766786`，恢复原缺口的 `0.5339554173146708`。train/frozen/extension gain 分别为
`0.22004357298474944`、`0.18819351975144252`、`0.12658227848101267`；14 个支持任务中 11 个有正增益，
dominant-task share=`0.1883495145631068`。原 relation-count、overall、gap-recovery、train/frozen、task-support 和
集中度门全部保持通过。

这说明 headline 不依赖 9 个 grade-absent children，但它仍只是 validity partial order：不能声称 numeric-quality
ordering、完整 choice set、MAR、predictor accuracy 或 search utility。

## 完整性

producer×2 与 verifier×2 均逐字节一致；focused=`5 passed`，完整 phase tests=`654 passed, 25 warnings`；
forbidden scientific path、秘密扫描与 worktree 漂移均为 0。首次 formal attempt 已完成科学重构，但 runner 在零路径
命中时因 shell `pipefail` 将空过滤误判为失败，故未执行全回归；修复仅让空过滤返回零，第二个 commit 从全新 worktree
完整重跑，旧半成品保留且不复用。

关键 SHA-256：

- `edges.jsonl`：`dda9f121dc32a1ef309992b0bec61934864e35ec337385bb2f5c0c548b258a3d`；
- `summary.json`：`5dd53823ca6e432e4ab593a1267c9a73bce954be977deceb6de63c4ed90ea84b`；
- `verification_a.json`：`ae280675707b38fad4da3042296b90c7a2fd3c744f484ba482703c542d0e5abf`；
- 完整远端 `SHA256SUMS`：`d4b0da8f296b8dd02a297c6ba37faa45e9e2bd711efd913f218e78babdc061b5`。

完整只读远端产物：

`/research/d7/spc/yzyang4/status-certified-edge-manifest/c9bfc21-v1`

本 README 是回传后的解释文件，不属于远端只读 `SHA256SUMS` payload。
