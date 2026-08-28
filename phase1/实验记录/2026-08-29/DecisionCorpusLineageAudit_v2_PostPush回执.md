# Decision-Corpus lineage audit v2：发布后独立复验回执

日期：2026-08-29。被复验的公开 package commit=
`7e625c603c8c47f433af2967f66c5a7c4b82ba0f`；科学 source commit=
`25148420ee457018a1ee3740c4a1c42da830610d`。fresh detached root=
`/research/d7/spc/yzyang4/decision-corpus-lineage-audit-v2/postpush-7e625c6-v1`。

复验从远端 `fork/phase1-value-critic` 精确 tip checkout；curated package `MANIFEST.sha256` 16/16 通过，协议与
producer/verifier/test blob SHA 全部等于 `source_bindings.json`。fresh worktree 用本地 LFS object hydrate exact v11
Cards 后，focused/full=`13/1488 passed`（47 warnings）。重新运行的 producer 与 package `producer_a.json` 逐字节
相等；独立 verifier 与 package `verifier_a.json` 逐字节相等，并再次确认 15/15 hard、35/36 support、全局 relation=
parent-present/orphan/same-run-nonsibling/cross-run `7579/528/0/0`，唯一失败门仍为
`frozen:b2.maximum_single_run_pair_share`。

file/network trace 的 forbidden opens/network calls=`0/0`，package credential filename/content=`0/0`；prospective
values 未读，row-level release 未生成，GPU/API/model-fit/base-update=`0/0/0/0`。post-push `SHA256SUMS` 已逐文件
复核，manifest SHA-256=`4fba37aa41c7563d49b9226d80b9ecb814125972507a317992e3d79b1db0daa4`。
