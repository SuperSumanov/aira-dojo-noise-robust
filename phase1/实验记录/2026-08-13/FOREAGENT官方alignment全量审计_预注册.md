# FOREAGENT 官方 alignment 全量审计预注册（2026-08-13）

状态：**读取任何全量准确率 aggregate 前冻结**。这是公开发布物的外部复算，不消耗 API/GPU，也不改变
schema/probe-first 主实验。此前只下载过一份 APTOS DeepSeek alignment 用于确认 JSON 字段和行数；只打印
第 0/1/末行的字段类型与截断 reasoning，未计算准确率、gap 分层或任务 aggregate。

## 1. 输入与选择锁

- 官方 GitHub：`zjunlp/predict-before-execute@c4d52cf99bd870d830b456ac7c0684aec1aef375`；
- 官方 Hugging Face dataset：`zjunlp/PredictBeforeExecute@6b322cb88bdbcb2b2d3897ec7d0ded94a5bb2d06`；
- 根目录：`solutions_subset_50/<task>/report/`；必须恰有 26 tasks；
- 每 task 只选文件名严格匹配
  `alignment_<task>_n2_data-both_<model>_<temperature>_pboost_cot_<timestamp>.json` 的发布物；
- model family 固定为 DeepSeek 的完整 `deepseek-reasoner` 三次网格和 GPT 的完整 `gpt-5_1` 三次网格，
  每 task/family 必须恰有 3 个文件，总计 156；这与根目录 3+3 份 pinned all-task report 文件名一致；
- Essay 任务另有一份更晚的单任务 `DeepSeek-V3_2-Thinking` alignment。它不构成 26-task triplicate，
  也不属于上述六份 all-task reports，故在读取 outcome 前显式列入 manifest 的排除项，不混入 primary；
- 不选择 `grade_report` 内容，根目录 report 只读文件名、bytes 与 oid 以锁定完整运行网格；
- 每个文件的 path、bytes、Git/HF oid、model token、temperature token、timestamp 在 outcome 下载前
  固化到 manifest。绝不把两个 `0p0` 和一个 `1p0` 重新描述成“三次同温度运行”。

manifest 选择失败、文件数不符或发布 revision 改变时 fail-closed，不按新文件补结果。

metadata-only builder 已在 outcome 下载前通过：26 tasks、156 selected files、861,305,044 bytes；JSON
manifest SHA256=`3df2715b2d2e5f3cc6193c07c99eb682e042e8aa6cb724b046b2469b35773a4e`，CSV SHA256=
`83d8272e5d74a6f8837b2ae10a20f419ca88c3a23a245c97da2ae8b579e558cc`。DeepSeek 文件精确为 52 个
`0p0` 与 26 个 `1p0`，GPT 为 78 个 `1p0`；唯一排除项即上文 Essay 单任务追加文件。

## 2. 解析与完整性锁

每条只读取 `solutions[{path,score}]`、`groundtruth{best_index,is_lower_better}`、
`prediction{best_index,confidence}`、`log_index`、`correct`；reasoning 不进入任何指标。以
`task + sorted(solution paths)` 为无序 pair key，并按 score 与 `is_lower_better` 独立重算真实 winner 和
correctness，不信任发布物的 `correct` 字符串。

必须先验证：

1. 每个 task 的 6 个文件具有完全相同的无序 pair grid；
2. 同一 pair 的两端 score、`is_lower_better` 和非平局 winner 跨文件一致；
3. 每个 task/family/pair 恰有 3 次发布预测；
4. `prediction.best_index` 为 0/1、confidence finite 且在 [0,1]；每个 task/run 的有效预测覆盖至少 99%；
5. 非平局时发布 `groundtruth.best_index` 与 score 推导一致；
6. 至少 24 tasks 在任务内最低/最高 gap 四分位各有至少 20 个非平局 pair。

任一 grid/ground-truth 一致性门失败时停止中心准确率裁决并报告 `GRID-MISMATCH`；支持或预测覆盖门失败
则报告 `INSUFFICIENT-SUPPORT`，不得悄悄取交集或删掉困难任务。

首次全量分析在写任何 summary/CSV 前 fail-closed：26 个 DeepSeek release-run-1 文件的 `log_index`
全部为 null，其他文件该字段可用。独立结构脚本确认 156/156 文件的 extraction `ordinal` 和无序 pair key
均唯一，pair-duplicate sources=0；`log_index` 从未在预注册中定义为 pair key 或一致性门，故冻结修正为
继续用 `task + sorted(paths)` 作唯一主键、`ordinal` 检查抽取完整性，并把 `log_index` null/duplicate 计数
写入 integrity summary。该修正发生在任何准确率/gap aggregate 产生之前，不允许用它删行或改变 gate。

exact-score ties 单独计数，不进入方向准确率、gap quantile 或 gate。官方论文的 18,438 与自动 parquet 的
18,361 相差 77；本审计事先**不假定**这 77 都是 ties，只在全量核对后描述。

第二次全量分析同样在 summary/CSV 写盘前 fail-closed：Google QUEST 有一个 solution `e5fd.py` 的 score
为 NaN，形成 49 个无序 pairs；它们在 6/6 发布文件中完整出现，共 294 records，其他 pair endpoint 为
finite，且没有 pair/ordinal 重复。因为这些 pair 无法从 score 独立定义 winner 或 gap，冻结处理是把完整
49 pairs 从两个模型、三次运行的所有方向准确率和 gap 指标中对称隔离，同时报告
`nonfinite_score_pairs=49`；不得依据 prediction 或发布 `groundtruth` 恢复标签。该规则仍在任何准确率/gap
aggregate 产生之前确定。18,438−18,361 是否恰等于 nonfinite pairs 加 exact ties 留给一次性结果核对。

## 3. outcome 前固定指标

三次发布运行不是独立 pairs。先对每个 `model × task × pair` 的三次 recomputed correctness 取平均，再算：

- primary：26 个 task accuracy 的等权平均（task-macro）及 task bootstrap 95% CI；
- secondary：所有 pair-average correctness 的 pair-weighted micro accuracy，并用 task-cluster bootstrap；
- 每个发布文件的 accuracy、index-0 pick rate、valid coverage、mean confidence、10-bin ECE；
- 固定 raw-gap 桶：
  `[0,1e-4),[1e-4,3e-4),[3e-4,1e-3),[1e-3,3e-3),[3e-3,1e-2),`
  `[1e-2,3e-2),[3e-2,1e-1),[1e-1,3e-1),[3e-1,∞)`；
- `gap<1e-2` 只作尺度敏感的 secondary 描述；
- 每个 task 内对非平局 raw gap 用相同 gap 的 average rank 定义 empirical percentile：若相同 gap 占排序
  zero-based `[lo,hi]`，则 percentile=`((lo+hi)/2+0.5)/n`；固定报告 quartiles 和 deciles；
- 每个 task 的最高 gap 四分位 accuracy 减最低四分位 accuracy，再对 task 等权平均并 task-bootstrap；
- 三次发布运行之间的预测一致率、temperature/config 明细和两端位置偏差；
- per-run、per-task、raw-gap、within-task quartile/decile 表全部落盘。

bootstrap 固定 seed=`20260813`、10,000 replicates、percentile CI `[2.5%,97.5%]`。release runs 先在 pair
内平均，禁止把 3×18,438 当独立样本；同一 task 内 solutions 的组合复用也禁止使用 pair-binomial CI。

## 4. 冻结裁决门

DeepSeek 是预注册 primary，GPT 是不改变 gate 的 replication：

- **LOCAL-DIFFICULTY-CONFIRMED**：DeepSeek 任务内最低 gap 四分位 task-macro point ≤0.55，95% CI
  包含 0.5，且“最高−最低四分位”的 task-paired 95% CI 下界严格大于 0；
- **GAP-ALONE-WEAKENED**：DeepSeek 最低四分位 95% CI 下界严格大于 0.55；
- 其余为 **INCONCLUSIVE**。

若 GPT 同方向且 paired-difference CI 也大于 0，只能作为跨模型 replication 加强主张；若反向，必须完整
报告，不能改 primary。该门检验“全局组合评测中的局部难对是否接近随机”，不证明我方 sibling 失效完全
由 gap 因果导致，也不等价于 FOREAGENT agent-level 效果无效。

## 5. 允许和禁止的论文主张

若门通过，允许说：全局近穷举 pair accuracy 是配对分布的加权平均，任务内局部近邻对显著更难；结合我方
真实 sibling pair 的 hard-share 明显更高，decision-aware / gap-aware benchmark 是必要的。禁止说：

- “FOREAGENT 的 61.5% 是假的”或其 6× agent-level 加速被本审计推翻；
- raw `gap<1e-2` 在所有任务具有相同语义；
- 18,438 pairs 独立，或只凭 solution 复用就断言原显著性无效；
- 本外部审计替代我方新 physical-run 的前瞻验证。
