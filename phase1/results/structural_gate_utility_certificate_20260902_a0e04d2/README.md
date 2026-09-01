# Structural Gate Utility Certificate（2026-09-02）

这是对四份已发布 aggregate evidence package 的**事后逻辑合成**，目标是回答一个窄而重要的
benchmark-curation 问题：当前结构校验是否曾删掉某个受影响 competition 的最后一份可用 checkpoint 支持。

在已结算的 283-archive 状态中，14 个结构拒绝触及 7 个匿名 competition：其中 6 个仍有 accepted eligible
support，合计覆盖 20 个 accepted archives、94 个 physical runs、92 个 eligible runs 和 2,558 个 endpoints；
每个被保留 competition 至少有 4 个 eligible runs 和 50 个 endpoints。唯一没有 accepted support 的 competition
对应一个零 checkpoint archive：发现 2 个 run roots，但两者都是 live-only，checkpoint runs 为 0。因此在这 7 个
已观察 competition 中，结构门导致“最后可用 checkpoint-derived support 被清空”的观测计数为 **0**。

这给出一条可写进论文的数据工程正结论：在当前审计状态里，结构校验表现为 support-preserving quality gate；
它保留已有可用支持，而唯一无支持事件本身没有 checkpoint 数据。机器可读主件是 `certificate.json`，独立实现的
核验结果是 `independent_verification.json`。

边界必须同时保留：这不是新的独立实验，也不是 fully blind confirmation；它不能外推未来语料稳定性，不能宣称
结构门具有普适无损定理，也没有测试修复 malformed archive 后是否可恢复数据。它不涉及 predictor accuracy、
scaling、search utility、因果方法效果或 task 白/黑名单。因此 `counts_as_distinct_claim_evidence=false`，应作为
已有 0KI/0KV/0KW/zero-checkpoint 证据的 paper-facing certificate，而不是第五项独立科学结果。

正式运行固定在 commit `a0e04d27bcf900c2a1293f8ffad38d5104f6d3a3`。聚焦/全库测试分别为
`12 passed` / `2013 passed`（48 warnings）；builder A/B、非导入 verifier A/B、trace 重建和输入 hash
before/after 均逐字节一致。远端 root 为只读 mode `0500`，37-member manifest SHA-256 为
`1078227f2b9591ae39041da26b9c2cea4930c4775c15799f1b19d36c15d45d82`；forbidden open、network、credential
filename/content hits 均为 0。前瞻 label/outcome/prediction、身份值和学长 raw archives 未读，GPU/API/model fit/
base update=`0/0/0/0`。

前三次未产生任何 scientific output：v1 在 checkout 前因缺少 Git LFS filter 以 rc=128 停止；v2 的交互连接中断后
最终记录同一 post-checkout hook rc=2；v3 的持久化运行再次确认该 hook 失败。v4 只对单次 `worktree add` 使用
空 hooks path，未删除或修改远端仓库钩子。完整记录见 `failure_history.json`。
