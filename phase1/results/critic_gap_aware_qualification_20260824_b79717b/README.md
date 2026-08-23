# Gap-aware critic train/dev qualification receipt

正式状态：`RETROSPECTIVE_DEV_GAP_AWARE_NO_UNLOCK`。

固定 commit=`b79717b3956a1b546943708a4c62e65841ffb663`，contract SHA-256=
`f411c0f732df12158e8c683ddbb94cea107d7673b40b8305ee5b83c8219ef4f8`。headline 的
`gap_weighted - binary` 为 `+0.01863809409732331`、CI
`[-0.02676049343489505,+0.066027790932867]`；相对 gap-permuted control 为
`-0.0035816185092047113`、CI `[-0.04433344970163935,+0.0395666585234688]`。因此不解锁 future
gap-aware escrow，也禁止同 dev 调参重试。

`formal_b79717b.tar.gz` 是远端正式目录的确定性完整归档，SHA-256=
`0858d49ddb7c896f6bf6d3cbd4966d3dd1840127b89f23ad89db07ea8e3a6372`。解包后在 `formal/` 内执行
`sha256sum -c SHA256SUMS`；该检查已在远端 post-audit、本地原目录和归档重解包后三次全量通过。
`SHA256SUMS` 自身 SHA-256=`49ab567a5fb109e2928b246d665859d2e3fdcef8cf675a25eac41004216988a9`，另以
`formal_SHA256SUMS.txt` 展开提供。归档包含两份完整 producer、两份独立 source-refit verifier、逐 pair/逐 task
结果、测试、资源、环境、安全与可重复性回执；headline summary/arm/verifier 另行展开，便于直接查看。post-audit
文件 SHA-256=`3f3860366e90ff6b8a6e75eb4d9ce09d1583a409afead053adb860d4f01cf1ff`。

`b79717b-v1.sibling_structure.json` 保留一次 postflight 的错误假设：它把 synthetic cross-run Draft 也要求为 physical
sibling，因此按预期失败。`b79717b-v1.semantic_structure_v2.json` 按冻结语义纠正并通过，SHA-256=
`7726c248f2850fa333915b9ce8e495fd86b83eb5d1408d58b6abe136d6dd17d6`；Improve train/dev 全部是同-run lineage
sibling，Draft 保留 released-group 语义，并再次确认已知的 8 个 train/dev Draft-parent overlap。

科学解释与失败链见 `phase1/实验记录/2026-08-24/GapAwareCritic_TrainDev资格实验_正式裁决.md`。
