# Randomized Sibling Logging v1：远端独立契约验收

## 裁决

在精确 source commit `59b5b8c698c6d687510cc184034d887619324243` 的全新远端 worktree 上，
producer 与不导入 producer 的 verifier 一致裁决：

`VERIFIED_OUTCOME_BLIND_RANDOMIZED_SIBLING_ASSIGNMENT`

这是一项 **0 GPU、0 API、0 scientific outcome** 的合成契约验收，不是生产采集，也不是方法收益实验。

## 验收结果

- 聚焦相关测试：`25 passed in 1.04s`；
- 完整 `phase1/tests`：`263 passed in 27.85s`；
- 合成 fixture：6 parents、2 tasks、16 rollout jobs、16 planned candidate-execution slots；
- 独立重建逐项一致：`independent_reconstruction_exact=true`；
- 产物不含 outcome：`contains_outcomes=false`；
- 声明的 displaced-slot ledger 与计划一致：`declared_slot_ledger_matches_plan=true`；
- producer 未被 verifier 导入：`producer_imported=false`；
- 远端安全扫描：14 个文件，可疑文件名 0、高置信凭据文件 0；
- 下载后按 `artifact_manifest.sha256` 本地复核：16 个文件，hash mismatch=0。

## 不得越界的边界

两个关键字段故意保持为 false：

- `actual_production_budget_decrement_verified=false`：这里只验证声明账本，不证明生产 scheduler 真正扣除了相同预算；
- `upstream_selection_probability_verified_by_assignment=false`：上游被日志机制替换的候选及其选择概率仍需生产 scheduler 独立签名。

因此本资产只冻结 outcome-blind、可复算的随机化日志格式。未经生产策略共同确认，不得挂到学长的日常语料生产，
也不得把它写成因果效果已经识别。

## 失败记录与环境隔离

第一次全新 worktree 创建在代码测试前失败：GitHub 缺少既有 LFS 对象
`a96e41b9f72c56c49b9af60ed1eead0d1b6daf21efe365a0f1a732590fc5eae4`。
该失败没有被成功验收覆盖。第二次使用独立目录并设置 `GIT_LFS_SKIP_SMUDGE=1`，才完成上述测试与合成验收。
缺失对象随后经压缩包流式凭据扫描、OID 校验和远端精确提交 include-only fetch 独立修复；修复不改变本契约的科学裁决。

## 证据文件

- `independent_verification.json`：独立 verifier 的机器可读裁决；
- `focused_tests.txt`、`full_phase1_tests.txt`：远端测试输出；
- `synthetic_assignment/`：生产者输出及其 manifest；
- `synthetic_fixture/`：只含身份、哈希和预算声明的合成输入；
- `safety_audit.txt`：远端凭据审计计数；
- `artifact_manifest.sha256`：归档逐文件哈希。
