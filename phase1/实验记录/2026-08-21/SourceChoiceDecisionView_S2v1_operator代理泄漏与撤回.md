# SourceChoiceDecisionView S2v1：operator 代理泄漏与撤回

日期：2026-08-21。裁决：`SOURCE_CHOICE_DECISION_VIEW_V1_MODEL_BLOCKED`。

S2 v1 发布到 Git LFS 后、任何模型拟合或 frozen 解封前，train-only 模型预检发现 `operator` 大小写保留了
重建来源：全角色小写 `improve` 恰有 899 个，与 S1v2 已独立确认的 899 个 journal-recovered candidates
总数相等；训练侧小写 `improve`=697 slots / 0 winners。大写 `Improve`=4,949 slots / 2,071 winners，
`Draft`=93 slots / 38 winners。因此 `provenance/source_journal_sha256` 虽已删除，模型仍可通过大小写无损恢复
同一 post-selection proxy。

这次发现发生在模型拟合=0、GPU/API=0、frozen/extension winner vault 未读的边界内，因此没有需要撤回的
predictor accuracy；需要撤回的是 0DK 的“model view ready”状态。四个 LFS payload 不覆盖、不删除，作为失败产物
保留并在 README/BLOCKED 中显式封锁。

候选数组按 candidate SHA 字典序；first/last/min-SHA/max-SHA 的训练 top-1 为
0.390232337601/0.411095305832/0.390232337601/0.411095305832，exact uniform expected 为
0.400178014652，未发现类似位置捷径。5,739 train slots 的 candidate ID 全唯一；7 个重复 code hashes 均未跨
physical run 或 task。这些只是辅助描述，不能抵消 operator 代理。

后续只能新建 v2：大小写不敏感地把 `draft/improve` 规范化为固定 `Draft/Improve`，未知值 fail closed；其余
group/candidate/winner/order/code bytes/step/depth/split/cluster metadata 全部保持。必须 producer×2、独立 verifier×2、
focused/full tests、forbidden-path/credential/read-only 门全过，才可重开 train-only OOF。
