# Senior config sidecar v2：prompt-sensitive 指纹交付

日期：2026-08-25

状态：`V2_HANDOFF_READY_NOT_DEPLOYED`

协议：`senior-experiment-config-manifest-v2`

## 1. 为什么 v1 不够

学长 `dojo-reproduce@b80c056` 把静态 system policy 与动态 user context 分离。现有 v1/历史
`config_sha256` 实际只覆盖 `(client, hardware, time_limit, execution_timeout)`（另在 stratum 中加 task），所以即使
prompt/operator config 改了，它也可能保持不变。仅凭 v1 不能把 0823 runs 归因到 b80，也不能称 exact producer
stratum。

v2 对 producer-side、尚未打包的 `dojo_config.json` 做 outcome-before 导出：去掉恰好两个 run-specific 路径字段
`solver.exp_name` 和 `solver.checkpoint_path` 后，对完整 resolved solver canonical JSON 计算
`resolved_solver_config_sha256`。system prompt、user template、所有 operator/client/search/retry/memory 设置均保留在
hash 投影中；投影字节从不写入 sidecar。

config-side `experiment_stratum_sha256` 进一步包含 task、统一 client、generator release、hardware、两个时间限制、
projection schema 和 solver hash。consumer 再把它与 source manifest 中逐 run `producer_commit` 组合成
`producer_stratum_sha256`，避免“config 相同但代码路径已变”仍被混为同层。

## 2. 安全与失败边界

- exporter 只读未归档 producer config；consumer 禁止从含凭据的历史 tar 运行它；
- exporter 不读 `env_variables.json`，hardware 由 producer 显式传入公开标签；
- raw config 在 JSON parse 前做 credential-shape 扫描，命中即整行不产出；
- 所有带 LLM 的 operators 必须使用同一 public model ID；mixed client 直接拒绝，不偷用 draft client 代表全 run；
- generator release 不可知时只能写 `unknown`，receipt 仍保 provenance，但
  `interaction_metadata_complete=false`；
- fresh output、exact 10-field schema、run/task/source exact join、symlink、篡改 hash、非正时间等均 fail closed。

完整规范和可直接调用的 exporter/validator：

- `phase1/contracts/SENIOR_EXPERIMENT_CONFIG_MANIFEST_V2.md`；
- `phase1/senior_experiment_config_v2.py`；
- `phase1/validate_senior_experiment_config_manifest_v2.py`；
- `phase1/examples/senior_experiment_config_manifest_v2.example.jsonl`（纯 synthetic，禁止当真实 receipt）。

## 3. 验证收据

本地 v1+v2 focused 为 `19 passed, 1 skipped`；唯一 skip 是 Windows symlink 权限。推送后在 fresh Linux detached
worktree `a6776bef85513209f36c88e3c373d54638c7f17c` 重跑，得到 **`20 passed in 0.21s`**，因此 symlink 攻击也在
目标系统通过。remote receipt root：
`/research/d7/spc/yzyang4/config-v2-postpush/a6776be-v1`，其 `SHA256SUMS` 自身 SHA-256 为
`93bde54b3022b4bd544d1b8c0b7c39eadf6b1e149b043897d3ddce6834798a3b`；独立 postverify 已全部通过且目录无可写路径。

攻击测试包括：prompt 改动必须改 hash、仅 run 路径改动必须不改 hash、release/solver hash 进入 stratum、mixed clients、
raw credential、完整 source composition、tampered hash、unknown 降级、fresh output 和仓库 synthetic example。

v2 与 coverage/report 完全集成后的 commit=`aa91322f05f41c58276686fc4e632449c3649cf5` 又在 fresh Linux
no-smudge worktree 跑完整 `phase1/tests`：`984 passed, 47 warnings in 75.33s`。postpush root=
`/research/d7/spc/yzyang4/postpush-aa91322-full-v1`，其 `SHA256SUMS` 自身 SHA-256=
`943f787d4c926b22d84955f16f82cfae2c0ee77c43c2ee665b27c9ea453a7e26`。

## 4. 当前不能说什么

没有真实 next-batch v2 sidecar，也没有真实 `PROMPT_SENSITIVE_CONFIG_PROVENANCE_VERIFIED` receipt；学长生产尚未
部署。0823 六个历史 archives 没有 outcome-before v2 sidecar，不能事后回填成 prompt A/B、b80 因果归因或 clean
scaling confirmation。v2 只让**下一批**具备可识别性，不是效果实验，也不授权 GPU、模型训练或揭盲。

建议学长从下一批 producer 在 archive 发布前调用 exporter，并把 per-run sidecar 与 source manifest 同步作为不可变
分批文件上传；consumer 合并时必须覆盖 frozen expected-run 集的全部 rows，禁止挑方便子集。
