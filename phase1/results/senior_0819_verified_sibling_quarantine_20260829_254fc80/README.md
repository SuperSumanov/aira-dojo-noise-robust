# Senior 0819 verified sibling core：正式隔离可行性证书

正式分类：`HISTORICAL_VERIFIED_SIBLING_CORE_QUARANTINE_FEASIBLE`

这是 0HT 整体 relation taxonomy 失败后的**独立、结果前冻结的 post-hoc repair 审计**。固定规则只保留 endpoints
都是 declared parent 的直接 children，且 parent/endpoints 同 task、同 physical run、同 frozen split 的 rows；其余 rows
全部进入 quarantine。本轮 16/16 hard gates 通过，证明该规则可提取一个 parent/run-partition 闭合的历史 sibling core。

## 正式结构结果

- core=`1270` rows（train/test=`952/318`）；quarantine=`6374` rows（`5532/842`）；二者 exhaustive-disjoint；
- core train/test 的 unordered-pair、endpoint、包含 declared parent 的 referenced physical-run overlap 均为 0；
- core unordered duplicates/conflicting orientations=`0/0`；split counts 与两个 orientation-free fingerprints 均精确匹配
  已发布的 0HT parent certificate；
- 旧全文件共有 743 条 parent-partition mismatch（train/test=`516/227`），全部位于
  `cross_run_declared_context`；direct sibling 与 same-run non-sibling 的 mismatch 都是 0；
- test core 仍是冻结前已知的 318 pairs / 29 tasks / 89 runs / 591 endpoints / 282 components，最大
  task/run/component share=`25/159`、`7/106`、`1/53`，8/8 compatibility gates 通过。因为这些支持数字在本次冻结前
  已知，它们只说明修复后仍保留足够宽度，不是独立确认结果。

这给数据集论文提供了一个正资产：旧 mixed decision 文件虽然不能整体称 sibling benchmark，但可以通过一个确定性、
结构定义、与模型结果无关的 quarantine rule 得到 run-clean historical sibling curated view，同时保留 6,374 条 context
stress rows 的聚合审计轨迹。

## 复验与安全

- protocol/source commit：`f4d09f1203ba72181046ac620862eb10351736cd01a25ac3597b21e4b931b680` /
  `f534114e60658043c07f7a15d6440492caffc8ad`；执行 commit=
  `254fc804c4904635e8f44e9121eab84b425ca6a8`；
- producer A/B 逐字节一致，SHA-256=`4f4902ce365523b01a0cca1eadb716b978aa0771d15286be1bf4aecca6456315`；
- 独立 verifier A/B 逐字节一致，SHA-256=`8b0eb84365aa3cb16bfd3b9a4ca3affabfc4fd24774071a6cbba366b88f57ca0`，
  且 `all_aggregate_fields_equal=true`、不导入本轮 producer；
- parent package manifest 全项复核通过；focused/full tests=`6/1475 passed`，full 有 47 个既有 deprecation warnings；
- forbidden file opens/network calls=`0/0`；remote formal manifest=
  `9a554d8c1ed3dffe5a5aa1ab7ff1579f890fa749fcbb82e545c3a2a7758d2d63`；
- first-960/Target-300 前瞻值、raw senior archives、模型 prediction/accuracy 与 search utility 均未读取或计算；
- row-level release 未创建；GPU/API/model-fit/base-update=`0/0/0/0`。

本证书不把历史 test 称 untouched/prospective，不把 recorded parent 升级为外部语义或因果真值，也不证明 critic scaling、
predictor effect 或端到端 search utility。任何行级 curated release 仍需单独授权、哈希绑定和泄漏审计。
