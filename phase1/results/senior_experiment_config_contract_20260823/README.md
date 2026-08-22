# Senior experiment-config provenance overlay

状态：`CONTRACT_IMPLEMENTED_REAL_MANIFEST_PENDING`。本目录增加的是 future-only 配置 provenance
组合层，不是新的科学效果，也不修改当前 33/300 score-channel cohort。

## 已闭合的接口

- 复用 `SENIOR_SOURCE_PROVENANCE_MANIFEST_V1` 的 archive/batch/commit 身份绑定，不复制其逻辑；
- 每个 frozen physical run 精确绑定公开的 `client`、结果前 `generator_release`、`hardware`、
  `time_limit`、`execution_timeout` 与既有 `experiment_stratum_sha256`；
- 独立重算 source mapping，要求已验证 source receipt、两个 manifest 和 expected-run 集合完全同一；
- 所有输入在 JSON parse 前做高置信凭据扫描，字符串使用公开标识 allowlist；
- `generator_release=unknown` 可以保存 provenance，但回执强制
  `interaction_metadata_complete=false`，不能拿去做 generator interaction；
- 不读取 archive payload、Cards、pairs、code、stdout、grade、prediction 或 orientation。

## 验证

远端 detached no-smudge base=`04b1be9fe88776be4531ce6c82130d4927b4cb45`。线程固定后的独立验证：

- source+config 聚焦/攻击测试：`21 passed in 0.18s`；
- 完整 `phase1/tests`：`809 passed, 33 warnings in 51.65s`；
- 文件名/内容凭据扫描：`0/0`；
- GPU/API/model fit/base-LLM update/future-truth open：`0/0/0/0/false`。

首次完整回归没有设置 BLAS/数值线程上限，在登录节点展开约 30 个线程；运行到约 17% 时主动中止，之前没有测试
失败。该次状态明确记录为 `ENVIRONMENT_THREAD_OVERSUBSCRIPTION_ABORTED`，日志保留且不计作通过。随后固定
OMP/OpenBLAS/MKL/NumExpr 各 1 线程，得到上述完整通过结果。

机器可读数字和文件 SHA-256 在 `verification_receipt.json`。成功/中止日志分别位于：

- `/research/d7/spc/yzyang4/prospective_decision_v1/config_provenance_verify_20260823_threadcapped.log`；
- `/research/d7/spc/yzyang4/prospective_decision_v1/config_provenance_verify_20260823.log`。

## 尚未闭合

尚无真实 producer config manifest，因此本目录不是已验证真实 cohort 的 receipt，也不支持 generator 效应结论。
学长后续只需在新 critic cohort 冻结时输出这一安全 sidecar；通过本契约后，再运行独立 outcome-blind balance/support
gate。当前 score-channel 33/300 的协议、truth vault 和 intake monitor 保持不变，禁止事后回填。
