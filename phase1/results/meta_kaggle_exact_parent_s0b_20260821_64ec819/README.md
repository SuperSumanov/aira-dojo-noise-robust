# Meta Kaggle exact-parent human-fork S0b 正式裁决

状态：`IDENTITY_UNAVAILABLE`。结果来自 source commit
`64ec81945b19f232968391a0b10d0772b9895641` 的两次 producer 和两次不 import producer 的独立 verifier；
producer 与 verifier 各自的重现性 diff 都是 0 bytes。7 个 focused tests 与全部 phase1 tests 分别为
`7 passed`、`611 passed, 25 warnings`。独立 verifier 重新扫描 1,946,556 条 Kernels、18,979,184 条
KernelVersions、5,526,938 条 competition links 和 12,066 条 Competitions 后确认
`verified=true`、`verified_status=IDENTITY_UNAVAILABLE`。

正式输入中有 391,175 条 explicit-fork rows，其中 748 条 malformed，得到 390,427 条可解析 edge；但这
390,427 条 edge 的 child `FirstKernelVersionId` 对应行都没有让 `ParentScriptVersionId` 与
`Kernels.ForkParentKernelVersionId` 一致，direct-parent agreement=`0.0`。同时有 362,922 条 child
first-version 的 `VersionNumber != 1`，所需 580,333 个 version IDs 只找到 537,972 个、缺 42,361 个。
因此 base-valid fork edges、canonical pairs、eligible parent groups 均为 0，原先冻结的身份与支持门全部未过。

该裁决只说明：公开、过滤后的 Meta Kaggle snapshot 不能在我们的双字段合同下识别 exact-parent sibling
estimand；它不说明 human forks 没有 future-potential signal。按结果前 stop rule，不删除一致性门、不把
`KernelVersionKernelSources` 改作 fork proxy、不按 outcome 换 child，也不打开 S1。`Submissions.csv` 仍只在
S0a 读取过 header，正式 S0b 使用 outcome rows=0、notebook code=0、model fit=0、GPU/API=0。

完整正式产物保持只读：
`/research/d7/spc/yzyang4/meta-kaggle-exact-parent-s0b/64ec819-v1`。本目录的小型回执均按该目录的
`output_manifest.sha256` 核验；本地与远端 manifest SHA-256 均为
`190c022651f5c33c71faa41c3a58da5add72dd291e16c7ecdbeacebcb755036d`，所复制文件的逐文件 mismatch=0。

关键文件：

- `summary.json`：producer summary，SHA-256
  `b1d3a10afc4e6e2461a3d8595227e03f95b519eb47b6e6bae9aeb23801f2dd66`；
- `independent_verification.json`：独立重建，SHA-256
  `a43fe3abde5e33df99521477c31b83f1157b1c80d5bd0e2d4b1cb7ac292b29e5`；
- `producer_manifest.json`：producer 内层 manifest，SHA-256
  `3ad16e36fd9a242cb4f8877b3a0bc806c9c9da403d95dc09c49cbf66424c903b`；
- `canonical_pairs.jsonl`：按冻结规则得到的空文件，SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。

系统调用审计的 forbidden paths=0、external network connects=0；artifact filename/content secret scans=0，
正式目录 writable files=0。
