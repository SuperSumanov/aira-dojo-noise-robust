# Task Balance Structural-Only：887 snapshot 前瞻外延预注册

冻结时间：2026-08-28T04:11:58Z。本文写在读取 `887491a...` 的逐任务 pair 分布、dominant count/share、
debt 与 compliance 状态之前。

## 问题与固定人口

唯一问题是：在结果盲、按时间序固定的 435-run provisional first-960 snapshot 上，既有 25% dominant-task
pair-share guard 是通过、改善但仍失败，还是没有改善。固定 snapshot 为
`887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697`；已知且允许使用的结果盲总量为
435 runs、3,053 canonical sibling pairs、34 tasks。

本实验逐字节复用 structural-only v2 的 7cda guard、整数 debt 恒等式、producer A/B、non-importing verifier A/B
及所有安全门。当前输入只允许 accumulator summary、summary-bound first-960 ledger 和已独立认证的 3,053-pair
common-support receipt；三者 SHA-256 已写入
`phase1/task_balance_structural_extension_887_protocol_v1.json`。

## 结果前解释顺序

1. 若 dominant share≤0.25 且 debt=0，记为 `CAP_PASS`。
2. 若 cap 仍失败，但 share 与 debt 均低于已公开 ad0b 参考（850/2,884，debt=516），记为
   `DIRECTIONAL_BALANCE_GAIN_ONLY`。
3. 其余记为 `NO_BALANCE_GAIN`。

第二种只允许写“结构债务描述性下降、硬门仍失败”，不得写自然摄取导致改善、producer 遵从策略或 predictor 变好。
无论结果方向如何，必须报告 dominant/non-dominant 增量、精确 debt delta、cap、chronology、共同支持与全部失败史。

## 禁止项与失败门

禁止读取 prediction pair/value/matrix、label、grade、outcome、winner、accuracy、effect、utility 与 raw archive payload。
任一 hash/path/snapshot 不一致、dominant task 改变、结构总量不一致、chronology 失败、A/B 不一致、forbidden open 或
credential hit 都 fail closed。GPU/API/model-fit/base-update 固定为 `0/0/0/0`。

这是一项 Decision Corpus benchmark-quality 审计，不是方法效果实验；即使 `CAP_PASS` 也不会授权揭盲、replay 或 GPU。
