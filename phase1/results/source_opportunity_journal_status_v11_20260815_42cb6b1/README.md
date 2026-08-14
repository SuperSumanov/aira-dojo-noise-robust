# v11 source opportunity journal-status recovery

日期：2026-08-15。协议：`source-opportunity-journal-status-v1`。source commit：
`42cb6b1ac0575f26350b72519b3d558aab5a084a`。

## 预注册裁决

producer 与不 import producer 的 verifier 一致裁决：

`VERIFIED_HIGH_COVERAGE_MISSING_STATUS_REGISTRY`

固定三门全部通过：target node recovery≥0.80、source-journal collision=0、journal parent mismatch=0。
`missing_status_registry_claim_allowed=true`；`missing_at_random_claim_allowed=false`；
`complete_labeled_choice_set_claim_allowed=false`。

## 主要正结果

- target missing sibling identities：996；
- unique source-journal nodes recovered：902；
- child-equal recovery rate：`0.9056224899598394`；
- unrecovered targets：94；
- source-journal collisions：0；
- journal parent mismatches：0。

恢复节点的 status 组成：

| status | count | share among recovered |
|---|---:|---:|
| `EXECUTION_ERROR` | 893 | 0.9900221729490022 |
| `OFFICIAL_GRADE_ABSENT` | 9 | 0.009977827050997782 |

893 个 execution failures 占全部 996 个 target identities 的 `0.8965863453815262`。按 role：

| role | targets | recovered | recovery rate | execution error | grade absent |
|---|---:|---:|---:|---:|---:|
| train | 769 | 699 | 0.9089726918075423 | 691 | 8 |
| frozen | 216 | 192 | 0.8888888888888888 | 192 | 0 |
| extension | 11 | 11 | 1.0 | 10 | 1 |

这给出一个明确、正面的数据结论：v11 labeled sibling fragment 的主导缺失机制是 candidate execution failure，
而非候选从未生成或无规律漏标。只在成功候选内做 pair ranking 因而估计的是 conditional-on-success quality，不能
直接代表 source opportunity set 上同时权衡 feasibility 与 quality 的部署决策。

## 安全与范围

扫描 roots 固定为先前 provenance audit 的 ours、senior_older、extract_0806、0807、0808、0809、0810、0811。
只选 canonical journal；整文件 credential scan 在 JSON parse 前执行。一个 credential-shaped journal 被跳过并只记录
相对路径 hash；不读取或输出其 bytes。没有打开 tar 其他 member、env、frozen/test pair 或 first-960，也不记录
numeric grade、code、stdout。GPU=0，API=0。

94 个未恢复 target 不能按 recovered 分布外推；`SOURCE_JOURNAL_NOT_FOUND` 不是“未生成”的证据。execution error
也不等价于不可修复，当前只陈述历史节点状态。

## 独立复核与失败保留

- focused tests：`7 passed in 0.16s`；
- full `phase1/tests`：`299 passed in 26.21s`；
- producer elapsed：311.49 s；verifier elapsed：274.61 s；
- artifact credential-shaped file hits：0；
- producer summary SHA-256：`9920ca85c740c0ff7912417ef1141f53ad331034f0b5d72f6b6efad9192440b9`；
- producer per-child SHA-256：`bfb9870d83c50ef2d06bf2d374fc9f9213f41665f4cebeab7ab31837bcfde0d2`；
- artifact manifest SHA-256：`b97e650e8efd8d26bf0ca3416572f4ddc4be8a1cd4d1b23868025aea6b3648fc`。

成功产物在 `/research/d7/spc/yzyang4/source-journal-status-v11-42cb6b1-a2`。`a1` 因相同 journal bytes 的不同
路径 hash 被误判为同-source conflict，在产生 summary 前 fail-closed；失败目录保留。新增“byte-identical copy 按
source SHA 折叠”回归测试后，`a2` 未改 roots、targets 或阈值。外层 SSH 超时后远端 verifier 正常完成；后续 resume
因 receipt 已存在保护门立即退出，未重写产物。

## 论文与下一方法门

可防守贡献是 failure-censored MLE source-opportunity resource：同一 parent 下同时发布 retained labeled candidates、
missing generated identities 与 execution/evaluation status。下一步可把 **feasibility→conditional quality** 两阶段
baseline 作为 benchmark 必备基线，并最终在固定预算新 run 上比较 downstream utility；hurdle/validity predictor
原语已有先例，本身不作为 novelty，也不得用 retrospective accuracy 代替 prospective utility。
