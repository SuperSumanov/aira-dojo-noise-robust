# Senior 0819 decision relation taxonomy：结果前预注册

日期：2026-08-29
状态：`FROZEN_BEFORE_SPLIT_SPECIFIC_TAXONOMY_READOUT`

## GCCV

Goal：判断已认证 run/endpoint/pair 隔离的 7,644-row historical decision 数据，能否在不看模型分数的条件下，被完整、互斥地
重构为 verified direct sibling、same-run non-sibling、cross-run 三个 relation strata；其中 test 的真实 sibling core 是否具有
足够的 task/run/endpoint/component 广度，可作为后续 relation-aware predictor benchmark 的正资产。

Context：固定 senior commit=`f534114e60658043c07f7a15d6440492caffc8ad`，Cards/run-split/decision 三个 Git-LFS
对象 SHA-256=`5e0f3807...6c343` / `593117cf...03bb` / `1a01d3a1...1442`。前一轮 formal 已知 overall
direct/same-run/same-task=`1270/7644` / `3389/7644` / `7644/7644`，但 split-specific class counts、test sibling
breadth、每类依赖集中度和 fingerprints 均未读取。

Constraints：taxonomy 和门固定在读取上述未知量之前；只使用 Card lineage parent、top-level physical run、task、split 与
unordered endpoint identity，不使用 pair orientation、gap、grade、label、模型 prediction、accuracy 或 search utility。输出仅匿名
aggregate 和 fingerprints，不发布 row identities。CPU-only，GPU/API/model-fit/base-update=`0/0/0/0`。

Verification：固定输入 hash 与 15 个 hard gates；producer A/B 不同 `PYTHONHASHSEED`；不导入 producer 的独立 verifier A/B；
focused/full tests、file/network strace、credential-before-parse、逐字节一致性和 manifest。任一 ambiguity 或 hash drift fail closed。
机器权威 protocol SHA-256=`df94c4ec6a3bb2c0856e29d148cb898d2b796cc1279800456b8f8e6108e08e32`。

## 固定 taxonomy 与最强门

三个类按顺序且互斥：

1. `verified_direct_sibling`：两端 Card 的 `lineage.parent_id` 都等于 declared parent，且三者同 physical run；
2. `same_run_declared_context_non_sibling`：三者同 run，但不满足 1；
3. `cross_run_declared_context`：三者不全在同一 run。

必须先通过输入、Card/run/task/split、taxonomy exhaustiveness/purity、train-test 三层零交叉、零 duplicate/orientation conflict，
并精确复现上一 formal 的 overall aggregate。strongest sibling-core gate 在 test 固定要求 pairs/tasks/runs/endpoints/components
至少 `100/10/30/150/50`，最大 task/run/component pair share 不超过 `1/3`、`1/5`、`1/4`。全过才允许分类
`HISTORICAL_RELATION_AWARE_DECISION_TAXONOMY_BROAD_VERIFIED_SIBLING_CORE`；hard 通过而 support 不全过只能报
`...LIMITED...`，hard 任一失败报 `...INTEGRITY_GATE_FAIL`。不得事后调阈值或用其他 strata/model score rescue。

## 可说与不可说

若 strong pass，可说历史 decision 数据经显式 relation taxonomy 后包含支持面广的 structurally verified sibling core，并可把
其余 rows 保留为同-run/cross-run transport stress strata；这是一项 MLE Decision Corpus 的 benchmark repair/audit 资产。
不能说 recorded parent 是外部语义或因果真值，不能把历史 test 说成 untouched final test，不能升级现有 seed-specific scaling，
也不自动授权 row-level release、GPU 重训或 agent/base LLM 更新。

## 结果前实现

在真实 split-specific readout 之前完成 producer、独立 verifier、六项 synthetic attack tests 与 fresh-worktree formal runner。
producer/verifier/test/runner SHA-256=`f32c9a56...299e9` / `84453ca9...e787f` / `d922222b...8a502` /
`bed7ae49...06fa4`；本地 focused=`6 passed`，与上一 integrity audit 合并=`13 passed`。独立 verifier 不导入 taxonomy
producer，使用上一轮独立 Card stream decoder 后自行重写 relation parsing、graph、fingerprint、profile 与 gates。测试覆盖
三类 strong pass、aggregate-only、parent split mismatch、limited-support 不可 rescue、反向 duplicate/conflict 和 input hash
drift。正式运行前仍只可称执行链就绪，没有真实分类。
