# Decision Corpus Evidence Index v7（clean provenance）

本包是从公开 source commit `a83bebfdb8dcf59bea21a1b84269b2e87bf7a02e` 的 fresh detached
no-smudge Linux worktree 生成的正式件。它从最后未受 prediction-matrix 事故影响的 v5 重建，不读取或继承 v6；旧 v6、
withdrawn coverage matrices、task-balance v1/forward v1 与 ABC crosswalk v1 仍原样保留为历史审计记录。

## 正式结果

- status：`FORMAL_CLEAN_PROVENANCE_EVIDENCE_INDEX_PASS`；
- index：14 entries、37 JSON artifacts、3 bound files、434 exact assertions；
- builder A/B 与 non-importing verifier A/B 均逐字节一致；
- focused：`10 passed, 1 skipped`；完整 `phase1/tests`：`1127 passed, 1 skipped, 47 warnings`；
- production file trace 对 v6、两套 withdrawn matrix、task-balance v1、crosswalk v1、pair predictions、label/outcome
  路径的命中为 0；credential hits=0；
- GPU/API/model-fit/base-LLM update=`0/0/0/0`；
- formal index SHA-256=`d8cc9c60900ab41ff1df0e3aae3add29bbb922d5a32157957dcac5675fa31674`；
- independent verification SHA-256=`b0bcd3213be641dcf6832b08d6a47720189bcfacc72dca15276ed01fe191d128`；
- remote formal manifest SHA-256=`608c0a4f9ef5d1a3af5e6f3c3123bb515afba968f8f1524406d2c25cffcbbbe1`。

`index.json` 与 `independent_verification.json` 分别是 formal A 跑的逐字节拷贝；A/B equality 已写入
`formal_summary.json`。`remote_formal_SHA256SUMS` 是完整远端 formal root 的原始 manifest，本目录自己的
`SHA256SUMS` 只覆盖实际发布的文件。

## 可引用与不可引用

可引用：receipt-certified 2,755-pair common support、run→pair structural weighting shift、closure-time
opportunity-yield interpretation contract、task-balance debt 657→645 但仍未清零，以及完整的 provenance withdrawal chain。

不可引用：orientation/tie/margin/activation 分布、predictor accuracy/effect/search utility、first-960 closure、
single-drop robust magnitude、producer compliance、causal acquisition effect，或“v1 provenance 已追溯修复”。本包是
benchmark integrity 与 claim-boundary 正资产，不是新的 predictor 效果结果。
