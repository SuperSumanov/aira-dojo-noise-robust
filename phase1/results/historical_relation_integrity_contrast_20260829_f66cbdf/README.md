# Historical Relation Integrity Contrast v1

这是一个 aggregate-only、known-result descriptive synthesis 发布包。它把三个已经独立发布的历史证书绑定为一条可复验链：

1. canonical v11 的 8,107/8,107 rows 均为 lineage-direct，hard gates 15/15；
2. mixed 0819 只有 1,270/7,644 rows 是 verified direct siblings，原 taxonomy hard gates 13/15，train/test
   referenced-run overlap 为 96；
3. deterministic direct-sibling quarantine 保留 1,270 rows、隔离 6,374 rows；repair certificate hard gates
   16/16、support compatibility gates 8/8，referenced-run overlap 为 0。

另有 743/743 parent-partition mismatches 位于 cross-run stratum。三套 gate schemas 相关但不相同，所以这些 pass counts
不得当成共同标尺比较；本包也不是 calibrated sensitivity/specificity、一般审计方法首创、causal resource comparison、
predictor effect/scaling、search utility 或 prospective confirmation。

权威 source commit 是 `f66cbdf10989da2e1242964259f31fb8d399db3e`。formal/postflight manifest SHA-256 分别为
`ab2b6fa69fa6705dbd442488067b63d0aea63eb6dc9c326a8bd0cef08087af54` 和
`b50a9a2941b360d5ca40b1de8c3887512b4a9ef80ac1b1969e4864ab49f57b9e`。formal 的 focused/full tests 为
34/1510 passed；producer/verifier A/B 逐字节一致，forbidden open/network/credential hits 均为 0。

本包不包含 row identities、pair orientations、labels、outcomes、predictions、accuracy 或 search utility；没有打开 senior raw
archives 或 prospective first-960/Target-300 values，GPU/API/model-fit/base-update 均为 0。
