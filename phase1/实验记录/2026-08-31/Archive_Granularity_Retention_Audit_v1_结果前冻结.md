# Archive Granularity Retention Audit v1：结果前冻结

时间：2026-08-31。该协议在读取受影响 competition 的 retained accepted archive/run/endpoint 数量及 task dominance
之前冻结。此前 taxonomy-aware 审计已公开 aggregate：结构拒绝 competition=`6`、其中 mixed=`6`；没有读取或输出这些
competition 的身份，也没有得到本协议的任何 retention 数值。

## Goal

量化一个可审计的 benchmark-design 问题：若错误地把“某个 archive 结构无效”上升为“整项 task 黑名单”，当前 corpus
中会丢掉多少本来已经通过结构门的 accepted support？参考策略是 archive-granular validation，只丢结构无效 archive；
反事实策略是丢掉所有 affected competition 的 accepted archives。

这不是线上随机对照或方法效果。它是当前冻结 corpus 的确定性 counterfactual accounting，作用是把 6/6 的定性结论转成
可解释的 corpus utility 数量级。

## Context 与固定输入

- snapshot=`30945550b6b12a146dadd6eda733c3b676b467aef86636ae31ac59813133104f`；
- frozen observations=`dccd59d9e3fe964aabce2458647013d772070c40a120f79f9a6b02605356e855`；
- accepted archives/tasks/physical runs/eligible runs/eligible endpoints=`126/34/520/494/13098`；
- structural rejected archives/competitions=`13/6`；alias quarantines=`8`，明确不进入 estimand；
- prior result/verification SHA-256=`58539382...c104e` / `854f81e5...21ab4f`。

accepted task 与 run/endpoints 只来自 snapshot transaction hash 绑定的 intake summary 与 `source_provenance.json`；每个
accepted archive 必须恰好一个 task，run ID 只用于内部去重，任何 identity 都不得输出。

## 冻结 estimand 与通过门

主指标：

1. affected competitions 下 retained eligible runs / 全部 accepted eligible runs；
2. affected competitions 下 retained eligible endpoints / 全部 accepted eligible endpoints。

同时报告 retained accepted archives、physical runs，以及匿名 task-level min/median/max。dominance 定义为 affected support
内部单个 task 的最大份额。

强支持须全部满足：

- 6 个 affected competitions 全部至少有 1 个 eligible run；
- retained eligible-run share≥10%；
- retained eligible-endpoint share≥10%；
- run 与 endpoint 的 dominant-task share 均≤70%。

部分支持：至少 4 个 affected competitions 有 eligible support、两项 retained share 均≥5%、两项 dominance 均≤85%。
其余为 kill。阈值在 retention 数值读取前固定，不根据结果调整。

## 13 项 pre-flight

1. **问题**：archive-granular validation 相对 task blacklist 保留多少有效结构支持？PASS。
2. **estimand**：全量冻结 corpus 的 exact accepted runs/endpoints accounting。PASS。
3. **输入**：exact snapshot、frozen observer、hash-bound transactions/intake provenance、prior verified taxonomy。PASS。
4. **泄漏**：不读 archive payload、label/outcome/prediction/accuracy/utility/candidate profile。PASS。
5. **对照**：task-level blacklist 为明示反事实；alias quarantine 排除，不能虚增 retained support。PASS。
6. **样本量**：穷举 126 accepted archives、520 provenance rows，不抽样、不提前停止。PASS。
7. **随机性**：无随机性。PASS。
8. **推断**：当前 corpus 全量 census，只报 exact counts/shares，不伪装成总体显著性。PASS。
9. **成本**：CPU metadata-only，预计小于 5 分钟；GPU/API/model-fit/base-update=`0/0/0/0`。PASS。
10. **恢复**：fresh write-new formal roots；失败件不复用。PASS。
11. **环境**：exact commit、固定 Python、单线程、focused/full tests。PASS。
12. **安全**：producer/verifier trace、network/credential/identity gates；身份只在 private trace 中且不公开。PASS。
13. **晋升**：producer A/B、独立 verifier A/B、hash/read-only/postflight 全过才发布。PASS。

## 解释边界

若强门通过，允许写：在当前 corpus 中，按 task 扩大结构拒收会丢弃至少 10% 的有效 runs 与 endpoints；archive-level
validation 避免了这种可量化的数据覆盖损失，且结果不由单个 task 主导。

禁止写：archive-level gate 提升了 critic accuracy/search utility、拒收机制有因果性能收益、任何 task 应永久保留/删除，
或这些比例会稳定外推到未来 corpus。
