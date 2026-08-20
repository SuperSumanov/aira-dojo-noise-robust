# Prospective 0819 intake + WL escrow receipt

日期：2026-08-21。状态：`BATCH_RESOLVED`、`CONFIRMATORY_COHORT_COLLECTING`、
`WL_GRAPH_ESCROW_APPEND_INDEPENDENTLY_VERIFIED`。

固定 8 个 0819 archives 最终为 7 committed / 1 rejected；Plant rejection 由 4/4 checkpoint journals 的
task-identity cardinality=0 支持。最终 snapshot=
`83ab1d681ed863d2374a6648df4801e6dbd6fb80d89f4f20cec8d46de1d5c047`，结构清单为 249 runs /
6,471 endpoints / 1,665 canonical sibling pairs / 26 tasks。first-960 尚差 711 runs，vault 未开。

固定 WL scorer 对同一 snapshot 完成 append-only 预测：旧 5,643 endpoints / 223 runs / 1,473 pairs 每行不变，
新增 828 endpoints / 26 runs / 192 pairs；独立四臂重算最大差均为 0.0。所有 runs 都在 activation 前开始生成，
所以 strict post-activation inventory 为 0；没有 accuracy 或其他 effect metric。

目录中的小型回执均直接来自远端正式产物：

- `batch_resolved_hashcheck.json`：八包状态与全源哈希，SHA256=
  `e1dade98a6a21acb87a6f07e490a3888879cd3f62bd64fb38cd04a3e1c60ba9b`；
- `diagnostic_a.json`：Plant credential-first identity 审计，SHA256=
  `8d05bb39325855ce1d3ed3ac244e3095522c2c0a40fdc6494119e855bc19f2ad`；
- `structural_gate_a.json`：独立结构门，SHA256=
  `d1d8388207ce5210867eb321c098c80b5131ce7d75bb0c798a398737754d84ce`；
- `summary.json`：WL artifact summary，SHA256=
  `14910d4db549df5dd12e9af510ed142d2a74bae176d0293cb9edc938a1a250e0`；
- `independent_verification.json`：不 import producer 的重算，SHA256=
  `2834564d3df477f309fc8d023a571757d664819c04b6ca3b154751e46a69cf03`；
- `append_verification_a.json`：append/trace/credential 双跑之一，SHA256=
  `1de6fa1657de0958c5e4be361110aff19a7353f15b707e7a4fe5f10110d3e855`；
- `full_artifacts.tar.gz`：完整 WL artifact、两份 syscall trace、运行时间、双 append verification 与
  `SHA256SUMS`，由 Git LFS 管理；远端生成与本地下载后重算 SHA256 均为
  `b3226d50f4dc652091df458d2a5ae5d5325d36f4e653c497d11ca6baf14f518b`。

append verifier 扫描 9 个目标文件 / 7,484,849 bytes，credential-shape matches=0；两份 trace 共 18,094 行，
forbidden-path hits=0。完整压缩包的内层文件 SHA 见 `SHA256SUMS`。
