# Decision Corpus Evidence Index v9：正式裁决

日期：2026-08-29。裁决：`FORMAL_LINEAGE_REPAIRED_EVIDENCE_INDEX_V9_COMPLETE`。

## 结果

v9 在 source v8 exact index SHA-256=
`e97eca05d99a2eb3b5429539469a7e790f20f40cf70670cdbdc6a2c0c3e730a3` 上只替换 `decision_corpus` 一项，其余
15 项逐对象相等，status 保持
`PROVISIONAL_TEMPORAL_SPLIT_CERTIFIED_EVIDENCE_STACK_AWAITING_FIRST960`。

replacement entry 绑定 lineage v2 package manifest=
`4c72c32449a4a68377fe3764089321c852648e0d6603655a09cd360a21d45447`，包含 3 artifacts / 51 exact JSON
assertions。它要求同时保留：8,107/8,107 lineage-direct rows、7,579 parent-present core、528 orphan tier、15/15 hard
gates、35/36 support gates，以及唯一失败 `frozen:b2.maximum_single_run_pair_share`。任何试图隐藏该失败门、改动其它
entry 或升级 provisional status 的 candidate 都被独立 verifier 拒绝。

权威 source commit=`f10881237447501a1b3b51213a267865bd854d17`。builder A/B 与 verifier A/B 分别逐字节一致；
index/verifier SHA-256=`b2d88479abb03cf72b27f9f958badfb3aeb8bc1e1e3cac2c50a3aace43511ff6` /
`2319c028b3cb28bef01db9b343a307a9327f3414c3e15e5595bd500af6985e6d`。focused=`37 passed`；full=
`1496 passed, 47 warnings`。单线程 CPU 限制、forbidden open、network、credential filename/content gates 全部通过。

## 工程失败链

- r1：远端仓库没有本地名 `myfork`，在 checkout/test 前 rc=128，无 index。
- r2：既有 full-suite 数值测试触发约 27 核 BLAS；主动停止并写资源守护 rc=143，无 index。
- r3：科学测试完成，但集群没有 `rg`，旧 `|| true` 吞掉 rc=127；空 hit file 不构成扫描通过，整轮已机器作废。
- r4：固定 `fork` remote、单线程 BLAS、scanner presence 与返回码门后完成；这是唯一权威 formal。

formal manifest=`2cc3b1b9fc7a12cb884913fddfa3448dc6ebc7d22be86bc4c69374f86bae854a`；独立 postflight
manifest=`fb3cb40cc0a80f42ad113cfb0fbf17d68714d0136113113e85387baffd192b58`。

## 科学边界

这是已知 0HY lineage 结果后的证据引用修复，不是新结果前实验；它把“结论真实但旧 artifact 证据不足”变成可执行、
fail-closed 的 provenance closure。不得申一般 benchmark-card/evidence-index/lineage novelty，不把 recorded parent 升级为
语义或因果真值，不称 b2 全门通过，也不推导 predictor accuracy/scaling/search utility。没有 row-level release；
prospective values/raw senior archives 未读，GPU/API/model-fit/base-update=`0/0/0/0`。
