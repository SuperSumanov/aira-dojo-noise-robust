# Senior 0819 verified sibling core：隔离可行性结果前预注册

日期：2026-08-29
状态：`FROZEN_BEFORE_SIBLING_ONLY_PARTITION_CLOSURE_READOUT`

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
