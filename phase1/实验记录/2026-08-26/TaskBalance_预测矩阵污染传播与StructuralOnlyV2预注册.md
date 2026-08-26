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
