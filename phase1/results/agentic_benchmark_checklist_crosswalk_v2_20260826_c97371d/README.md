# Agentic Benchmark Checklist Crosswalk v2（clean provenance）

本包从公开 source commit `c97371d7433b808933624b706a848a644991139c` 的 fresh detached no-smudge
Linux worktree 生成。v1 crosswalk 只作为 hash-pinned 人工 item/status 模板；其 catalog 指向的 v6、withdrawn coverage
matrix 和 task-balance v1 artifacts 均未打开，也未作为 v2 evidence。

## 正式结果

- status：`FORMAL_CLEAN_PROVENANCE_ABC_CROSSWALK_PASS`；
- 24 个 ABC items、29 个 clean evidence files；删除 6 个 tainted IDs，加入 11 个 clean IDs；
- 人工状态未升级：PASS_LOCAL/PARTIAL/INHERITED_UPSTREAM/NOT_APPLICABLE=`9/9/5/1`；
- builder A/B 与 non-importing verifier A/B 均逐字节一致；
- focused：`11 passed, 1 skipped`；完整 `phase1/tests`：`1144 passed, 1 skipped, 47 warnings`；
- source v1 template 在 production traces 中有 24 次 open records；removed evidence、prediction pair/value、label/outcome
  路径命中为 0；credential hits=0；
- GPU/API/model-fit/base-LLM update=`0/0/0/0`；
- crosswalk SHA-256=`65cbf6cf0b9e15d0c5821420f5ce1adbdd8b8749c42fa8fbcc0ccc217b1487ee`；
- independent verification SHA-256=`242ef697a7c78c1da332703f7a9fa6f289bfaaae69245d00fc0cdfbae535dd06`；
- remote formal manifest SHA-256=`1552c9111a7b4b173759db7249fdf67ef7bb758f6f82c224deb7a9b529effcef`。

`crosswalk.json` 与 `independent_verification.json` 是 formal A 跑的逐字节拷贝；A/B equality 见
`formal_summary.json`。`remote_formal_SHA256SUMS` 是完整远端 formal root manifest，本目录 `SHA256SUMS` 只覆盖发布文件。

## 解释边界

该 verifier 只认证 schema、24-item set/order、保守 status、引用闭包、路径安全和 evidence SHA-256。它不认证人工语义判断，
不计算 aggregate compliance score，也不把 PARTIAL/INHERITED/NOT_APPLICABLE 转成 PASS。clean crosswalk 是审计与论文
claim-discipline 资产，不是新的 predictor 效果、benchmark 总分或“已满足顶会标准”的证明。
