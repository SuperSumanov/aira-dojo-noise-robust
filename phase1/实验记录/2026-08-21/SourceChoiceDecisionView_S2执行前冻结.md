# Source Choice Decision View S2：执行前冻结

日期：2026-08-21。上游裁决：
`SOURCE_CHOICE_RAW_MATERIALIZATION_VERIFIED_MODEL_VIEW_BLOCKED`。本记录写于任何 S2 output、模型训练或 frozen
score 之前。

## 唯一问题

能否对 S1v2 已固定的 3,000 groups/8,027 candidates 做一个纯结构、逐字节可复现的 decision-time projection，
在不改 group、candidate、winner 或顺序的条件下，把 post-selection materialization provenance 从所有模型可见文件
中彻底移除，并保留独立的 cluster metadata 供 sealed evaluator 做 task/run 聚类统计。

## 固定输入与输出

输入只允许 S1v2 `public_a` 的 SHA-pinned summary、manifest、independent verification 以及
train/frozen/extension 三个 public JSONL。禁止读取独立 vault 目录、prospective outcome、first-960、grade、gap 或旧
模型结果。

模型视图 group exact allowlist 为 `schema_version/group_id/task/source_size/candidates`；只有 train 额外允许
`winner_candidate_sha256`。candidate exact allowlist 为
`candidate_id_sha256/code/code_sha256/operator/step/depth`。`provenance/source_journal_sha256` 必须从 8,027 个
候选全部删除；`role/run_id_sha256/parent_id_sha256` 不给模型，只进入 exact-field cluster manifest。

输出固定为 train/frozen/extension model JSONL、单一 cluster manifest、summary 与 hash manifest。candidate 顺序、
group 顺序、code bytes/code hash 与所有 identity hashes 逐条保持。frozen/extension winner 字段必须仍为 0。

## 13 项 preflight

1. 当前方向仅是 0DJ input-integrity correction；不恢复 HCE/TD/probe/multifidelity。
2. estimand 是 release-view readiness，不是 accuracy 或 search utility。
3. 三个 source JSONL、summary、manifest、independent verification 全部 SHA 锁定。
4. unit 固定为 3,000 groups/8,027 candidates；不删组、不插补、不去重合并。
5. winner 只原样保留在 train；frozen/extension labels 与 vault 不读。
6. group/candidate/model/cluster 字段集合均 exact-match；extra/missing field 立即失败。
7. code bytes、code SHA、candidate order 与 source size 逐条重验。
8. blocked fields 在结构化对象层计数并全部删除，不依赖文本 grep。
9. model view 与 task/run/parent cluster metadata 分文件，sealed evaluator 通过 group ID 闭合。
10. producer x2、独立 verifier x2；verifier 不 import producer，全部要求 byte-identical。
11. strace 必须对 vault/prospective/outcome/first-960 路径零命中。
12. CPU-only、GPU=0、API=0、base LLM update=0；预计小于 10 分钟。
13. 正式输出拒绝覆盖、先 staging 后只读原子晋升；失败原样保留且不产生科学主张。

## 裁决门

只有全部计数精确、两个 producer/两个 verifier 一致、完整 tests 通过、blocked field/forbidden path/credential/
worktree drift 均为 0，才允许状态 `SOURCE_CHOICE_DECISION_VIEW_READY`。否则 S2 关闭，不允许训练或 LFS 发布。
即使通过，也只证明 model-input integrity；任何 baseline、frozen evaluation、GPU 或方法主张都须另立结果前协议。
