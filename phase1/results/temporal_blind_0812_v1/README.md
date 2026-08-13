# 0812 pre-activation temporal blind holdout

该目录只公开结构 seal，不包含 `blind_views.jsonl` 或 `label_vault.jsonl`。标签值在远端单独封存，尚未用于任何
metric、模型选择或方法修改。

固定事实：805 endpoints、57 个 source-journal physical runs、9 tasks、103 sibling parents/pairs；其中只有 7
tasks 有 sibling pair 支持。它不是 scorer 激活后的 prospective cohort，只能作为 analyst-blind temporal
holdout；由于支持很小，不能单独承担论文确认性结论。

`source_truth_audit.json` 同时记录了旧 step heuristic 的一个反例：57 个 journal 被合并成 56 个 heuristic
runs，1 个 ranzcr heuristic group 含两个真实 journal，且没有 source split。新批次因此必须携带 flatten 前的
显式 run ID。

随后以仓库中的通用 `source_journal_run_ids.py` 从原始 candidate 和 57 个脱敏 journal 独立重放；输出仍为
805 cards / 57 runs / 9 tasks、1 个 heuristic merge、0 个 source split，生成的 run map SHA-256
`31b7f144450682f3f54b4234f407037eb70d9b05b584f7635688479f5ae6a5d2` 与最初独立脚本的 map 完全一致。
重放摘要见 `generic_source_truth_verify.json`；该核验同样没有读取 label vault。

直接哈希与时间见 `seal.json`；全部不含 label 值。
