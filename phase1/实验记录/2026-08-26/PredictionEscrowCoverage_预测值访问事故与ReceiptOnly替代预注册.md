# Prediction Escrow Coverage：预测值访问事故与 receipt-only 替代预注册

记录冻结时间：2026-08-26T05:07:32Z。本文在任何 receipt-only 正式运行前写入并提交。

## 1. 事故与撤回

旧 `prediction_escrow_coverage_matrix.py` 并非只比较结构 receipt：它打开 WL/transition pair prediction 文件，解析
margin/selected 字段，并计算 tie/non-tie、activation 与 effect-eligibility 聚合。因此其
`prediction_values_aggregated=false` attestation 按字面为假，也不满足 2026-08-26 收紧后的规则：first-960 +
独立 closure 前，除冻结 scorer/独立数值 verifier 在封存流程内运行外，通用审计不得读取或聚合 prediction values。

诊断期间还向操作者显示过少量 prediction-derived aggregate。没有读取 label、grade、outcome、accuracy 或 search
utility；没有改变任何 frozen scorer、activation、模型、threshold、task/subset、停止规则或 hypothesis。现有 remote/
Git artifacts 原样保留作事故与撤回链，不删除、不覆盖，也不得继续用于论文结论。

因此撤回以下“符合预闭包零预测值访问契约”的表述：0FT/0FU/0FV 及其后续 coverage matrix 的合规性；Decision Corpus
Evidence Index v6 中依赖该 matrix 的第十项也降级为 historical-withdrawn。旧 matrix 的任何 orientation、tie/non-tie、
activation/eligibility 数字均不得迁入新结果。该撤回不等于其数值已被证明错误，而是证据生成协议不合规。

## 2. 结果前冻结的新问题与允许主张

唯一问题：在不打开 prediction pair 文件、不解析 artifact summary 内容、不读取 prediction value 的条件下，能否认证
WL 与 transition 两个已提升 escrow 对同一 immutable snapshot 的 exact canonical structural pair population 具有共同
支持？

允许的成功主张仅为 `RECEIPT_CERTIFIED_EXACT_CANONICAL_COMMON_SUPPORT`。逻辑前提是：

1. 两个 promoted state 指向同一 snapshot，并分别以 SHA-256 绑定 artifact summary bytes；
2. 两份 frozen independent verifier 源码 hash 与预注册 contract 一致；
3. 记录的 verifier command 把同一 snapshot、state artifact 与对应 independent receipt 精确绑定；
4. 两份 independent receipt 各自认证其 frozen verifier 重建的 canonical structural pair population，且 pair count 相同；
5. 两个 verifier contract 明确重建的是同一个 first-960 canonical sibling-pair 定义。

“pair count 相同”单独绝不充分；成功依赖上述完整 contract chain。新结果不得声称重新打开过 pair identity/orientation，
不得报告 orientation、margin、tie/non-tie、activation、eligibility、temporal/joint strata 或任何 predictor distribution。

## 3. 固定输入与实现

允许输入只有 promoted WL/transition state、各自 independent verification receipt、记录的 independent-verifier command、
artifact summary bytes（只做 SHA-256）及 frozen verifier source bytes（只做 SHA-256）。明确禁止 pair prediction 文件、
label/outcome vault、score registry、regrade、accuracy/effect/search utility。

producer A/B 必须逐字节一致；不 import producer 的 verifier A/B 必须分别从允许输入重建 candidate，并逐字节一致。
四个进程均用 file-level `strace`；任何 `pair_predictions.jsonl`、artifact `pairs.jsonl` 或 outcome/label 路径 open 都使
正式运行失败。全部 BLAS/数值库线程固定为 1；GPU/API/model fit/base-LLM update 均为 0。

## 4. 预注册杀死条件

任一条件触发即不得提升 receipt state：promoted snapshots 与 `LATEST` 不同；summary hash 失配；frozen verifier source
hash 失配；verifier command 的 module/snapshot/artifact/output 绑定失配；receipt status/scope/summary binding 失配；两份
canonical pair count 不同；producer A/B 或 verifier A/B 不一致；独立 verifier 不接受 candidate；strace/credential scan
非零；manifest 复验失败。

当前运行只给出 pass/fail 和 structural pair count。无论结果是否通过，都不得据此改 scorer、arm、threshold 或假设；
first-960 与 closure 之前继续禁止 effect/accuracy 解封。

## 5. 预注册后的正式结果

上述协议先以 public commit `9f2cbe9bff91c2f0ee6f86ff93d9737f9431547f` 固定。fresh Linux focused/full=
`19 passed` / `1104 passed, 47 warnings`。随后在 current `8579` promoted states 上正式执行：

- status=`INDEPENDENT_PREDICTION_RECEIPT_COMMON_SUPPORT_VERIFIED`；
- receipt-certified exact canonical common support=`2,755 structural pairs`；
- producer A/B 与 non-importing verifier A/B 各自逐字节一致；
- prediction pair file open hits=`0`，outcome path open hits=`0`；
- prediction values accessed=`false`，prediction value aggregates=`[]`；
- pair identity/orientation reopened=`false`，prospective outcome/effect=`false/[]`；
- formal manifest=`179a511d9c85dbde73b93cd8f3f5eec6b90efc53a7c6f75e341fddf33635d995`。

前置 WL exact replay 通过 `22/1094 passed`，producer 与 one-shot current artifact 逐字相同，manifest=
`ba152f6171a87cc72ec805c8c4ecacd07bd0462b9a93e063709ce19b798e121d`。新 WL / receipt-only monitors 分别为
PID `2374019/2374760`；transition PID `2320379` 保持。两个旧 monitor 只在精确 cmdline 与 replacement live state 都核验
后 TERM，历史 artifacts 保留。

因此本次允许的正面结论是：未来 paired benchmark 的 exact common support 可在 first-960 closure 前由 receipt chain
认证，而无需通用审计读取 prediction values。它不是方法效果、accuracy 或 orientation 结论。
