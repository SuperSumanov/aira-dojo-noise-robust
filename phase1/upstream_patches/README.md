# Upstream patches

这里保存针对其他现有分支、但不直接改写对方分支的可审计补丁。补丁必须注明精确 base commit、测试结果与
迁移边界；只有维护者审阅后才 cherry-pick。

## Prospective config-v2 producer hook（2026-08-27）

`0001-Add-prospective-config-v2-producer-hook-18-tests.patch` 精确基于学长
`dojo-reproduce@61459c0a1248900079dafed7c505afa87e476b40`，SHA-256=
`56a3e4b61918e1b06830712d418ed27ef5135017eab2b9e833b92c626054c9a5`。它把已经审计的
prompt-sensitive config-v2 指纹嵌入真实 `dojo.main_run` 启动路径，但默认关闭；仅在
`DOJO_CONFIG_V2_SIDECAR=1` 且显式提供 `DOJO_GENERATOR_RELEASE` 时，于 solver/task 构造前写
`producer.config_v2.jsonl`。输出不含 resolved solver、环境 dump、凭据、outcome 或 label；只含十个公开字段与
SHA-256。相同 run 的 resume 只允许复用逐字节一致的 sidecar，配置变化或竞争写入均拒绝且不覆盖。

fresh Linux no-smudge worktree 的 focused/full 为 `19 passed` / `84 passed, 1 skipped`；128 个合法变体与
`phase1/senior_experiment_config_v2.py` 逐 row、逐字节相同，4 类非法变体两边都拒绝；filename/blob
credential hits=`0/0`。正式根=
`/research/d7/spc/yzyang4/config-v2-producer-hook/verify_fa2151b_v4`，`SHA256SUMS` 自身 SHA-256=
`fbb9536c760c9a14ba9e7da044d1f32fe7f748ff54298f27fb1951bbe743c2b0`。

另在不读 env/outcome 的历史 schema-only smoke 中，按 mtime 预先冻结的 20 个真实 `dojo_config.json` 全部得到
candidate/reference 完全相同的 row/bytes；覆盖 7 tasks、2 clients、2 solver fingerprints、9 strata，forbidden
path opens=0、sidecar writes=0。formal root=
`/research/d7/spc/yzyang4/config-v2-producer-hook/real_config_smoke_65896b6_v1`，manifest SHA-256=
`80c8ab4b9ef5c23693aad00c7db75e81d81fd18f7339f65d6dff67e86003c47e`。这是兼容性验证，不是历史 provenance。

状态严格为 `PATCH_VERIFIED_NOT_DEPLOYED`：补丁没有改写学长分支，尚未观察到真实 producer sidecar，不能把
历史 archive 回填为 exact stratum，也不授权训练、GPU 矩阵或效果主张。8 月 19 日旧 exact-stratum patch 是
Cards/pair 生成后的 v1 同层过滤；本补丁解决的是更早的 outcome-before producer config/prompt 可识别性，两者不重复。

## Critic clean-confirmation overlay（2026-08-23）

以下四份补丁按顺序应用于学长 `dojo-reproduce@ac008af8b907d319b694f26b0ba9cf4053b3bf69`：

1. `0001-Harden-critic-confirmation-protocol.patch`，SHA-256
   `2fd5ca7b38e4277b68c2eb90b42c0f0ce85b8ab0ef687802e68ceeb8f0fc1fe2`；
2. `0002-Allow-fixed-step-critic-budget-calibration.patch`，SHA-256
   `89d7af494e436c4d5a7ed5c4a06e43c4d012cb26c3efd3c1e9f52bf00b3bd641`；
3. `0003-Record-critic-wall-clock-receipts.patch`，SHA-256
   `a4146bdc6ef3123e3b88a3b909352dd40db3cff992503919d4207c1756313f67`；
4. `0004-Emit-endpoint-score-receipts.patch`，SHA-256
   `237bbffe1130af74527d1a3febcfdcc3330b49a13b785c31039a79a1ac091242`。

集群 fresh no-smudge worktree 中四份补丁均通过 `git apply --check`，Python compile、launcher shell syntax、
`git diff --check` 以及 8 个聚焦测试文件；打印结果为 `36 passed in 46.79s`。第 4 份只把 evaluator 已经计算的
better/worse scalar scores 连同 margin 写入 one-shot receipt，并检查三者一致，不改变模型、输入或预测。该通过只证明工程 overlay 与精确
base commit 兼容，不证明模型效果，也不解除 source-batch provenance、全新 experiment-closed dev/frozen、Cards
LFS 和单旋钮门禁。当前不得直接运行 mixed launcher。
