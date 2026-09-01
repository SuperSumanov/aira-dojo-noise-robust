# Evidence-index erratum（2026-09-02）

## 错误

support-floor protocol 与首次 release 文案把 6 个 prior-supported competition 的 totals、分布范围和 concentration
描述为尚未读取的新量。这个说法不成立：`phase1/CURRENT_DIRECTION.md` 的 0KI 以及
`phase1/results/archive_granularity_retention_v1_20260831_bc88298/a/result.json` 已在一天前正式发布同一 population、同一
prior snapshot 上的核心量。

遗漏发生在证据检索：开发时只沿最新 0KV census 链检查 predecessor，却没有对整个 `CURRENT_DIRECTION.md` 与既有
`phase1/results/` 做 estimand/numeric crosswalk。计算本身、输入哈希、A/B、独立 verifier 和 release 字节均无错误；错误在
“哪些量此前未知”与“这是新突破”的科学定位。

## 精确重叠

旧 0KI 与本包 prior-prefix 的以下量逐项相同：

- affected/prior-supported competitions=`6`；
- accepted archives / physical runs / eligible runs / endpoints=`20/94/92/2558`；
- archive min/median/max=`1/4/5`；
- physical-run min/median/max=`4/17/29`；
- eligible-run min/median/max=`4/17/29`；
- endpoint min/median/max=`50/458.5/944`；
- max eligible-run share=`29/92`；
- max endpoint share=`472/1279`。

旧 result SHA-256=`f28ef79447ded3d642c563cf1a684f86f063a9e0c270949f5f935f995c9a2184`；本包 result
SHA-256=`ce8b30101a26fdba178c6046c24e55a219eacd1e307dc8c033cae754898f4248`。两者 schema 与目的不同，不能要求整文件
相同，但上述共享 estimand 完全复现。

## 仍然有效、但不构成新突破的内容

- 新 producer 与 verifier 是独立实现，正式 A/B 与全字段重建有效；
- 完成后的 14-event census class count=`6 prior + 1 no-support` 被重新绑定；
- current window 只给 1 个 competition 增加 `1` archive、`4` physical/eligible runs、`96` endpoints；
- exactly-one counts 与两个 minimum ratio 是附加 post-hoc 描述，不是独立确认。

因此本包固定分类为 `PRIOR_EVIDENCE_OMISSION_CORRECTED_INDEPENDENT_RECONSTRUCTION`。不得把它与 0KI 分开累计为两项
正结果，不得称新的 fully blind 或 preregistered discovery。

## 防复发

后续任何 aggregate extension 在冻结前必须同时搜索：唯一方向入口、既有 result schemas、关键 totals/ranges/ratios 与
population/snapshot bindings；若共享 estimand 已存在，协议必须把 predecessor 列入 `known_before_readout` 并明确分类为
replication、lineage 或 sensitivity，而非 unknown discovery。
