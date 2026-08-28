# Decision Relation Integrity Contrast v1：正式裁决

## 裁决

正式分类为 `HISTORICAL_RELATION_INTEGRITY_DIAGNOSTIC_AND_REPAIR_CONTRAST`。

这是已知结果后的 aggregate-only descriptive synthesis。它支持一个窄但正面的数据集/审计主张：现有审计栈在两个历史资源
家族上不是 constant-accept 或 constant-reject；它接受 lineage-clean canonical v11 的 hard-integrity certificate、拒绝
relation-mixed 0819 certificate，并且 fixed direct-sibling quarantine 得到一个 referenced-run overlap 为零、通过其独立
repair 协议的 core。

它不支持一般 audit-method novelty、calibrated sensitivity/specificity、因果资源质量比较、predictor effect/scaling、search
utility、prospective confirmation 或 row-level release。

## 聚合结果

| 证书 | 全部 rows | direct sibling / lineage-direct | non-direct / quarantine | hard gates | support gates | train/test referenced-run overlap |
|---|---:|---:|---:|---:|---:|---:|
| canonical v11 | 8,107 | 8,107 | 0 semantic non-direct | 15/15 | 35/36 | 0 |
| mixed 0819 taxonomy | 7,644 | 1,270 | 6,374 | 13/15 | 不适用 | 96 |
| mixed 0819 fixed quarantine | 7,644 source rows | 1,270 core | 6,374 quarantine | 16/16 | 8/8 | 0 |

- canonical lineage-direct share=`8107/8107=1`；parent-present strict-core retention=
  `7579/8107=0.93487109905020349`，另有 528 个 orphan-parent lineage-certified rows。
- mixed verified-direct share=`1270/7644=0.16614338042909471`；non-direct/quarantine share=
  `6374/7644=0.83385661957090529`。
- mixed 的 non-direct 分解为 same-run non-sibling=`2119`、cross-run=`4255`。
- parent-partition mismatch=`743`，且 `743/743` 均位于 cross-run stratum；direct sibling 与 same-run non-sibling 均为 0。

三套 gate schemas 相关但不相同，表中的 pass counts 只能在各自原协议内解释，不能作为共同分数比较。尤其 canonical 唯一
support failure `frozen:b2.maximum_single_run_pair_share` 必须保留。

## 复验链

- source commit：`f66cbdf10989da2e1242964259f31fb8d399db3e`；
- protocol SHA-256：`9b647d1e25786631875114893604650c273a36051c815d976ab189602e0feb37`；
- contrast / independent verifier SHA-256：`96ce116570a6144b50c91bc39de99028614927c2c378d98dbd6a921eaed4a1b4` /
  `1779e696251430347e2574915c2fd07c75e01004be925cd4beae088cc63c5ec2`；
- 三个 source package manifest SHA-256：`4c72c324...d45447` / `6ce816fa...faa7` / `3f6202fb...84a28`；
- focused/full tests：`34/1510 passed`，47 warnings；
- producer/verifier A/B：各自逐字节一致；
- forbidden opens/network calls/credential filename/content hits：`0/0/0/0`；
- formal manifest：`ab2b6fa69fa6705dbd442488067b63d0aea63eb6dc9c326a8bd0cef08087af54`；
- postflight manifest：`b50a9a2941b360d5ca40b1de8c3887512b4a9ef80ac1b1969e4864ab49f57b9e`；
- publication package manifest：`36320ae5d8f43e26906a085e8c11bca1e4be5f8946b45acaec81fdf78efd5c1e`（21 members）。

postflight 重新验证 formal 全 manifest、输出哈希、关键字段、目录只读性和 source commit 已在公开目标分支；本地又独立重建
contrast/verifier，与 formal 逐字节相同。

## 范围与安全

只读取三个已发布 aggregate packages。没有读取 first-960/Target-300 的 label、outcome、prediction、accuracy 或 search
utility，没有打开 senior raw archives，没有输出 row identities / pair orientations，也没有创建 row-level release。
GPU/API/model-fit/base-update=`0/0/0/0`。
