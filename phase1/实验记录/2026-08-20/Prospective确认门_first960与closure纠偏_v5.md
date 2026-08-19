# Prospective 确认门纠偏：恢复 first-960 与 accrual closure

## 审计发现

v3 outcome-blind verifier 把当前所有 223 个 eligible runs 重建为 1,473 pairs，其结构计数和资产质量数字均正确；
但“只差 27 pairs”错误地把 first-960 内的支持门当成了停止门。2026-08-14 结果前功效附录明确保留 first-240
pilot，并将唯一确认 cohort 固定为 first-960；生产关闭凭据也必须在 outcome 未读时绑定 registry。近期没有正式
预注册 supersede 这两项。

## 修复与复核

commit `757ced0b2d36d8b105b5d25f23df577ac2bc07e6` 的 verifier v5：

- 锁死 first-960 与 1,500/150/15/0.25 支持阈值；
- 独立按 generation UTC/source SHA/run ID 排序和截断，区分 all-eligible 与 provisional-first960；
- accrual closure 必须 provided、all uploaded、outcomes unread，且 accumulator 已进入 frozen identity 状态；
- source binding 只读取当前 verifier Git blob，避免全仓库 metadata traversal。

真实 snapshot 双跑逐字节一致，receipt SHA=
`9d12e2a8cac555a9eef6743169d0b922c2840b1e6d9c20996662e1910b65e875`。结果为 223/960 runs、
1,473/1,500 pairs、222 finite-decision runs、25 pair tasks、dominant share=`0.1887304820095044`；closure 未提供，
状态 `CONFIRMATORY_COHORT_COLLECTING`，标签仓不得打开。禁读路径命中 0，credential shape 0，全套
`435 passed in 36.26s`。

v4 曾因全仓库 `git status` 产生 54 次 forbidden-path metadata stat；未读内容，但仍按零接触标准作废。

## 裁决

撤回“当前确认门只差 27 pairs”。准确状态是结构支持门接近满足，但确认 cohort 尚差 737 runs，且最终还需
独立 closure receipt。此前高决策覆盖、低 exact-code 冗余等正资产数字继续成立，作用域明确改为
`provisional_first960_prefix`。继续安全摄取；不得在 first-960 和 closure 前自动冻结或揭盲。

证据入口：`phase1/results/prospective_confirmatory_gate_correction_20260820_757ced0/README.md`。
