# Task Balance：预测矩阵污染传播与 Structural-Only v2 预注册

冻结时间：2026-08-26T05:48:16Z。本文写在任何 v2 formal artifact 提升之前。

## 1. 下游污染传播

旧 prediction coverage matrix 已因预闭包读取、解析并聚合 prediction values 而撤回其“严格零预测值访问”合规性。进一步
审计确认，该 matrix 的逐任务 pair counts 又被 `prospective_task_balance_accrual_guard_v1` 直接读取；旧 forward input
同时绑定 v1 guard 和后续 value-reading coverage matrix。因此旧 task-balance guard v1、forward v1 及其 formal replay
也不能继续作为严格零 prediction-value provenance 的证据。

Decision Corpus Evidence Index v6 中 matrix 项、Agentic Benchmark Checklist crosswalk 中指向 matrix/guard 的证据
指针同步降级。其他不依赖这些文件的结构证据不受影响。完整机器登记见
`phase1/prediction_matrix_downstream_taint_registry_v1.json`。

这不证明旧算术数值错误：没有读取 prospective label/outcome/accuracy/search utility，也没有据此改 scorer、模型、任务、
阈值或 hypothesis。但“数值可能正确”和“证据生成协议合规”是两件事；前者不能修复后者。旧文件全部保留，不删除、不
覆盖，也不将旧 matrix 数字当作 v2 输入。

## 2. v2 的独立结构来源

基线 guard v2 只允许三类输入：独立 structural gate、snapshot-bound accumulator `summary.json`、以及 summary 内 SHA-256
绑定的 `provisional_first960_runs.jsonl`。逐任务 pair/run/endpoint counts 直接来自 accumulator；ledger 重新计算 run 与
endpoint counts；independent structural gate 交叉确认总 pairs、总 runs、tasks、dominant count/share 和 accumulator checks。

forward v2 对基线和当前 accumulator/ledger 各自重新验证，并额外绑定 receipt-only common-support independent receipt 来
交叉确认当前 canonical pair 总数。禁止任何 prediction pair file、prediction value、coverage matrix、label/outcome vault、
raw archive payload 或 effect 表作为输入。

producer 与 independent verifier 不互相 import。正式件必须 producer A/B、verifier A/B 逐字节一致，且 file-level trace 中
prediction-pair/outcome opens 为 0。协议全文见 `phase1/task_balance_structural_only_protocol_v2.json`。

## 3. 时间与认识边界

v1 已经显示过 657→645、债务 −12 等算术。因此 v2 不是 blind numerical discovery，而是 provenance repair。协议是在本地
实现与 smoke 后、任何 formal evidence promotion 前冻结；正式结果无论复现或不复现，都必须报告。若复现，只能称“同一
算术可由严格 structural-only 链独立重建”，不得用一致性追溯性地恢复 v1 合规性。

## 4. 正式杀死条件

任一输入 hash/path/snapshot 绑定失败；summary/ledger/gate/receipt 数量不一致；ledger 出现非结构字段；安全字段显示
prediction/outcome access；chronology set/subsequence/row identity 失败；A/B 不一致；独立复核不一致；forbidden file open 或
credential hit 非零，均须 fail-closed。GPU/API/model-fit/base-LLM update 固定为 0。

## 5. 预注册后的 formal 结果

公开 source commit=`1b9b8365f1b2067c9ebb27c20d29b6844bc79f3a`。fresh no-smudge Linux focused/full=
`4 passed` / `1113 passed, 47 warnings`。guard 与 forward 的 producer A/B、non-importing verifier A/B 均逐字节一致；
postformal verifier A/B 又分别与 formal verifier 逐字节一致。forbidden file opens、credential filename/content hits 均为 0，
GPU/API/model-fit/base-update=`0/0/0/0`。

结构源独立恢复：baseline 2,635 pairs、OSIC 823、share=`0.31233396584440226`、debt=657；current 2,755
pairs、OSIC 850、share=`0.308529945553539`。新增 dominant/non-dominant pairs=`27/93`，故冻结恒等式与当前逐任务
重算均为 debt=645，delta=−12。25% cap 仍失败，且 debt 清零前新增 dominant pairs，因此即时动作状态仍为
`DEFINITELY_NOT_ADHERED_BEFORE_DEBT_CLEARANCE`。

guard/independent SHA-256=`2ffa91a5...52cd177` / `62f5fa00...15310c`；forward/independent=
`fca979bb...ea0fb1` / `00f8fec2...102146`；formal/postformal manifest=`b1405cd4...005135` /
`8b90eab9...cb0166`。结果包：
`phase1/results/task_balance_structural_only_v2_8579_20260826_1b9b836/`。

首次 formal 已完成 4/1113 tests 与 A/B，但 credential regex 无左边界，把目录名内部的 `sk-...` 字符串误报为 key，
因此按约定 fail-closed、不提升。修复只收紧为 boundary-aware regex 并加入正/负自检；新 commit/new output 从头重跑。
本次一致性只恢复结构算术主张，绝不追溯恢复 v1 provenance。
