# Senior 0819 decision relation taxonomy：结果前预注册

日期：2026-08-29
状态：`FORMAL_COMPLETE_INTEGRITY_GATE_FAIL`

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

## 正式结果（冻结协议原样执行）

exact public commit=`827fe55dcf03280cd8e9391d4b44c20db38484d3` 的 fresh detached formal 已完成。分类为
`HISTORICAL_RELATION_AWARE_DECISION_TAXONOMY_INTEGRITY_GATE_FAIL`：15 个 hard gates 中 13 个通过，失败的是
`all_decision_endpoints_parent_tasks_and_splits_valid` 与 `train_test_physical_run_overlap_zero`。train/test endpoint 和
unordered-pair overlap 均为 0，但加入 declared parent 的引用闭包后，physical-run overlap=`96`；因此旧文件整体不能称
run-clean relation-aware benchmark，8 个 sibling support gates 全过也不得 rescue frozen strong classification。

三个类的 total/train/test rows 分别为 direct sibling=`1270/952/318`、same-run non-sibling=`2119/1620/499`、
cross-run=`4255/3912/343`。test direct-sibling core 有 318 pairs、29 tasks、89 runs、591 endpoints、282 components；
最大 task/run/component share=`25/159`、`7/106`、`1/53`，8/8 预注册 support gates 通过。这个 aggregate 只支持后续
“确定性隔离 sibling core 并 quarantine 其余 rows”的新可行性审计；它不是本轮 strong-pass，也没有发布 row identities。

producer/verifier A/B 各自逐字节一致，SHA-256=`b75df026f...c6d3` / `d5613fe7...b66a`，独立 verifier 报
`all_aggregate_fields_equal=true`。focused/full=`6/1469 passed`，forbidden opens/network=`0/0`，formal manifest=
`68d845cc6e2801d814bcd320017bce5ae5712c2e01f94dff7a010b1195230f56`。正式包见
`phase1/results/senior_0819_decision_relation_taxonomy_20260829_827fe55/`。GPU/API/model-fit/base-update=`0/0/0/0`，
prospective values、raw archives、模型分数与 search utility 均未读。

证书随后由公开 commit=`9a922abbf15cc769c1867f6991423021d661c5dd` 发布。fresh detached post-push 对 package
manifest、`13/15` hard gates、`8/8` support gates、class counts 与 verifier equality 均复核通过；focused/full=
`6/1469 passed`，credential filename/content=`0/0`，post-push manifest=
`35b168b81ad5488cefd967b19e3f9054c9fa4b5546cf3fdaa775611fbda6b7aa`。
