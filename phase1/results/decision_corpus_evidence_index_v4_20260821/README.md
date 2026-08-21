# Decision-Corpus Evidence Index v4

正式状态：`INDEPENDENTLY_VERIFIED_FAILURE_AWARE_EVIDENCE_INDEX`。控制 commit：
`832947a6d7bf43da57dcb3702bb713a3b226e47e`。

v4 逐项继承 normalized-LF SHA-256=
`424f06b161086972fedf55d5e8e06e22d92c21e1558a04b2dd6c55e3cb637b49` 的 v3 七项证据，不修改旧
entry、artifact、assertion、claim 或边界；新增第八项 `status_certified_partial_order`。

新增项不仅绑定 summary 与独立 verifier，还直接绑定 2,079-line `edges.jsonl` 的 normalized hash 和逐行 JSON 合法性，
再以 formal manifest 交叉绑定 edge/summary hashes。最终 index 含 8 个互异 estimands、23 个 JSON artifacts、1 个
bound JSONL 和 240 条 dotted/exact-key assertions。index normalized SHA-256=
`80450de3528fcaf2dc5edb5f54109ba30189f81e66c5715fbe755012d5de391b`。

允许新增到 release contract 的结论只有：2,079 条 provenance-certified validity edges 已显式发布；更窄的 2,060 条
execution-error-only 子集仍通过原全部材料门。validity relation 不是 numeric-quality total order；unknown 与其他未解析
关系继续 unresolved；不证明 complete choice set、MAR、predictor/search utility、prospective effect 或方法 novelty。

builder×2 与不 import producer function 的 verifier×2 逐字节一致；focused=`6 passed, 1 skipped`，完整 phase tests=
`660 passed, 1 skipped, 25 warnings`。skip 是控制 commit 尚未含正式 v4 输出时的 checked-output test；回传正式目录后
该测试在本地转为通过。worktree 前后干净，两类秘密扫描均为 0，正式目录只读。

关键 SHA-256：

- `index.json`：`80450de3528fcaf2dc5edb5f54109ba30189f81e66c5715fbe755012d5de391b`；
- `independent_verification.json`：`7ff399e5a9f0cb1ca5c6cbe888f209a56e9a869c7cf862c15f4f6ccff74d9f0a`；
- `SHA256SUMS`：`8a76c8d04d02f24cfaca13aaf086c0580284417dbdf7dbf9588957167484cd58`。

完整只读远端产物：

`/research/d7/spc/yzyang4/decision-corpus-evidence-index-v4/832947a-v1`

该索引仍是 `AWAITING_FIRST960` 的 provisional release stack；它不能把尚未到达的前瞻效果写成已完成结果。
