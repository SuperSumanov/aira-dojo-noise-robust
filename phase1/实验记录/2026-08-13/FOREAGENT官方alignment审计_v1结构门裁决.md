# FOREAGENT 官方 alignment 审计 v1 结构门裁决（2026-08-13）

状态：**GRID-MISMATCH；v1 中止，没有准确率/gap outcome**。

## 触发过程

v1 在 outcome 前要求每个任务的 DeepSeek/GPT 共 6 个文件具有完全相同的无序 pair grid。156 个官方
alignment 文件下载完成并抽取为只含 primitive fields 的 compact JSONL 后，分析连续三次在任何
summary/CSV 写盘前 fail-closed：

1. 26 个 DeepSeek release-run-1 文件的 `log_index` 全为 null；独立检查确认 pair key 与抽取 ordinal
   均唯一，因此将 `log_index` 降为显式缺失元数据并提交修正；
2. Google QUEST 的 `e5fd.py` score 为 NaN，涉及 49 个无序 pairs，在 6/6 文件中对称出现；因无法从
   score 独立定义 winner/gap，提交为两个模型、三次运行都隔离且显式计数；
3. v1 最终触发不可放宽的 pair-grid 门：DeepSeek 三次在 26/26 任务内网格完全一致；GPT 三次在
   20/26 一致，而首次 GPT run 在 6 个任务合计缺 8 个 pair。跨模型/六文件完全相同的冻结条件不成立。

结构检查没有读取或聚合 `prediction`、`correct` 或 confidence；截至 v1 关闭时，
`phase1/foreagent_alignment_audit_v1/` 没有结果文件。故 v1 不允许输出模型准确率或任何 gap 裁决。

## 已验证的结构事实

- selected files：156；tasks：26；models：2；nominal releases/model/task：3；
- compact records：110,620；compact SHA256=
  `480616317ddebb249084dbc8b36b4060fac4b77353fce16b436351eab9c235fe`；
- DeepSeek：3 个完整且任务内相同的 grids；
- GPT：run 2/3 与完整网格一致，run 1 总计缺 8 pairs，涉及 Essay、LMSYS、PetFinder、Random Pizza、
  Stanford Covid Vaccine、TensorFlow Speech；
- 49 nonfinite-score pairs 全部来自 Google QUEST 的一个 NaN endpoint，6/6 文件都存在；
- `log_index` all-null 恰好是 26 个 DeepSeek run-1 files；156/156 文件的 pair key/ordinal 无重复。

## 后续允许动作

另立 v2，且必须在读取任何准确率前冻结：

- DeepSeek 继续作为 primary，使用其 3 次完整同网格发布运行；
- GPT 只作 replication，在每个任务内使用 3 次运行的预先固定交集，并报告 union/intersection/缺失数；
- 不计算跨模型逐 pair accuracy difference，避免不同评测集冒充配对对照；
- 49 nonfinite-score pairs 与 exact ties 对两个模型对称隔离；
- v2 其余 raw-gap、任务内 gap 分位、task bootstrap 与原 gate 保持不变。
