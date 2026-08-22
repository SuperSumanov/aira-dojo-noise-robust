# Senior mixed `ac008af`：生成配方逐字节恢复

日期：2026-08-23。正式状态：`UNIQUE_IN_FROZEN_GRID_AND_BYTE_EXACT`。

## 1. 结论

0DS 中“真实 mixed 文件在 `src/`/`docs/` 零引用、提交时没有 builder command/seed/weights/receipt”的事实不变；
但“因而配方不可恢复”已经被本次后验审计推翻。学长 commit
`ac008af8b907d319b694f26b0ba9cf4053b3bf69` 中的通用 builder 仍存在，四个 LFS 对象也已物化。冻结一个简单、有限且
事前写死的 66-candidate 搜索后，恰有一个候选逐行、逐顺序命中 target；再用原 builder 在 Linux 独立执行两次，两个
输出都与 target 逐字节相同。

恢复出的命令语义为：

```text
datasets = batch_value_pairs_filtered_runsplit.jsonl,
           merged_decision_pairs_filtered_runsplit.jsonl,
           value_pairs_hardware_timelimit_gap_filtered_runsplit.jsonl
weights = 8, 1, 1
n_samples = 15000
use_test_split = merged_decision_pairs_filtered_runsplit.jsonl
seed = 7
```

对应 requested sample counts=`12,000/1,500/1,500`。去重并排除 test-overlap 后 sampled train 为 14,715 条，随后原样
保留 decision test 1,160 条，最终为 15,875 条；全文件 source counts 为 value=13,312、decision=2,563。

## 2. 冻结搜索与唯一性边界

搜索空间没有在查看候选结果后扩大或缩小：

- 三份输入的全部 6 种顺序；
- seed 固定为 7，`n_samples=15000`；
- decision 固定抽 1,500；
- global hardware/time value 从 0 到 7,500、步长 750；
- local batch value=`13,500-global`。

总计 `6 × 11 = 66` 个候选，逐候选独立复刻上游 builder 的 sequential `rng.sample`、统一 shuffle、oriented pair
first-occurrence dedup、sample/test overlap removal 与完整 decision-test append。66 个候选中恰有 1 个与 target 的
15,875 个 parsed JSON objects 全顺序相等。

“唯一”只对这个冻结 66-candidate 简单网格成立，不声称在任意程序、任意随机数实现或任意等价参数化中全局唯一。真正
把 recovered command 锚定到 artifact 的强证据是下一节原 builder 的逐字节复现。

## 3. 两层独立验证

第一层是本仓库的独立实现：从锁定输入 SHA 读取 pair JSONL，重放唯一候选，并按上游
`json.dumps(ensure_ascii=False,separators=(",",":")) + "\n"` 序列化。输出：

- rows=`15,875`；
- bytes=`6,625,497`；
- SHA-256=`7792a7da4119bb607cf76628fcdde19923898651ac734ff6afffb0732883cf6e`；
- parsed sequence equal=`true`；serialized bytes equal=`true`。

第二层不调用上述独立实现生成数据，而是在 Linux fresh detached worktree 上锁定 senior `ac008af8...`，直接运行原
`build_decision_augment_pairs.py` 两次。两次均打印 14,715 sampled + 1,160 retained test，且 rows、bytes、SHA 全部与
target 相同；两次输出之间 `cmp` 也相同。因此 Windows 换行差异没有混入正式结论，正式逐字节证据来自 Linux 原
builder。

同一独立恢复器又在 Linux/Python 3.11.15 连续执行两次，两份 receipt 逐字节相同；其 scientific-core SHA-256 与
Windows/Python 3.13.4 receipt 同为
`3a7ef3ade0dc98ff16e00527e36ddae32a8e6274f11343d6dc2fcfb2fa91bdb5`。运行环境字段不同，因此不要求完整 receipt
文件 SHA 跨平台相同。

聚焦 synthetic tests 覆盖冻结 grid cardinality、权重分配、dedup/test retention、候选区分、UTF-8/LF 序列化、输入
SHA/size fail-closed、credential-shaped bytes 拒绝，以及同一 Git blob 的 CRLF/LF worktree 等价验收。远端首次验收
曾按预期拒绝 Windows checkout 的 raw CRLF SHA；这不是配方失败。修正后的门同时锁定 senior commit 的 Git blob
SHA-1 与 normalized-LF SHA-256，再次远端验收才允许通过。

## 4. 访问边界与没有做的事

恢复器完整解析了四份历史 pair JSONL，因此如实记录其读取了 `gap_raw` 等 pair-construction metadata；不能称为“不读
任何 outcome-derived metadata”。它没有打开 Cards、solution code、raw grade、prospective outcome vault、checkpoint
或模型 prediction。GPU jobs/API calls/model fits 均为 0。

## 5. 对实验门的精确影响

这是正面的复现资产：mixed artifact 的输入顺序、权重、sample counts、test retention 与 seed 现在都可重建，0DS 的
“配方不可恢复”阻断撤回。

但 GPU 门仍保持关闭，原因是其他阻断项相互独立：

1. 1,160 条旧 decision test 已被训练期周期评估，不能作 one-shot frozen confirmation；
2. producer-side physical-experiment provenance 尚未提供真实 manifest，异常 archives 也未替换；
3. Cards LFS 对象 fresh fetch 仍返回 404；
4. launcher 引用错误文件名；
5. 同一 commit 同时改变 prompt、mixture 与 ZeRO/offload，无法单旋钮归因；
6. 生成时仍没有不可变 receipt；本次只能提供后验恢复证据。

因此正式裁决从“protocol + recipe reproducibility blocked”收窄为“recipe recovered；identity/protocol/LFS/single-knob
blocked”。这不是 mixed objective 的效果确认，也不改变严格前瞻 score-channel 主线。

## 6. 证据

- `phase1/recover_senior_mixed_recipe.py`；
- `phase1/tests/test_recover_senior_mixed_recipe.py`；
- `phase1/results/senior_mixed_recipe_recovery_20260823/formal_receipt.json`；
- `phase1/results/senior_mixed_recipe_recovery_20260823/remote_verification.json`；
- `phase1/results/senior_mixed_recipe_recovery_20260823/README.md`。
