# Component-clean 数据学习曲线 v1：正式裁决

日期：2026-08-23。正式状态：`RETROSPECTIVE_DEV_DATA_SCALING_NO_UNLOCK`。

## 1. 绑定与完整性

- exact scientific commit：`eb1e1f5847584106b8daba30b75ee5459520c6c4`；
- contract SHA-256：`a7c6bca3e430580c4a178d89694e90658a5496b8a1775a967221b7dc32d3c9da`；
- train=`4,689 pairs / 28 tasks / 127 components / 430 runs`；
- dev=`551 pairs / 25 tasks / 41 components / 81 runs`；
- train/dev endpoint、pair、physical-run overlap 均为 0；
- 聚焦测试 8/8；完整 `phase1/tests` 866/866（33 warnings）；
- producer×2、独立 source-refit verifier×2 的输出分别逐字节一致；verifier 最大数值差为 0；
- held-out test pairs、test predictions、prospective vault、score-channel truth 均未打开；GPU/API/base-LLM update=
  `0/0/0`；producer 与 verifier 各 10 个唯一 CPU fits。

## 2. 预注册结果

| train fraction | task-macro accuracy | task-macro log loss |
|---:|---:|---:|
| 0.25 | 0.5724219783380433 | 0.6816094159627339 |
| 0.50 | 0.5298091977807858 | 0.6826620147808903 |
| 0.75 | 0.5652811276147386 | 0.6755762240399482 |
| 1.00 | 0.5643959081886237 | 0.6739468803314009 |

Proper-score 的 full−mean-quarter 点差为 `-0.007662535631333114`，task-bootstrap 95% CI=
`[-0.038109760581376086,0.026746893869806762]`，LOTO 范围=
`[-0.019117321293433378,-0.0023493217535835212]`。三个 selection seed 的 full−quarter contrast 为
`-0.005383092600273587/-0.015283850000521904/-0.002320664293203878`。虽然三 seed 与全部 LOTO 同向，
但 25%→50% 先恶化，CI 跨 0，且点差没有达到预注册 `≤-0.01`；proper-score positive 不成立。

Accuracy 的 full−mean-quarter 点差为 `-0.008026070149419494`，95% CI=
`[-0.07052702433385415,0.05604648899548043]`，LOTO 范围=
`[-0.024564193442682344,0.00552839914991025]`。三个 seed contrast 符号不一致，所有 top-1 正门失败。

## 3. 裁决与主张边界

本结果最多支持“在固定 char-TFIDF/LR、这个 retrospective component-clean dev 上，proper score 有小且同向但
不确定的增加数据迹象”。它不支持稳定 scaling、方法 novelty、frozen/future confirmation、live-search utility，
也不足以单独证明继续增加 runs 会改善 neural critic。accuracy 不能 rescue proper-score；同池不得改 fraction、seed、
task pool、阈值或选择更漂亮的子组。

Reward-model data scaling 已有大量先例；ICML 2026 [*What Does Preference Learning Recover from Pairwise
Comparison Data?*](https://arxiv.org/abs/2602.10286) 还把 comparison-graph connectivity 明确列为 pairwise
preference learning 的 sample-efficiency 因素。因此后续 equal-budget breadth 实验即使通过，也只能作为真实 MLE
代码语料里“跨 run/component 覆盖与组件内密度”的受控 benchmark 证据，不能声称首次发现 connectivity 有效。

## 4. 哈希打包缺陷与修复边界

原 launcher 在内部 manifest 后才将最终四行状态写进 `tee` 的 live `run.log`。因此原 `SHA256SUMS` 的 38 项中，
37 项通过，唯一 mismatch 是 `run.log`：manifest 记录空文件 SHA-256=
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`，最终文件为 163 bytes、SHA-256=
`ea75d87ddc8ef19769e2be48ef77fd4003da0e7c485dd2780fa582f147ccbc70`。独立审计确认四行 suffix 精确、launcher
先 hash 后打印、其余 37 项全过、审计没有改动 formal root。该缺陷属于 completion-log packaging，不影响已封存
科学产物；禁止为了修漂亮 receipt 重跑或覆盖 root。后续 launcher 从内部 manifest 排除 live `run.log`，进程退出后
由外层 bundle 单独哈希。

修正后的两个 launcher 及两个对应测试已在 detached `21186e0` 加四文件 overlay 上复核：聚焦 16/16、完整
`phase1/tests` 874/874（33 warnings），overlay credential filename/content shape hits=`0/0`。这只验证未来
packaging 行为，不回写或改变上述 formal 科学结果。

## 5. 证据索引

审计包：`phase1/results/critic_component_data_learning_curve_20260823_eb1e1f5/`。

- `formal_extract.json` SHA-256：`4d6cc13966babb5b2607cad07a6a5c7ad1821d3e17a2fa13dd5e53eff06552c8`；
- `posthash_runlog_audit.json` SHA-256：`3c90a9ad7aa31dbee5098ba4731dc3b6972c48b5931830b00b0bde7b47d64cad`；
- `original_sha256_verify.txt` SHA-256：`fdda707817b5277f0e24253090807271acd03bca7efbb9b7ee454f8a9d18f9d3`；
- 原始远端 `ORIGINAL_BUNDLE_SHA256SUMS` SHA-256：
  `3a13bc0e8f4fab2fc18e0b1230c9768ec57f5cf3a928adbe49d41d0fd38983bd`。
