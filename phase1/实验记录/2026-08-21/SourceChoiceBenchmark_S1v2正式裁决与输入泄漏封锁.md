# Source Choice Benchmark S1v2：物化通过，原始模型视图封锁

日期：2026-08-21。控制 commit：`5d6de6eddad30cef46c5803d8810f835c3f58c4f`。正式发布裁决：
`SOURCE_CHOICE_RAW_MATERIALIZATION_VERIFIED_MODEL_VIEW_BLOCKED`。

## 物化正结果

v1 因错误要求 parent card/code 而在任何正式输出前 fail closed；v2 不删组、不改 winner、不换分母，统一采用
task/run/parent hash 加完整候选代码的 candidate-only context。正式 producer x2 与独立 verifier x2 均确认：

- 3,000 groups、8,027 candidate slots 全部闭合；train/frozen/extension=2,109/778/113 groups；
- 899 个 missing candidates 从 169 个 credential-safe、status-bound journals 恢复，169/169 命中；
- frozen/extension public winner fields=0；train/frozen parent overlap=0、run overlap=0；
- parent card 只在 2,946/3,000 组可用，但 v2 不要求也不输出 parent code，因此 54 个 orphan-context 组没有被
  隐式删除；
- 两次 public、vault 与 verification 均 byte-identical；14 个 focused tests 与 695 个完整 tests 全过。

这正式证明 candidate code reconstruction 和 sealed-label plumbing 可行，是数据基础设施正资产。

## 结果后、模型前发现的输入泄漏

原始候选对象为审计目的携带 `provenance` 与 `source_journal_sha256`。在任何模型训练、frozen label 打开或 frozen
score 之前，对 train public labels 做确定性字段诊断：

- `card` candidates=5,042，wins=2,109；
- `journal_recovered` candidates=697，wins=0；
- 全部 2,109 个 winners 都属于 `card`；496 个 train groups 同时含两种 provenance；
- provenance-aware uniform filtering 的 expected top-1 人为增加 `0.039746120009281544`；固定 min-hash control
  人为增加 `0.034613560929350404`。

这不是模型能力，而是被最终保留/恢复状态携带的 post-selection signal。若把原始 v2 发给 predictor，用户可在不读
代码语义的情况下先排除 697 个已知 loser，污染 frozen benchmark。因此 S1 的物化状态保留为 PASS，但 model-view
release gate 明确为 BLOCKED；不能把两者合并成“benchmark ready”。

## 后续唯一合法动作

下一步只做单独预注册的 decision-time projection：模型可见字段使用 exact allowlist，结构化删除
`provenance/source_journal_sha256`，frozen/extension 继续无 label；聚类统计所需 run/parent metadata 与模型输入分层。
独立 verifier 和 sealed evaluator 必须拒绝任何 extra field，并用 syscall audit 证明 projection 不读取 vault。

该投影是 input-integrity correction，不是 result rescue：本轮没有 predictor outcome，frozen/extension labels 从未打开。
投影通过前不训练 source-choice 模型、不跑 GPU、不发 LFS 数据。唯一主线的 score-channel prospective gate、既有 Qwen
checkpoint 约束与 first-960/strict-future 边界均不改变。

证据：

- `phase1/results/source_choice_benchmark_materialization_v2_20260821_5d6de6e/README.md`；
- 远端只读公开侧：
  `/research/d7/spc/yzyang4/source-choice-benchmark-materialization/5d6de6e-v2`。
