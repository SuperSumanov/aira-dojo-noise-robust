# Archive Granularity Retention Audit v1：正式结果

## 裁决

结果前冻结的强门正式通过：`ARCHIVE_GRANULARITY_RETENTION_STRONG`。这把此前“结构拒绝不等于任务拒绝”的
定性结论，推进成了有明确数量级的正面 corpus-utility 结论。

在 6 个存在 structural-rejected archive 的 competition 中，6 个都仍有 eligible accepted support。若采用
task-level blacklist，而不是 archive-granular validation，会额外丢弃：

- 20 个 accepted archives；
- 94 个 physical runs；
- 92 个 eligible runs，占当前 494 个 accepted eligible runs 的 `18.6234817814%`；
- 2,558 个 eligible endpoints，占当前 13,098 个 accepted eligible endpoints 的 `19.5296991907%`。

结果没有被单一任务支配：最大 affected task 占 retained eligible runs 的 `31.5217391304%`，占 retained
eligible endpoints 的 `36.9038311181%`，均低于结果前冻结的 70% 强门。6 个 affected tasks 的 eligible-run
分布匿名 min/median/max=`4/17/29`，endpoint 分布=`50/458.5/944`。

## 严格性

- exact scientific commit：`bc88298cb410183cf642c132c5d1df2e2d9497ba`
- frozen LATEST：`30945550b6b12a146dadd6eda733c3b676b467aef86636ae31ac59813133104f`
- frozen observations：`dccd59d9e3fe964aabce2458647013d772070c40a120f79f9a6b02605356e855`
- producer A/B 与不导入 producer 的独立 verifier A/B 均逐字节一致；
- focused/full tests=`10/1860 passed`，full suite `48 warnings`；
- 独立 postflight PASS；network/forbidden-path/credential/identity hits=`0/0/0/0`；
- result/verification/manifest SHA-256：
  `f28ef794...9a2184` / `4965c047...d3b187` / `5a5f5168...957823`。

## 可写入论文的主张边界

允许主张：在当前冻结语料中，把结构验证做到 archive 粒度，而不是因某个 archive 无效就 blacklist 整个 task，
可保留约五分之一的有效 accepted run/endpoint 支持；这个收益横跨全部 6 个 affected tasks，且不由单一任务主导。
这直接支持 benchmark intake/audit protocol 的设计价值。

必须同时说明：这是全量冻结语料上的确定性 counterfactual accounting，不是线上方法效果或因果估计；没有读取或
输出 affected task/archive/run/candidate identity，也没有读取 archive payload、label、outcome、prediction value、
accuracy、utility。它不支持 predictor accuracy、模型 scaling、search utility、task whitelist/blacklist 或未来语料
stationarity。GPU/API/model fit/base update=`0/0/0/0`。

机器件位于 `phase1/results/archive_granularity_retention_v1_20260831_bc88298/`。
