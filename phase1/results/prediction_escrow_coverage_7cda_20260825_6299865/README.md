# Prediction escrow common support：7cda snapshot

结果盲 WL 四臂与 transition 三臂在 snapshot
`7cdaefcf2be7786442e1af1f4d0b4012edee708932f1fad31e174c0dcaf803a1` 上各覆盖 2,635 个 canonical sibling
pairs、334 个 runs、30 个 tasks。独立复核得到 intersection=union=2,635、IoU=1.0，且 2,635 对 left/right
方向全部一致；matrix SHA-256=`be63fbe02c63c306bb488aa30416de7260e83e4701bdce3ed3f1d8843fd6f6b7`。

两套 activation 不能混写：463 对同时位于两者 activation 后，507 对仅位于 WL activation 后，1,665 对在两者中
均为 support-only。transition 的 strict-effect-eligible 仅 399 对；对应独立 transition receipt 为 52 runs、17 tasks，
因此仍是 `TRANSITION_ESCROW_INSUFFICIENT_FUTURE_SUPPORT`。

正式链 focused/full=`10/1002 passed`，formal `SHA256SUMS` 文件自身 SHA-256=
`f67c1ecac1bea3cd743b9667d222a49867109e8f97e8983ea4634fe69f391a26`，credential filename/content hits=`0/0`。
该结果证明七臂未来可做严格 paired comparison；它没有聚合 prediction values，没有读取 truth，也不提供 accuracy、方法
优越性、runtime/cost 或 search utility 结论。
