# Decision-Corpus lineage audit v2（历史 v11，aggregate-only）

权威 source commit：`25148420ee457018a1ee3740c4a1c42da830610d`。冻结 protocol SHA-256：
`ef3aefd1534fb76d7d0a05d0fc4f4b4cbe02ceac8b183acea635b2b9c8d3c88a`。正式分类为
**`HISTORICAL_V11_PARENT_COMPLETE_SIBLING_CORE_LIMITED_SUPPORT`**。

## 结论

15/15 个 hard integrity gates 全过。九个固定 pair sets 共 8,107 行，全部是两个 endpoint 的
`lineage.parent_id` 同时等于 declared parent：parent Card 可见的 strict core 为 7,579 行（`689/737 =
0.93487109905020349`），parent 被裁剪但 lineage 仍可证的 orphan tier 为 528 行；same-run declared-context
non-sibling 与 cross-run context 都是 0。所有 row task/run/split/budget violation、within-set duplicate/reverse
conflict 均为 0；同 budget train/frozen 在 unordered pair、endpoint、parent 与包含 parent 的 referenced physical
run 四层 overlap 均为 0。

六个 train/frozen primary sets 的 36 个 support gates 通过 35 个。唯一失败是 `frozen:b2` strict core 的最大单 run
pair share：`52/254 = 26/127 = 0.20472440944881889`，略高于冻结上限 `1/5`。因此不能把总分类升级为 strong pass。
其余五个 primary sets 全部六门通过；既有 headline `frozen:b0` 保留 1,424/1,498 pairs、21/22 tasks、83/92 runs、
1,929/2,022 endpoints，最大单 run share=`67/356 = 0.18820224719101122`，全部过门。`frozen:b1` 也全部过门。

| population | strict core | all rows | retention |
|---|---:|---:|---:|
| train b0+b1+b2 | 5,397 | 5,816 | 0.92795735900962861 |
| frozen b0+b1+b2 | 1,989 | 2,086 | 0.95349952061361454 |
| extension b0+b1+b2 | 193 | 205 | 0.94146341463414629 |
| all nine sets | 7,579 | 8,107 | 0.93487109905020349 |

## 独立复验

producer A/B 与 verifier A/B 分别逐字节一致；verifier 不 import producer，逐字段重建结果并报告
`all_aggregate_fields_equal=true`。focused/full tests=`13/1488 passed`，full suite 有 47 个既有 sklearn/scipy 弃用警告；
forbidden opens/network/credential filename/content=`0/0/0/0`。远端 `SHA256SUMS` 已逐文件复核，manifest SHA-256=
`117678f333d2f053e2cc29aa8ca1e34238a39e52df5444bdd491e4d0ea9d36e4`。

## 失败与更正记录

1. `formal-170f095-v1` 在 scientific readout 前因 runner 从主工作树寻找九个小输入而失败；无 producer output。
2. `formal-9628c23-v2/v3` 已过输入与全测试，但旧 parser 把 nested Card task object 整体转成字符串，在首行 task
   consistency 处停止；v3 捕获到确切异常，无结果 JSON。
3. `formal-89689b2-v4` 把 metadata violation 改为 aggregate fail receipt，但仍沿用错误 task parser；它虽完整运行，
   其 `INTEGRITY_GATE_FAIL` 是无效 schema 解释，不得引用为语料结论。
4. 生成器 `build_decision_v10.py` 明确使用 `card["task"]["name"]` 写 pair task。commit `2514842...` 据既有 schema
   修复 producer/verifier，并加入 nested-task 等价合成测试；fresh `formal-2514842-v5` 是唯一权威结果。

## Claim boundary

本包支持的是 historical v11 lineage-direct sibling relation、parent-complete curated core、deterministic quarantine 与
run/split closure 的可审计性。它不证明 predictor accuracy/scaling/search utility，不是 prospective confirmation，不把
recorded parent 升级为语义或因果真值，也不主张首个 tree/sibling/pairwise-RM 方法。没有生成 row-level filtered release；
`first-960`/Target-300 prospective values、raw senior archives 均未读取，GPU/API/model-fit/base-update=`0/0/0/0`。
