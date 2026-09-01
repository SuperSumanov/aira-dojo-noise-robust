# Decision Corpus v11 Schema Dictionary（2026-09-02）

> 状态：`SCHEMA_COMPLETE_FOR_CURRENT_V11_JSONL_NOT_RELEASE_CLEARANCE`。本文件只关闭 v11 cards 与九个
> decision JSONL 的字段定义、类型、nullability、来源、可用时点和敏感等级；它不替代 competition-data、
> credential/PII、逐赛事规则或 license gate。机器盘点与独立复核见
> `phase1/results/release_schema_inventory_v11_20260902/`。

## 1. 绑定范围与方法

机器盘点绑定 `cards_current_v11.jsonl`（16,012 rows；SHA-256=
`6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75`）及
`train/frozen/extension × b0/b1/b2` 九个 decision JSONL（合计 8,107 rows）。脚本逐行只累计 JSON path、
type、presence/null count、array-length bounds、bytes 与 hash；不写出任何 source value、candidate identity、label、
prediction 或 prospective resource。producer 与不导入 producer 的 verifier 对 10 个资源、24,119 行逐字段完全一致；
inventory/verifier SHA-256=`9a48bde7...6440eb` / `d6725443...7b1f8`，focused tests=`3 passed`。

`sha256_normalized_lf` 是 decision 文件的跨平台权威 hash；Windows checkout 的 raw hash 可能只因 CRLF 改变。

## 2. Availability 与 release class 词表

| 词 | 含义 |
|---|---|
| `PRE_EXECUTION` | 候选代码生成后、候选尚未执行时可得；可作为 execution-free critic 输入，但仍须服从具体 protocol。 |
| `PRIOR_EXECUTION` | 来自已执行 parent 的历史状态；不是当前候选的 execution-free 内容。 |
| `POST_EXECUTION` | 只有运行候选后才产生；不得称为 free predictor。 |
| `RETROSPECTIVE_STRUCTURE` | sibling batch/搜索日志形成后才能完整确定；不能假装单候选提议瞬间可得。 |
| `LABEL_ONLY` | external evaluator 或由其派生的 target；训练/评测代码必须与 predictor input 隔离。 |
| `SPLIT_AUDIT_ONLY` | 仅用于 split、cluster、provenance 或审计；原始 ID 不应成为 predictor feature。 |
| `PUBLIC_METADATA` | 原则上可发布，但仍服从最终 dataset license。 |
| `PUBLIC_LABELED_TARGET` | 可作为历史 labeled benchmark 发布；一经公开就不是秘密 leaderboard test。 |
| `CONTENT_SCAN_REQUIRED` | schema 可发布，但 field value 在公开前必须通过 competition-data/credential/PII/path 扫描。 |

## 3. Card JSONL schema

除表中明确说明外，字段在 16,012/16,012 行存在且 JSON type 固定。object/array 容器本身也在机器 inventory 中逐项
记录；下表列可供使用者解释的叶字段。

| JSON path | Type / nullability | Source and semantics | Availability | Release class / sensitivity |
|---|---|---|---|---|
| `id` | string, non-null | `{task}__{journal node id/step}` card identifier | `SPLIT_AUDIT_ONLY` | `PUBLIC_METADATA`; raw ID 不作模型特征 |
| `task.name` | string, non-null | `metric_info.competition_id` / task registry | `PRE_EXECUTION` | `PUBLIC_METADATA`; 公开 task identity |
| `task.type` | string, non-null | fixed `phase1.build_cards:TASK_TYPE` taxonomy | `PRE_EXECUTION` | `PUBLIC_METADATA` |
| `task.metric` | string, non-null | extractor task metadata；schema 不保证语义非空 | `PRE_EXECUTION` | `PUBLIC_METADATA` |
| `task.higher_is_better` | boolean, non-null | inverse of `metric_info.is_lower_better` when supplied | `PRE_EXECUTION` | `PUBLIC_METADATA`; orientation metadata |
| `task.desc` | string, non-null | task description/slug carried by extractor | `PRE_EXECUTION` | `CONTENT_SCAN_REQUIRED`; low/medium |
| `task.medal_thresholds.{bronze,silver,gold}` | number, non-null | external evaluator medal thresholds used by normalization | `LABEL_ONLY` unless protocol explicitly exposes task thresholds | `PUBLIC_METADATA`; label-adjacent |
| `code` | string, non-null | complete generated Python candidate program | `PRE_EXECUTION` | `CONTENT_SCAN_REQUIRED`; high content risk |
| `obs.fidelity.{epochs,data_frac}` | null in 16,012/16,012 | reserved fields; AIRA-dojo source did not natively log them | unavailable | `PUBLIC_METADATA`; must not impute |
| `obs.val_curve` | array, length 0 in 16,012/16,012 | reserved learning-curve field; no observations in v11 | unavailable | `PUBLIC_METADATA`; must not imply curve coverage |
| `obs.val_at_low` | number or null; null 1,344 | candidate self-reported validation metric | `POST_EXECUTION` | `PUBLIC_METADATA`; not execution-free |
| `obs.runtime_s` | number, non-null | candidate execution duration | `POST_EXECUTION` | `PUBLIC_METADATA`; cost signal, not pre-execution feature |
| `obs.error` | null in 16,012/16,012 | reserved execution-error field; v11 retained cards carry no value here | `POST_EXECUTION` | `PUBLIC_METADATA`; missing field semantics |
| `obs.stdout_tail` | string, non-null | last 800 characters of terminal output | `POST_EXECUTION` | `CONTENT_SCAN_REQUIRED`; highest release risk |
| `lineage.parent_val` | number or null; null 7,289 | parent self-reported validation value | `PRIOR_EXECUTION` | `PUBLIC_METADATA`; not current-candidate execution-free evidence |
| `lineage.op` | string, non-null | first recorded search operator, capitalized | `PRE_EXECUTION` | `PUBLIC_METADATA` |
| `lineage.depth` | integer, non-null | legacy parent-count/depth field kept for feature compatibility | `PRE_EXECUTION` | `PUBLIC_METADATA`; do not conflate with `tree_depth` |
| `lineage.parent_id` | string, non-null syntactically | recorded first-parent card identifier | `PRE_EXECUTION` / `SPLIT_AUDIT_ONLY` | `PUBLIC_METADATA`; raw ID not a predictor shortcut |
| `lineage.tree_depth` | integer, non-null | cycle-safe depth from journal root | `PRE_EXECUTION` | `PUBLIC_METADATA` |
| `lineage.children_ids` | array[string], length 0--11 | retained child IDs reconstructed from the journal | `RETROSPECTIVE_STRUCTURE` | `PUBLIC_METADATA`; incomplete source children remain possible |
| `lineage.n_siblings` | integer, non-null | retained siblings sharing recorded parent, excluding self | `RETROSPECTIVE_STRUCTURE` | `PUBLIC_METADATA`; not full opportunity-set size |
| `lineage.step` | integer, non-null | journal build-order index | `SPLIT_AUDIT_ONLY` | `PUBLIC_METADATA`; shortcut-prone |
| `label.graded` | number or null; null 21 | raw external MLE-bench grade | `LABEL_ONLY` | `PUBLIC_LABELED_TARGET`; hidden from predictor input |
| `label.y_norm` | number or null; null 21 | medal-threshold piecewise normalization to [0,1] | `LABEL_ONLY` | `PUBLIC_LABELED_TARGET`; hidden from predictor input |
| `label.medal_bucket` | string, non-null | `none/bronze/silver/gold/invalid`-style derived bucket | `LABEL_ONLY` | `PUBLIC_LABELED_TARGET` |
| `run_id` | string, non-null | validated source run ID or file-contiguity reconstruction | `SPLIT_AUDIT_ONLY` | `PUBLIC_METADATA`; never model input |
| `provenance.run_id_source` | string, non-null | explicit-vs-reconstructed run-ID provenance | `SPLIT_AUDIT_ONLY` | `PUBLIC_METADATA` |
| `provenance.task_type_source` | string, non-null | fixed taxonomy source marker | `SPLIT_AUDIT_ONLY` | `PUBLIC_METADATA` |
| `provenance.label_status` | string on 21 rows; absent on 15,991 | quarantine reason for non-finite historical labels | `LABEL_ONLY` / audit | `PUBLIC_METADATA` |

重要边界：`Card.view()` 的实现会剥离整个 `label`，但它不会自动剥离 post-execution `obs`、`parent_val`、ID 或
retrospective structure。每个 predictor protocol 仍必须显式 allowlist 字段；不能把“在 card view 中”误写成
“决策时免费可得”。

## 4. Decision JSONL schema

九个文件除 `run_id` 外具有同一字段集合。所有 8,107 行的 `clears_tau` 都是 null；其余共同字段均存在。

| Field | Type / presence | Source and semantics | Availability | Release class / sensitivity |
|---|---|---|---|---|
| `better` | string, 8,107/8,107 | external-grade orientation 后的 winning endpoint ID | `LABEL_ONLY` | `PUBLIC_LABELED_TARGET`; target，不得作输入 |
| `worse` | string, 8,107/8,107 | 同一 pair 的 losing endpoint ID | `LABEL_ONLY` | `PUBLIC_LABELED_TARGET`; target，不得作输入 |
| `gap_raw` | number, 8,107/8,107 | 该 budget 下两 endpoint target 的绝对差，写出前 round 到 6 位 | `LABEL_ONLY` | `PUBLIC_LABELED_TARGET`; analysis only |
| `parent` | string, 8,107/8,107 | 两 endpoint 的 recorded parent ID | `PRE_EXECUTION` / audit | `PUBLIC_METADATA`; raw ID 不作 shortcut |
| `task` | string, 8,107/8,107 | competition/task identifier | `PRE_EXECUTION` | `PUBLIC_METADATA` |
| `budget` | integer, 8,107/8,107 | target construction horizon；b0/b1/b2 分别为 0/1/2 | protocol metadata | `PUBLIC_METADATA` |
| `set_size` | integer, 8,107/8,107 | 生成时 retained finite candidates 数 | `RETROSPECTIVE_STRUCTURE` | `PUBLIC_METADATA`; 不是完整 choice-set 保证 |
| `intask_split` | string, 8,107/8,107 | `train` 或 `test`；按 physical run 固定 | `SPLIT_AUDIT_ONLY` | `PUBLIC_METADATA`; train/test 路由 |
| `loto_fold` | string, 8,107/8,107 | leave-one-task-out fold label（当前等于 task） | `SPLIT_AUDIT_ONLY` | `PUBLIC_METADATA` |
| `clears_tau` | null, 8,107/8,107 | 旧 matched-budget pipeline 的保留槽位 | unavailable | `PUBLIC_METADATA`; 不得赋予未记录语义 |
| `src` | string, 8,107/8,107 | decision generator/version provenance tag | `SPLIT_AUDIT_ONLY` | `PUBLIC_METADATA` |
| `run_id` | string, 6,021/8,107 | train 5,816 + extension 205 显式记录；frozen 2,086 行全部缺失 | `SPLIT_AUDIT_ONLY` | `PUBLIC_METADATA`; 见下方重建规则 |

### Frozen `run_id` schema 差异

`decision_frozen_v11_b*` 沿用早期已冻结行，因此没有逐行 `run_id`；这不是 null，而是字段缺失。权威 physical run
由 `better`、`worse` 经 `phase1/card_run_map.json` 重建，二者必须映射到同一 run；若行中显式 `run_id` 存在，
`decision_corpus_audit.py` 还要求它与重建值严格一致。当前 audit 已验证九组全部为 true physical-run siblings，且
同 budget train/frozen 在 pair、endpoint、parent、run 四轴均零交集。使用者不得把 frozen 缺字段填成任意值，必须走
同一 run map 与 hash-bound audit。

### `b1/b2` 的当前路线边界

`b1/b2` 是历史 descendant-budget target resource；当前论文主线不自动恢复 K>=1 lookahead 或多保真方法主张。
主 predictor benchmark 的可解释基础单元是 b0 sibling decision。任何使用 b1/b2 的新 effect claim 都需要新的明确协议，
不能仅因数据文件存在而视为获批。

## 5. Predictor-facing allowlist 原则

默认 execution-free critic 输入只允许：candidate `code`、task context、proposal-time operator/parent/depth，以及协议明确
允许的已执行历史 context。默认拒绝：`label.*`、`better/worse/gap_raw`、split/fold/run/card raw IDs、`obs.*`、
`parent_val`、runtime/stdout/error、retrospective children/sibling counts。若研究问题需要放开某项，必须把它列为单独
estimand，并同步修改所有对照臂的公平契约。

## 6. 本 schema 没有关闭的发布门

- 没有扫描 `code` / `stdout_tail` 的 Kaggle competition-data、credential、PII 或绝对路径内容；
- 没有裁决 22 个 competition rules 或 provider/model output terms；
- 没有生成最终 `LICENSE`、`NOTICE`、`licenses.json`、Croissant 或 Responsible AI metadata；
- 没有读取 prospective first-960/Target-300/Target-522 value、label、prediction、identity 或 private selection；
- 没有把 historical public frozen labels变成一个秘密 leaderboard test。

因此 schema gate 已关闭，但完整数据 release 仍是 `NOT RELEASE CLEARED`。
