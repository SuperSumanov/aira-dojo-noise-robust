# Probe-First Artifact Contract A/B V2：正式无效，诊断仍为 QUALITY_KILL

四个 replay shards 11160--11163 全部 `COMPLETED 0:0`，16/16 固定 index 完整。实际 replay allocation 为
2,603 GPU 秒（`0.723055555555556` GPU·h）；含 generation 共 25,731 GPU 秒（`7.1475` GPU·h），低于批准
12 GPU·h。

冻结 primary 数值结果为：120 秒 coverage `4->4`、净增益 0、合法 contract probe `4/8`、full-valid
`6->4`、paired full scores=4；K0/K1/K2 失败，K3 通过，primary 点裁决 `QUALITY_KILL`。

正式实验不能采用该裁决：primary 的 V2 数值门正确使用 `paired_full_scores>=4`，但 gate 输出键误写为
`quality_pairs_at_least_3`；独立 verifier 使用正确的 `...at_least_4`，在 gate map 精确比较时失败。因此按冻结
预注册状态为 `INVALID_INDEPENDENT_VERIFIER`，不得事后修复后追认为确认实验。

为定位影响，另建不覆盖原件的 post-outcome diagnostic root，只把 stale gate 键重命名，不改任何 summary、row、
阈值或 replay。冻结独立 verifier 完成 30 个唯一 artifact regrade 后，与 primary 的 verdict、gates 和所有
summary scalar 一致，仍为 `QUALITY_KILL`。这只作为诊断性边界：没有隐藏的正结果，prompt-only contract 不提高
120 秒 coverage，并降低 full validity；该方法线关闭。
