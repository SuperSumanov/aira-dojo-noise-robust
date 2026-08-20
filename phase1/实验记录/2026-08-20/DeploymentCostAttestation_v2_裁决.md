# DeploymentCostAttestation v2：正式裁决

日期：2026-08-20。结果前协议见 `DeploymentCostAttestation_v2_在线单对预注册.md`。正式 source commit 为
`c800345d281b4a15edb90b6c1593ee1b14337327`；clean worktree 预检通过定向 `9/9` 与 phase1 全套
`448/448`。正式 A/B 在同一主机、同一单核 affinity 和固定线程契约下顺序独立运行，51 分 31 秒内完成，未触发
2 小时 hard wall。

## 裁决

- A producer：`DEPLOYMENT_COST_ADVANTAGE_SUPPORTED`，独立 verifier 通过；
- B producer：`DEPLOYMENT_COST_ADVANTAGE_SUPPORTED`，独立 verifier 通过；
- cross-run comparator：`CROSS_RUN_STABILITY_VERIFIED`；
- 总计 18 fits、4,608 online queries；两 run 各 2,313 measurement rows，其中 9 行为 fit/init；
- execution reference 为 frozen b0 的 1,498 对，coverage=`1.0`，ideal-parallel p50=
  `199.62654004304204` 秒。

三个模型的 A/B online query p50 分别稳定在：static-LR `40.909126/41.00444` ms、static-GBM
`49.3092785/49.0379345` ms、TF-IDF-LR `33.925568/33.0667115` ms。相对 ideal-parallel execution p50，
p50 比值范围为 `4048.4579396764457` 到 `6037.084759488165`；最坏 query p95 占 execution p50
`0.05797248618597878%`，通过固定的 1% 门。init p50 范围为 `98.586651793` 到 `155.037595478` 秒，
三模型 A/B 的 break-even 均为 1 pair，并通过≤10×execution p50 门。

所有 trial 的 fit warning=0、tie=0、antisymmetry=`1.0`；同模型 trial 内和 A/B 间 decision digest 均一致。
A/B query-p50 最大 cross-run ratio=`1.025973447646888`，init-p50 最大 ratio=`1.0901214467517888`。

## 解释边界

这是当前 D&B 资产缺口中一项可引用的正成本结论，正式替代旧的缓存式单次延迟和错误“七百万倍”算术。它没有
计算 frozen accuracy、没有读取 prospective outcome/vault、没有 GPU/API 消耗，不能与旧 accuracy 事后拼成
accuracy-adjusted speedup；也不能单独证明搜索质量、wall-clock 收益或方法 novelty。可写法应是“查询在真实
在线路径上相对候选执行便宜约四千至六千倍，且 A/B 重复稳定”，同时另表报告 predictor accuracy 与覆盖。

完整产物：`phase1/results/deployment_cost_attestation_v2_20260820_c800345/`。
