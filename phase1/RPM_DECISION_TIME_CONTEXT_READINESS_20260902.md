# RPM transfer 的 decision-time context 门（2026-09-02）

> 状态：`STRUCTURAL_CONTEXT_POLICY_FROZEN_TOKEN_PACKING_NOT_YET_FROZEN`。本工作只固定结果盲的历史
> context 语义、序列化与独立复验；没有选择前瞻 panel、调用模型、读取冻结结果或授权 API/GPU。

## 先排除一个会污染冻结集的错误入口

最初只做 split-first 可行性检查时，`decision_clean_b0/b1/b2.jsonl` 的 2,087 行全部为
`intask_split != train`，train 行为 0。检查在 endpoint lookup 前跳过全部行，因此没有把这三份冻结 test 文件
用于开发、拟合或 context 统计。后续只使用 immutable Source Choice Decision View v2 的公开
`train_model.jsonl`；`frozen_model.jsonl` 和 `extension_model.jsonl` 没有打开。

## 字段可见性裁决

RPM prompt 要求“其他历史解及其分数”。Decision Corpus 中必须区分：

- `label.graded` 是事后 external MLE-bench grade，候选选择时不可见，context 中永久禁止；
- `obs.val_at_low` 是历史节点执行后 agent 当时可见的 self-reported validation，允许作为历史 context score；
- candidate 自身的 `obs`、同 step/更晚节点、跨 run/task 节点、runtime/stdout/error 与任何 post-hoc provenance
  均禁止进入 context；
- cutoff 是完整 sibling set 的最早 candidate journal step，而不是只看当前显示的 pair。由此同一 parent 的所有 pair
  和 AB/BA orientation 使用同一 context，不能按候选或结果改变。

历史 train-only 聚合检查绑定：

- `cards_current_v11.jsonl`：SHA-256=`6794acbf...01b75`；
- `train_model.jsonl`：SHA-256=`e5ca6dc9...aa6e1`；
- `cluster_manifest.jsonl`：SHA-256=`a8f328a3...4035`；
- 2,109 train groups / 5,739 candidate slots；5,042 slots 可直接映射到 cards；全部 2,109 groups 都能映射
  physical run 且有非空 task description；
- 2,071/2,109 groups 有至少两个可用的 prior scored nodes，覆盖率=`0.981981981982`；38 groups 没有 prior
  scored context，必须输出显式空-context marker，不得从未来节点、external grade 或别的 run 补齐；
- 可用历史节点数 min/median/max=`0/30/506`。

这些只是 train-only 工程可行性计数，不是 predictor accuracy、search utility 或独立科学证据；检查没有咨询公开 train
winner hash 的值，也没有咨询 external grade 值。

## 冻结实现

机器契约 `phase1/rpm_decision_time_context_contract_v1.json` 固定：

1. 上游输入必须先只保留同 run/task、严格早于 sibling-set cutoff 的历史节点，且 candidate record 不得出现；
2. 每个节点必须有非空 code/operator 与 finite `self_reported_validation`；
3. 顺序固定为 journal step 降序、node SHA-256 升序，不按 external grade 或 candidate outcome 排序；
4. 每个节点序列化为一行 canonical compact JSON，只含 code、context rank、step、operator、score type/value 和
   optimization direction；不输出 raw/hash identity；
5. credential-shaped task/code/operator 使整个 decision group fail-closed；candidate payload 在
   `rpm_inference_only_transfer.py` 也执行同一类门；
6. producer=`rpm_decision_time_context.py`，独立 verifier=`verify_rpm_decision_time_context.py`，后者不 import producer；
   双跑必须逐字节一致，输出已存在时拒绝覆盖。

## 仍未关闭的门

token packing 仍未冻结。RPM v2 只说明使用模型窗口能容纳的最大 context-node 数，没有公开足够实现细节来证明其节点
排序/格式；我方不得用字符或字节上限冒充 tokenizer token count。真实调用前仍须固定 exact model checkpoint、tokenizer、
system wrapper、context window、reasoning/output reserve，并且只能取上述固定顺序的完整前缀，禁止截断单个 node。

此外还需 outcome-blind exact-common-support panel、candidate/context 内容审查、append-only prediction escrow、
first-960 + accrual closure、以及单独的 calls/tokens/latency/currency cap 批准。当前
GPU/API/model fit/base update=`0/0/0/0`，prospective label/outcome/prediction/accuracy/utility 与 candidate identity/profile
均未读，`counts_as_distinct_claim_evidence=false`。

## Successor 边界（不改写本 v1 receipt）

在本 context-v1 receipt 中，token packing 仍未冻结；后续独立 successor
`RPM_PREFIX_PACKING_READINESS_20260902.md` 已固定公开 Qwen tokenizer 与 recency-transfer 的完整节点前缀装箱。
同时，RPM v2 明确采用从当前 parent 出发的 breadth-first traversal 和此前 non-buggy 节点；本 v1 的时间倒序规则并不
paper-aligned。v1 继续作为无泄漏 transfer 输入，不得被 successor 的 tokenizer readiness 追溯改称 RPM reproduction。
