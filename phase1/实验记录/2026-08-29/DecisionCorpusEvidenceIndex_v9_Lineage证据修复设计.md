# Decision Corpus Evidence Index v9：lineage 证据修复设计

日期：2026-08-29。性质：**已知结果后的 reporting/provenance 修复**，不是结果前预注册，也不是新效果实验。

## 为什么需要修复

Evidence Index v8 的 `decision_corpus` 条目继承自 v1 audit。该 audit 验证了 pair/run/task/split 的一致性，
但没有读取 Card 的 `lineage.parent_id`；因此它所附的证据不足以单独支持“declared parent 的直接 children”这一更强解释。
2026-08-29 完成的 lineage audit v2 已用独立 producer/verifier 正式闭合这个缺口。

v9 不新增一般 evidence-index novelty。它只修复本项目机器证据栈中的一条过弱 provenance pointer：

- source v8 的 16 个 entries 中，只允许替换 index 0 的 `decision_corpus`；
- 其余 15 项必须逐对象完全相等；
- v8 的 provisional 状态必须原样保留，不得借 lineage 正结果提前宣告 first-960 closure；
- 新条目必须同时写入 15/15 hard gates、35/36 support gates，以及唯一失败的
  `frozen:b2.maximum_single_run_pair_share`；
- 不生成 row-level core，不读取 prospective values 或 raw senior archives。

## 固定机器合同

协议：`phase1/decision_corpus_evidence_index_v9_protocol_v1.json`；SHA-256=
`a5d49990f3af37ce8968495fd13bf1b1c3f5e48875b117a86a878b75ed8d958a`。

绑定 source v8 index SHA-256=
`e97eca05d99a2eb3b5429539469a7e790f20f40cf70670cdbdc6a2c0c3e730a3`，lineage package manifest SHA-256=
`4c72c32449a4a68377fe3764089321c852648e0d6603655a09cd360a21d45447`。replacement entry 固定引用：

1. v2 producer aggregate；
2. 不 import producer 的 v2 verifier；
3. source/protocol/formal hashes 的 package bindings。

三份 artifact 共固定 51 项 JSON assertions。任何 source SHA、package manifest、classification、b2 失败门、
15 个非目标条目、provisional status 或安全边界漂移均 fail closed，不写 candidate index。

## 允许与禁止的结论

若 formal 通过，只允许称：Evidence Index 的 canonical decision-corpus 证据已从 run-map consistency 升级为
recorded-parent direct-child lineage certificate，并机器保留 parent-complete core 的 limited-support 边界。

不得称一般 machine-readable benchmark card/evidence-index 首创；不得把 recorded parent 称为语义或因果真值；
不得称所有 support gates 通过；不得推导 predictor accuracy/scaling/search utility 或 prospective generalization。
GPU/API/model-fit/base-update=`0/0/0/0`。
