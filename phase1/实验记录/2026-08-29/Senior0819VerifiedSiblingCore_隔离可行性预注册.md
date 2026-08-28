# Senior 0819 verified sibling core：隔离可行性结果前预注册

日期：2026-08-29
状态：`FORMAL_COMPLETE_QUARANTINE_FEASIBLE`

## GCCV

Goal：在 0HT 已正式判定旧 7,644-row decision 文件整体完整性失败后，验证一个不读取模型分数、不给出行 identity 的
确定性 repair 是否可行：只保留结构上可核验、parent/task/run/split 闭合的 direct-sibling core，把所有其余 rows 明确
quarantine；核心 train/test 是否在 unordered pair、endpoint 和包含 declared parent 的 physical-run closure 三层均无交叉。

Context：固定 senior commit=`f534114e...`、0HS taxonomy protocol=`df94c4e...`、0HT formal summary/verifier=
`b75df026...` / `d5613fe...`，以及已公开证书 commit=`9a922abb...`。本次冻结前已经知道三类 total/train/test counts，
知道 full-file referenced-run overlap=96，也知道 test sibling support=318 pairs / 29 tasks / 89 runs / 591 endpoints /
282 components；这些支持数字不再作为“新发现”。尚未直接读取 sibling-only parent-partition closure、sibling-only
train/test referenced-run overlap、partition mismatch 在 relation×split 的聚合分布或 quarantine fingerprint。

Constraints：core 规则不含 label、grade、pair orientation、prediction、accuracy 或 search utility；不调阈值，不从历史模型
表现选择 rows。输出只含匿名 aggregate 与不可逆 fingerprint，不产生 row-level release。历史 test 已被周期使用，结果只可称
post-hoc benchmark repair feasibility。GPU/API/model-fit/base-update=`0/0/0/0`，不读取 first-960/Target-300 值或 raw archives。

Verification：16 个 hard gates，producer A/B 不同 `PYTHONHASHSEED`，不导入 producer 的独立 verifier A/B，synthetic
attacks、fresh-worktree focused/full tests、credential-before-parse、file/network trace 与 manifest。任一 input/certificate/hash/
partition ambiguity fail closed。机器权威 protocol SHA-256=
`f4d09f1203ba72181046ac620862eb10351736cd01a25ac3597b21e4b931b680`。

## 固定 repair 规则

`verified_direct_sibling_core` 当且仅当：两个 endpoint 的 `lineage.parent_id` 都等于 declared parent；三张 Card 同一 task、
同一 top-level physical run；row split 等于三张 Card 的 frozen run partition。其他全部 rows 进入 quarantine，并只按冻结的
三类 relation 与 parent-partition mismatch 状态报聚合计数。

核心必须同时通过：规则 purity；core/quarantine exhaustive-disjoint；parent partition closure；所有 mismatch 均在
quarantine；train/test unordered-pair、endpoint、含 parent 的 referenced-run overlap 都为 0；零 duplicate/conflicting
orientation；split counts/fingerprint 与 0HT direct-sibling stratum 完全一致。descriptive support compatibility 沿用 0HS 的
固定门，但其数值在本次冻结前已经已知，不能包装成独立确认。

全部 hard gates 和 compatibility gates 通过才报
`HISTORICAL_VERIFIED_SIBLING_CORE_QUARANTINE_FEASIBLE`；hard 通过、支持不足报 `...LIMITED_SUPPORT`；任一 hard
失败报 `...INTEGRITY_GATE_FAIL`。不得通过调整 core 定义、门槛或查看模型分数 rescue。

## 可说与不可说

若通过，可说：旧 mixed decision 文件可由一个确定性、结构定义、结果盲的 quarantine 规则提取出 run-clean historical
sibling core，适合作为 MLE Decision Corpus 的可选 curated view 和审计示例。不能说这是 untouched/prospective test，
不能说 recorded parent 是语义或因果真值，不能升级旧 scaling，不能自动发布行 identities，也不能直接推出 predictor
效果或端到端搜索收益。

## 结果前实现

在真实 sibling-only closure readout 前完成 producer、独立 verifier、六项 synthetic tests 与 formal runner。producer/
verifier/test/runner SHA-256=`c23f5a43...4d04` / `58adabb2...cdd4` / `772e1974...d4e1` / `28d882ad...c580`；
本地 focused=`6 passed`，与 0HS taxonomy tests 合并=`12 passed`。独立 verifier 不导入本轮 producer，而是使用上一轮
独立 Card/decision decoder 后自行重建 core selection、partition mismatch、graph、fingerprint、overlap、support 与
classification。攻击覆盖 cross-run parent mismatch 全量隔离、aggregate-only、core 反向 duplicate/conflict、已知支持门
不足不可 rescue、parent certificate hash drift 与 input hash drift。正式运行前仍只有冻结执行链，没有真实 classification。

## 正式结果（冻结规则原样执行）

exact public commit=`254fc804c4904635e8f44e9121eab84b425ca6a8` 的 fresh detached formal 已完成，分类为
`HISTORICAL_VERIFIED_SIBLING_CORE_QUARANTINE_FEASIBLE`。16/16 hard gates 与 8/8 descriptive compatibility gates
通过。core=`1270`（train/test=`952/318`），quarantine=`6374`（`5532/842`）；core 的 train/test unordered-pair、
endpoint、含 declared parent 的 referenced-run overlap 均为 0，duplicate/conflicting orientation=`0/0`，split counts 与
fingerprints 精确匹配 0HT parent certificate。

新增的 partition 诊断为：743 条 parent-partition mismatches 全部属于 cross-run stratum（train/test=`516/227`）；direct
sibling 与 same-run non-sibling 均为 0。test support 仍为冻结前已知的 318 pairs / 29 tasks / 89 runs / 591 endpoints /
282 components，不能包装成新确认；本轮新增证据是 deterministic core 的 parent/run closure 与所有 mismatch 的完整隔离。

producer/verifier A/B 各自逐字节一致，SHA-256=`4f4902ce...56315` / `8b0eb843...57ca0`，独立 verifier 报
`all_aggregate_fields_equal=true`。focused/full=`6/1475 passed`，parent package manifest 全项通过，forbidden opens/
network=`0/0`，formal manifest=`9a554d8c1ed3dffe5a5aa1ab7ff1579f890fa749fcbb82e545c3a2a7758d2d63`。正式包见
`phase1/results/senior_0819_verified_sibling_quarantine_20260829_254fc80/`。row-level release 未创建；GPU/API/model-fit/
base-update=`0/0/0/0`，prospective values/raw archives、模型分数与 utility 均未读。

证书随后由公开 commit=`04ed63ebd08bc6406d863b43c93ec61f44b97126` 发布。fresh detached post-push 对 package
manifest、`16/16` hard gates、`8/8` compatibility gates、core/quarantine counts、743 条 mismatch 定位与 verifier
equality 均复核通过；focused/full=`6/1475 passed`，credential filename/content=`0/0`，post-push manifest=
`4e7093b20bec14cfd5a957db253812125f0620fff24123b9ad9460cb223e6d44`。
