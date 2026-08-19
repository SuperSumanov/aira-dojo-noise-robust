# Temporal prediction escrow v1

日期：2026-08-19。正式状态：`VERIFIED_TEMPORAL_PREDICTION_ESCROW`。

结果前 commit `37fa0f0d12bbee09772b5b051038810bca540f8a` 固定了输入 SHA、固定 scorer、
pre-cutoff denylist、两个预测 arm 和全部成功门。远端 Linux 首先通过 `396 passed in 38.32s`；
producer 双跑逐字节一致，独立数值 verifier 双跑一致。

冻结资产包含 805 endpoints / 57 physical runs / 9 tasks / 103 structural sibling pairs。pre-cutoff
endpoint ID 与 exact-code SHA overlap 均为 0；`static_lr` 与 `char_tfidf_lr` 均覆盖全部 103 pairs，
ties 均为 0。独立实现对两个 arm 的最大绝对分数差均为 0.0。

完整性边界：程序不接受 label-vault 参数，`label_vault_read=false`、`numeric_grade_used=false`、
`accuracy_computed=false`；系统调用 trace 对 `label_vault.jsonl` 的 open 次数为 0。trace SHA256=
`810426ac88bc56b423040572b325f4269aabe8535dc3d11d05de66dd40f9cfb9`，不随仓库发布。

关键文件 SHA256：

- `summary.json`：`c8f9d06dc3df8ca01b9e9bc65383fc14a0469163d93f1b87d5ccae79dd222c0b`；
- `endpoint_scores.csv`：`753ccabc54d787bba875bef7e161a6f48e0c2752236c6c0c95f332bd0349fc72`；
- `pair_predictions.jsonl`：`656bc5547a1e066f7c2b39f163fc49a40304518d4e3c24dfe8731a58ceacdf64`；
- `independent_verification.json`：`436ff8c38abc18299a967c23b8e3961607035bc26d5b82f47ca09ce21254c2d1`。

这不是效果结果，也不授权现在打开 0812 label vault。其用途是让激活前固定的两个轻量 predictor
与未来 clean checkpoints 在同一时点完成不可修改的预测冻结，之后才可能进行一次性共同评测。
