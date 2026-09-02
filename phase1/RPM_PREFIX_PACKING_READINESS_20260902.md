# RPM transfer 的 tokenizer / prefix-packing 门（2026-09-02）

> 状态：`PUBLIC_TOKENIZER_AND_DETERMINISTIC_TRANSFER_PACKING_FROZEN_PAPER_ALIGNED_BFS_BLOCKED`。
> 本门只固定公开 tokenizer、chat wrapper 与完整节点前缀装箱；不下载/加载模型权重，不调用模型，不读取前瞻结果，
> 也不把 transfer 改称 RPM reproduction。

## 先修正一个直接竞品复现边界

RPM v2 正文并不是笼统地“取此前若干节点”：它说明从当前 parent 出发，对已经探索的树做 breadth-first
traversal，收集最多 `K` 个此前 non-buggy 节点。已经冻结的 Decision Corpus context v1 则是另一条保守但不同的规则：
同 run/task、严格早于完整 sibling set cutoff 的全部可评分节点，按 journal step 降序、node SHA 升序排列。

v1 不读取 candidate outcome 或 external grade，因而没有结果泄漏；但它没有 parent-rooted BFS 输入，且当前 cards 无法证明
逐节点的 exact RPM non-buggy predicate。因此 v1 receipt 保持不可变，本文件新增的是 **transfer packing**，不是对旧 receipt
的改写。最终表必须继续叫 `RPM-style inference-only prompt transfer`；只有补齐 parent edges、独立 BFS verifier、exact
non-buggy predicate 和 checkpoint/serving equivalence 后，才允许讨论 paper-aligned reproduction。

## 固定的公开模型与 tokenizer

公开主来源 `Qwen/Qwen3.6-27B` 固定到 immutable revision
`6a9e13bd6fc8f0983b9b99948120bc37f49c13e9`。本门只允许以下五个非权重文件，逐字节绑定：

- `config.json`：4,308 bytes，SHA-256=`69db4eb7...a9d9c`；
- `generation_config.json`：202 bytes，SHA-256=`e70c136c...e550e`；
- `tokenizer_config.json`：16,718 bytes，SHA-256=`5186f0de...b29b`；
- `tokenizer.json`：12,807,982 bytes，SHA-256=`5f9e4d49...1cb42`；
- `README.md`：62,593 bytes，SHA-256=`bb936d6d...51d3d`。

chat template 为 7,764 UTF-8 bytes，SHA-256=`e84f32a2...4259`；tokenizer class=`Qwen2Tokenizer`，
model max length=`262,144`，EOS/PAD=`<|im_end|>` / `<|endoftext|>`。运行时固定为
transformers/tokenizers/huggingface-hub=`4.57.1/0.22.1/0.36.0`，只允许 `local_files_only=True`、
`trust_remote_code=False`；目录中出现任何模型权重后缀立即 fail-closed。公开 revision 不能证明 RPM 作者私有部署使用了
相同 checkpoint/serving stack，所以仍是 transfer binding。

## 确定性装箱规则

1. RPM optimized prompt 仍使用已冻结的 1,950-byte v2 原文；候选 plan 对称使用
   `[PLAN_NOT_RECORDED_BY_DECISION_CORPUS]`；
2. 单一 user message、无 system message，官方 chat template 使用 `add_generation_prompt=True` 与
   `enable_thinking=True`；
3. native window 固定 `262,144` tokens；按官方 model card 的常规输出建议保留 `32,768` tokens，故两个方向的
   prompt token limit 都是 `229,376`。这是 transfer 预算选择，不声称等于 RPM 私有部署；
4. context 在 published prompt 中出现两次，必须在完整渲染后的 chat prompt 上计数，不能只数一次 context；
5. 以 context v1 的完整 canonical JSON 行为原子，依次尝试前缀；AB 与 BA 都不超限才接纳该节点；第一个溢出节点
   立即停止，禁止截断节点、跳过该节点再装后续节点或以字符/字节预算代替 tokenizer；
6. 原始 context 确实为空时保留 `NO_PRIOR_EXECUTED_SCORED_NODE`；有节点但零个能装入时使用不同的
   `NO_COMPLETE_PRIOR_NODE_FITS_TOKEN_BUDGET`，不得混淆数据缺失与预算截断；
7. 输出只记录 packed context、AB/BA token count 与 prompt/chat/token-id hashes，不实现网络下载、模型 transport、
   credential loader、结果 join 或 live call。

producer=`phase1/rpm_prefix_packing.py`；独立 verifier=`phase1/verify_rpm_prefix_packing.py`，后者既不 import
producer，也不 import prompt renderer。两者必须在同一个 hash-bound 本地 tokenizer snapshot 上逐字段一致；已有输出拒绝
覆盖。

## 仍未关闭的门

- parent-rooted BFS / exact non-buggy predicate，或最终表中显式保留 transfer 偏差；
- outcome-blind exact-common-support panel、candidate/context 内容安全审查与 append-only prediction escrow；
- first-960 identity + accrual closure 后才允许结果 join；
- 模型 checkpoint/serving/reasoning 等价性，以及 parse/position/truncation/latency/cost smoke；
- calls/tokens/latency/currency cap 的单独用户批准。

当前 Table 4B=`SEALED`，GPU/API/model fit/base update=`0/0/0/0`，prospective
label/outcome/prediction/accuracy/utility/candidate identity/profile 均未读，
`counts_as_distinct_claim_evidence=false`。
