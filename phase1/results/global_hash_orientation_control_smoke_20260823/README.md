# Global endpoint-hash orientation control smoke

状态：`HISTORICAL_SCHEMA_SMOKE_PASS_EFFECT_BLOCKED`。

本 smoke 验证 0EA 的 `Ghash→L` 负控能在学长真实 pair schema 上确定性物化，不含模型训练或效果数值。

- source branch：`ac008af8b907d319b694f26b0ba9cf4053b3bf69`；
- source global LFS oid：`8a01dfb90c2c3d8498174ebe78df43ee21d6d0eac9f4ff81f63700b315473405`；
- credential-first high-confidence hits：0；
- full global rows：16,204，train/test=14,206/1,998；
- train-only SHA-256：`d9163bbcde70d8fe1f6f2ead9db266eca7ced932682cdaed9d3a9ece6fa43010`；
- train rows/tasks：14,206 / 39；
- overlay v2 SHA-256：`55ced63f9ea41adcd57c2067cb70fcfa3d430ba7171d89ae6f697e79396a2849`；
- producer×2、independent verifier×2：byte-identical；
- outcome-derived fields/commitments in overlay：0；交换真实 orientation、改 gap 或新增 outcome 注释后，overlay
  均逐字节不变；
- focused protocol/overlay tests：`15 passed in 0.10s`；
- GPU/API/model fit/effect authorization：0。

最终未提交源码随后覆到 `74ffb87...` 的远端无 LFS 隔离克隆：联合聚焦测试 25/25，通过；完整
`phase1/tests` 783/783，通过（33 个既有 sklearn 弃用警告）。该最终包同时包含 truth-support 独立 verifier 的
archive-boundary 加固；前两次包装
分别在“基线对象未 fetch”与“系统
Python 无 pytest”处、测试启动前失败，也保留在 `remote_validation_receipt.json`，不计作测试通过。

提交前审计发现 v1 overlay 的 `source_row_sha256` 会随原始 better/worse 与 outcome 元数据变化。它不写出原值，且从未
进入训练或 effect，但不能称为严格 grade-independent commitment。v1 overlay SHA
`3f80cd031e8532cf955ab90d42c9723461b8ee07fcf8b3f3a5527ea68e786cf0` 已撤回；v2 改为只绑定
`row_number/task/train/unordered_endpoints` 的安全身份哈希，并把 task 纳入 pair hash，同时拒绝 endpoint 跨 task 复用。

历史文件含已知 test rows，烟测只为 schema/吞吐支持。正式实验必须使用新 producer 输出的物理 train-only 文件并绑定
新 SHA；此处的 overlay 不得进入 effect stage。

机器回执见 `verification_receipt.json` 与 `remote_validation_receipt.json`。
