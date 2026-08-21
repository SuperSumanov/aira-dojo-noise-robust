# Decision-Corpus Evidence Index v5

正式状态：`INDEPENDENTLY_VERIFIED_SOURCE_ANSWERABILITY_EVIDENCE_INDEX`。控制 commit：
`fff9e9fb937390142b059818dde3c593ece144a8`。

v5 逐项继承 normalized-LF SHA-256=
`80450de3528fcaf2dc5edb5f54109ba30189f81e66c5715fbe755012d5de391b` 的 v4 八项证据，不修改旧
entry、artifact、assertion、claim 或边界；新增第九项 `source_decision_answerability`。

新增项直接绑定：

- 3,252-row `per_parent.csv` 的 hash、精确 header、行数与等宽性；
- 23-row `per_task.csv` 的 hash、精确 header、行数与等宽性；
- 正式 summary、独立 verifier receipt 与 producer hash manifest 的 hash 和 65 条 JSON assertions。

最终 index 含 9 个互异 estimands、26 个 JSON artifacts、3 个 bound files（既有 2,079-row edge JSONL 加
两份 answerability CSV）和 305 条 assertions。index normalized SHA-256=
`4bff2b9fa48f2b530de886ab6b799011e8c4aa48ed378cdee0959c8b087a1627`。

允许新增到 release contract 的结论只有：对全部 3,252 个固定 source parents，发布的 finite orientation
可认证 2,344 个唯一 winner；status-certified partial order 可认证 3,001 个、新增 657 个，all-parent
answerability=`0.9228167281672817`。这不是 predictor accuracy、search utility、完整 numeric total order 或
prospective effect；传递关系不是 logged agent comparisons，identity-unavailable parents 没有被插补。

builder×2 与不 import builder 的 verifier×2 逐字节一致。正式 focused=`7 passed, 1 skipped`，完整 phase
tests=`678 passed, 1 skipped, 25 warnings`；skip 仅因控制 commit 尚未包含正式 v5 output。产物回传后本地
checked-output gate 转为 `8 passed`。worktree 前后干净，两类秘密扫描均为 0，正式目录只读。

关键 SHA-256：

- `index.json`：`4bff2b9fa48f2b530de886ab6b799011e8c4aa48ed378cdee0959c8b087a1627`；
- `independent_verification.json`：`6a1a09cd3ca8d6b8e0ac6c729e8231adea2392db35825c1c11fb08d321a8bce1`；
- `SHA256SUMS`：`9b8339679e73bed8e3aec2ac4fcad0614e8f3d08be5eab8d57399cd648beb8c0`。

完整只读远端产物：

`/research/d7/spc/yzyang4/decision-corpus-evidence-index-v5/fff9e9f-v1`

该索引仍是 `AWAITING_FIRST960` 的 provisional release stack；它不能把尚未到达的 strict-future 效果写成已完成
结果，也不改变 score-channel 或 Qwen GPU 的既有批准门。
