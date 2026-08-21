# Decision-Corpus evidence index v3

正式状态：`INDEPENDENTLY_VERIFIED_OBSERVABILITY_AWARE_EVIDENCE_INDEX`。控制 commit：
`ce5c558509b1f481f9e9df1212d9f00c3cf00bce`。

v3 不改变 v2 的六个 estimand，而是新增第七项 `decision_observability`，把已经正式验证的 release funnel 接入同一份
机器可核验证据合同。最终 index 共 7 个条目、20 份 JSON artifact、181 项 dotted assertions；v2 source index、漏斗
summary 和独立 verifier 都由固定 normalized-LF SHA-256 锁定。

新增条目允许的正结论是：在完整的 3,252-parent census 中，9,088 个 source child slots 到 finite 阶段保留 7,760
个，child loss=`0.14612676056338025`；declared `C(n,2)` pair capacity 从 9,755 降到 5,998，loss=
`0.3851358277806253`，组合放大=`2.6356283154144×`。finite capacity 中发布 5,897 条 unique edges，coverage=
`0.9831610536845615`。这把 source opportunity registry、task-conditioned retention 与 observability denominator 连接成
一条可复核的 D&B 数据主张。

强制边界也进入机器合同：`C(n,2)` 不是 agent 实际比较日志；全部 3,252 parents 仍保留 finite/published decision，
禁止写成“38.5% 决策点消失”；不恢复完整 labeled choice set，不假定 MAR，也不证明 predictor accuracy、search
utility、因果性或 prospective effect。

builder×2 与不 import builder 的 verifier×2 均逐字节一致。正式 focused tests=`5 passed, 1 skipped`；skip 只因为
控制 commit 中尚未包含随后回传的正式 index。完整 phase tests=`643 passed, 1 skipped, 25 warnings`；worktree 前后
干净，两类秘密扫描与正式可写文件均为 0。index normalized SHA-256=
`424f06b161086972fedf55d5e8e06e22d92c21e1558a04b2dd6c55e3cb637b49`，独立 verifier SHA-256=
`e20dbc8c1ba69e8a3ffffb4552d47f9b5632b7cc69aed32e0972680d85d2a793`，正式 `SHA256SUMS` SHA-256=
`48b5b56698ac9f1c3bb285dddc1887f64d87002cf1f1079d6bb28db91fd403ee`。本目录回传的 30 个 payload 文件全部通过
`SHA256SUMS`，无缺失或不一致。

完整只读远端产物：

`/research/d7/spc/yzyang4/decision-corpus-evidence-index-v3/ce5c558-v1`

本 README 是回传后的解释文件，不属于远端只读 `SHA256SUMS` payload。

