# Decision-Corpus evidence index v4：正式裁决

结论：通过，状态为 `INDEPENDENTLY_VERIFIED_FAILURE_AWARE_EVIDENCE_INDEX`。

控制 commit `832947a6d7bf43da57dcb3702bb713a3b226e47e` 严格继承 v3 的七个 estimands，并新增
`status_certified_partial_order`。正式结果为 8 entries、23 JSON artifacts、1 个直接绑定的 2,079-line edge JSONL、
240 条 assertions；index normalized SHA-256=
`80450de3528fcaf2dc5edb5f54109ba30189f81e66c5715fbe755012d5de391b`。

## 新增合同解决了什么

0DD 已给出显式边文件，但若统一 evidence index 只引用其 summary，读者仍无法由 index 检查实际边文件是否被替换。
v4 同时固定 edge normalized hash、line count、逐行 JSON 对象性、formal edge/summary manifest、summary assertions 与独立
verifier assertions。因而“2,079 条显式边”从报告文字变成可机器验证的 release contract。

继承的七项完全来自固定 v3 index；builder 与 verifier 都要求 source hash、protocol/status 和 entry 顺序精确一致，不能
在 v4 中悄悄改写旧结论。独立 verifier 不 import builder implementation，逐项重建相同 index，并再次打开全部 23 个
JSON artifacts 和 bound JSONL 做 hash/assertion 检查。

## 边界

v4 不产生新科学效果，只包装已确认资产。允许说 failure-aware partial order 已显式发布，且 execution-error-only 子集不掉
材料门；禁止说 numeric-quality total order、complete choice set、MAR、predictor/search utility、causality、prospective
effect、算法 novelty 或 first/only。整体状态保留 `AWAITING_FIRST960`，不能用 evidence packaging 替代前瞻确认。

## 复核

builder×2/verifier×2 byte-identical；focused=`6 passed, 1 skipped`，全部 phase tests=
`660 passed, 1 skipped, 25 warnings`。控制 commit 内尚无 formal v4 output，因此 checked-output 测试按设计 skip；正式
产物回传后本地复跑应转为全过。worktree 漂移与两类秘密扫描均为 0，远端目录只读；`SHA256SUMS` 自检全过。

该结果使 D&B 主资产形成八项统一、可机器核验的 evidence stack；不改变 strict-future score-channel 主实验、first-960
closure 或 clean Qwen 预算门。
