# Raw choice-set completeness：结构审计预注册

日期：2026-08-14。状态：结果前冻结。触发原因：只读统计发现 281/281 个现有 production configs 均为
`step_limit=20, num_children=5, max_debug_depth=20, max_llm_call_retries=3`，而 v11 b0 的发布 parent 大多只有
2–3 个可见 candidates。两者可能由剩余预算、debug、不同历史 generator 或有限标签过滤解释，也可能意味着
“choice-set-faithful”表述过强。结果出来前先冻结以下审计，不调模型、不看 first-960 outcome。

## 1. 审计问题

对 v11 的 `train/frozen/extension` 三个 b0 文件，每个 `(partition,parent)`：

1. `P_raw`：`cards_current_v11.jsonl` 中所有 `lineage.parent_id=parent` 的直接 children；
2. `P_finite`：`P_raw` 中 `label.graded` 可解析为有限数的 children；
3. `P_edges`：发布 b0 rows 中出现的 endpoint IDs 与无向 pair edges；
4. `set_size`：发布 row 声明的候选数。
5. `P_source_size`：每个保留 child 的 `lineage.n_siblings+1`。`cards.py` 明确定义 `n_siblings` 为原始
   journal 中共享 parent、排除自身的 siblings 数，并在 `build_cards.py` 按可用官方标签丢 card 之前计算；因此它是
   当前不重读 senior tar 的 source choice-set size 证据。

只比较身份、parent、task、physical run、有限/非有限状态、集合大小与 edge topology；不读取 card code、stdout、
runtime、submission、模型预测或 first-960。pair 的 better/worse 只转换成无向边，不分析方向、gap 或准确率。

## 2. 预先固定的完整性量

- endpoint fidelity：每个发布 endpoint 必须属于对应 `P_raw`，且 endpoint/parent 必须同 physical run；
- finite endpoint fidelity：发布 endpoint 还必须属于 `P_finite`；同 parent 的全部 retained raw children 必须与发布行
  的 task/run 一致。若 parent card 自身仍在语料中，它的 task/run 必须一致且 `children_ids` 必须覆盖 retained children；
- finite-set declaration：`set_size == |P_finite|`；
- endpoint coverage：`|P_edges endpoints ∩ P_finite| / |P_finite|`；
- raw-to-finite loss：`1-|P_finite|/|P_raw|`；
- graph coverage：实际唯一无向 edges / `choose(|P_finite|,2)`；
- raw/finite/published endpoint count histogram；
- source retention：`|P_raw|/P_source_size` 与 `|P_finite|/P_source_size`，并要求同 parent 所有保留 children 的
  `n_siblings+1` 一致；
- parent-mapped 与 orphan parent 分开报告；
- `|P_raw|>5` 的 parent 数、run/task/source 支持只报聚合，不事后删除。

所有比例同时报告 parent-macro、run/task 分布与分子分母。ties 会造成 edge graph 不完整，但不能被写成“漏候选”；
因此 endpoint coverage 与 graph coverage 分开，旧 audit 的 `complete_parent` 只能称 pair-graph complete。

## 3. 预先固定的裁决

结果前 schema probe 已抽查一组：cards 中保留 2 个 direct children，但两者均记录 `n_siblings=4`，即
`P_source_size=5`。这项抽查在全量统计前公开保留，不能被后续均值覆盖。

只有同时满足以下条件，才允许把 b0 称为 **完整 choice set**：

1. endpoint fidelity 100%；
2. finite-set declaration mismatch=0；
3. parent-level finite endpoint coverage =1；
4. `|P_raw|=P_source_size` 且 `|P_finite|=P_source_size` 的 parent share=1；
5. 所有 `|P_raw|>5` 或 `P_source_size>5` 的情况都能由已记录 generator contract 解释，不能仅因占比小忽略。

即使全过，也不得称“simultaneously generated candidates”：当前 MCTS 是 child-by-child 生成/执行，且 debug 可能
发生在同一 expansion block 内。允许的表述只是“同一 physical parent 下实际实现、有限且可评分的 direct siblings”。

若 1 或 2 失败，撤回当前 pair 数据完整性并修发布物；若 3 或 4 任一失败，立即撤回“choice-set-faithful / 完整
choice set”，统一改称 **labeled sibling fragment**，主结果必须加入 source-retention/missingness 边界或重建 raw
journal choice sets；若 5 未解释，暂停 prospective confirmatory interpretation，先修 provenance。

这里的结构完整性还包括：`n_siblings+1` 在同 parent retained children 间一致且不小于 retained 数；若不一致，
裁决为结构无效而不是 fragment。`P_source_size>5` 即使结构上完整，也只进入 provenance hold，不能自动放行
“完整 choice set”主张。

## 4. 复现与隔离

- 输入固定为当前 commit 所引用的 v11 cards、run map 与三个 b0 artifacts；逐文件记录 SHA-256；
- 输出写新目录，producer 与不导入 producer 的 verifier 分开；
- bootstrap/模型训练/GPU/API 均为 0；
- 失败和不完整 parent 全部保留，禁止按 task、set size 或结果删行；
- 结果产生后不得修改上述阈值，只能按裁决更新 `CURRENT_DIRECTION.md`。

透明性记录：在全量统计前为确认 schema，曾有一次只读命令意外把一条完整 card 行打印到本地终端，因此暴露了
该单条 card 的 label 数值。裁决阈值与 source-size schema probe 在此之前已经冻结；全量程序不使用 label 大小，
只使用“能否解析为有限值”这一 availability bit。该事件不涉及 first-960，也不得用于删 task、改阈值或解释结果。
