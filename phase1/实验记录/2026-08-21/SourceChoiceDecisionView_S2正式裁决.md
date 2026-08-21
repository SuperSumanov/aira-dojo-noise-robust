# Source Choice Decision View S2：正式裁决

日期：2026-08-21。控制 commit：`fd5c3ee0fdfffe399088e2e3a4394598264239a6`。正式状态：
`SOURCE_CHOICE_DECISION_VIEW_READY`。

## 正结果

S2 在不改 S1v2 的 3,000 groups、8,027 candidates、winner、顺序与 code bytes 的前提下，生成了 exact-field
decision-time model view。`provenance/source_journal_sha256` 各从 8,027 个 candidate objects 全部删除；模型对象
blocked fields=0。run/parent/role 与模型视图分离到 cluster manifest，frozen/extension winner fields 仍为 0/0，
train winner fields=2,109。

producer x2、独立 verifier x2 与全部 hash/census 均一致；focused 18 tests、完整 704 tests 全过。strace 对真实
vault、prospective outcome、first-960 等路径零命中，秘密扫描与 worktree drift 均为 0，正式目录只读。

这是真正解决 0DJ 泄漏的修复：不是要求用户“不要用 provenance”，而是 model JSONL 从 schema 层根本不包含这些
字段；sealed evaluator 也拒绝任何 extra field，并通过独立 cluster manifest 验证 task/run closure。

## 边界

本轮只证明 release-view integrity。没有模型训练、frozen label 读取、predictor accuracy、search utility、
prospective effect 或算法收益。原始 S1v2 仍是内部 provenance-rich 审计层，不可直接用于模型；只有 S2 view 可以
进入未来 benchmark harness 或 LFS release。

下一步若做 train-only OOF，只允许在 2,109 个 train groups 上预注册 split、baseline、primary metric 和 kill gate；
frozen/extension vault 在模型族与选择规则冻结前继续不读。若做 LFS，只上传 S2 immutable model files 与 cluster
manifest，不上传 S1 原始 provenance view 或任何 vault 文件。

证据：

- `phase1/results/source_choice_decision_view_v1_20260821_fd5c3ee/README.md`；
- 远端只读正式目录：`/research/d7/spc/yzyang4/source-choice-decision-view/fd5c3ee-v1`。
