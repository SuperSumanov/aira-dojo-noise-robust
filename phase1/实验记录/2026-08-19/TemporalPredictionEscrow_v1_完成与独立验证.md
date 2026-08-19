# TemporalPredictionEscrow v1：完成与独立验证

日期：2026-08-19。裁决：`VERIFIED_TEMPORAL_PREDICTION_ESCROW`。

## 执行结果

- 结果前 commit：`37fa0f0d12bbee09772b5b051038810bca540f8a`；
- Linux 全套测试：`396 passed in 38.32s`；
- 冻结范围：805 endpoints / 57 runs / 9 tasks / 103 sibling pairs；
- pre-cutoff endpoint ID overlap=0，exact-code SHA overlap=0；
- `static_lr`/`char_tfidf_lr` 均为 103/103 覆盖，ties=0；
- producer 两次 summary、endpoint scores、pair predictions 逐字节一致；
- 不导入 producer/current scorer 的 verifier 两次一致，两个 arm 的最大绝对差均为 0.0；
- trace 中 `label_vault.jsonl` open=0；trace SHA=
  `810426ac88bc56b423040572b325f4269aabe8535dc3d11d05de66dd40f9cfb9`；
- GPU/API=0，未使用 numeric grade，未计算 accuracy。

summary SHA=`c8f9d06dc3df8ca01b9e9bc65383fc14a0469163d93f1b87d5ccae79dd222c0b`；endpoint
scores SHA=`753ccabc54d787bba875bef7e161a6f48e0c2752236c6c0c95f332bd0349fc72`；pair predictions
SHA=`656bc5547a1e066f7c2b39f163fc49a40304518d4e3c24dfe8731a58ceacdf64`；独立验证文件
SHA=`436ff8c38abc18299a967c23b8e3961607035bc26d5b82f47ca09ce21254c2d1`。

## 科学边界与下一步

本轮只把预激活固定 predictor 的预测变成不可修改的 escrow，没有读取标签，因此没有新的 accuracy、
selection utility 或模型优越性主张。0812 temporal holdout 只有 103 pairs，不能单独承担论文确认结论；
label vault 继续封存。

下一步仍等待时间更晚、由 exact-stratum producer 产生的 clean future cohort。若学长产生未触碰 frozen test、
只由 train-only dev 固定的 checkpoint，可先对同一 blind view 冻结它的预测；所有预先冻结方法再按另立的
one-shot unseal 协议共同评估，禁止先看本轮标签后选择 checkpoint 或方法。
