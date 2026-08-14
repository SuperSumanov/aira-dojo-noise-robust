# v11 source opportunity identity recovery

日期：2026-08-15。协议：`source-opportunity-identity-recovery-v1`。source commit：
`3faf0013ff34f8a6f4c33ac99b0431b5ef394580`。

## 预注册裁决

producer 与不 import producer 的 verifier 一致裁决：

`VERIFIED_HIGH_COVERAGE_SOURCE_IDENTITY_RECOVERY`

固定门全部通过：complete/non-orphan 正控率=1.0；overall incomplete-parent recovery≥0.80；train/frozen
各自≥0.75。`opportunity_identity_registry_claim_allowed=true`，但
`complete_labeled_choice_set_claim_allowed=false`。

## 主要正结果

- source-incomplete parents：870；
- exact identity recoverable parents：721；
- parent-equal recovery rate：`0.828735632183908`；
- 恢复出的 missing child identities：996；
- complete/non-orphan 正控：2,328/2,328；
- unrecoverable incomplete parents：149；
- orphan incomplete parents：149；
- non-orphan unrecoverable parents：0。

| role | incomplete parents | recoverable parents | recovery rate | recovered missing IDs | orphan incomplete |
|---|---:|---:|---:|---:|---:|
| train | 665 | 544 | 0.8180451127819549 | 769 | 121 |
| frozen | 194 | 166 | 0.8556701030927835 | 216 | 28 |
| extension | 11 | 11 | 1.0 | 11 | 0 |

因此 source retention 缺口并非大面积无法追踪：只要 parent card 仍在，`children_ids` 与 child-side
`n_siblings+1` 在本语料上全部精确闭合。剩余不可恢复项完全由 orphan parent cards 构成。这支持发布一个
parent-equal、带 retained/missing 标志的 source-opportunity identity registry。

## 严格边界

本实验不访问 label 字段、numeric outcome、pair orientation、gap、code 或 first-960；GPU=0，API=0。恢复的是
child ID，不是 child card、执行 receipt 或分数。所有缺失 identity 的 execution/evaluation status 与 outcome 仍写
`UNKNOWN`；不能声称 missing-at-random、完整 labeled choice set、censor-aware predictor 收益或 downstream search
utility。

## 独立复核

- focused tests：`6 passed in 0.13s`；
- full `phase1/tests`：`292 passed in 36.39s`；
- producer elapsed：16.39 s；verifier elapsed：16.35 s；
- artifact credential-shaped file hits：0；
- producer summary SHA-256：`f9873bc539df9719897d562eaab909f9eab60c3f96e28ca18a65af4aae0b5226`；
- producer per-parent JSONL SHA-256：`b4261a4f042e92acca4a53630efe3e33ea1f2847d1a8148e9c8f18c35b447cd2`；
- artifact manifest SHA-256：`d7ffafc66ba2ea4f8cff1a1db70dd3aca1575221ccdba915a1d0c83067532e33`。

成功产物保留在 `/research/d7/spc/yzyang4/source-identity-recovery-v11-3faf001-a1`。上游
`per_parent.csv` 在运行前精确验证 SHA-256
`75c02200d1f9b8d87614762a9f2b71ba3c678d598ff28bc237c8a46a4bc36d03`。

## 下一门

后续已按结果前冻结的协议完成 journal status audit：996 个 missing IDs 中 902 个唯一恢复，893 个是 execution
error、9 个是 official grade absent，详见
`phase1/results/source_opportunity_journal_status_v11_20260815_42cb6b1/README.md`。该结果把 unknown identity 缺口
推进到 failure-censored registry，但仍不自动授权训练模型或改变 first-960 scorer。
