# Pair-graph intervention 裁决

日期：2026-08-14。对应 outcome 前协议：`PairGraphIntervention_预注册.md`；运行 commit：
`926db4a3ece3fc24a2714b50e23b76c64b270c5c`；协议：`pairgraph_v11_train_oof_descriptive_v1`。

## 冻结裁决

正式状态为 **`VERIFIED_PAIRGRAPH_EFFECT_NOT_SUPPORTED`**。producer 与不 import producer 的 verifier
分别重建 endpoint registry、枚举跨 run 有限总体、计算三图 transport 和 10,000 次 task bootstrap，逐项一致。
完整性门全过，`frozen_read=false`。

共同支持为 3,921/4,263 sibling rows（0.9197748064743139）、20 tasks；dominant task share
0.22851313440448864。96 个 task×fold cell 中共枚举 196,949 个 finite non-tie 跨 run pairs；31 个 raw-grade
ties 被对称排除。507 个 sibling task×fold×gap strata 中 344 个至少有 5 个跨 run candidates；不支持 strata
及其 342 条 sibling rows 从三图共同排除，未作插补或事后合桶。

## Headline 与失败门

char-TFIDF 的结果方向与“全局对更容易”一致，但跨任务不稳健：

| graph | micro accuracy | task-macro accuracy | mean raw gap | `gap<1e-2` share |
|---|---:|---:|---:|---:|
| real sibling | 0.5212955878602398 | 0.5284907717433142 | 0.18952568987503196 | 0.4047436878347360 |
| cross-run uniform transport | 0.6234760891415420 | 0.5814158858170438 | 0.5072151172099988 | 0.12862978744843032 |
| cross-run gap transport | 0.5488747823033655 | 0.5478674917657668 | 0.18297047756139279 | 0.4047436878347360 |

task-macro 描述分解为：

- total pairing inflation：+0.052925114073729684，task-bootstrap 95% CI
  [-0.04418436017058699, 0.15460114273445769]；
- gap composition component：+0.03354839405127704，CI
  [-0.001990051528197312, 0.07664803900562936]；
- coarse-gap-matched residual：+0.019376720022452644，CI
  [-0.0630247411891304, 0.11343931282674605]；
- gap component 占正 total 点估计的 0.6338842086299702，但其 CI 下界仍未严格大于 0。

headline 点估计达到 +0.05，然而 CI 门失败。四臂只有 2 臂 total 点估计为正，0 臂 CI 下界大于 0，低于
预注册的 3/4 与 2/4 replication 门，故不能声称 pair graph 普遍抬高 critic accuracy，也不能把 63.4%
当成确认的 mediation 比例。

## 更细但仅描述性的 benchmark 发现

pair graph 的作用明显依赖 predictor family：

| arm | sibling task-macro | uniform task-macro | gap-transport task-macro | uniform − sibling [95% task CI] |
|---|---:|---:|---:|---:|
| fixed frozen global | 0.5197131896273652 | 0.5214729047862192 | 0.5038549490441755 | +0.001759715158853903 [-0.08080246028677301, 0.07860838314971694] |
| op-only LR | 0.5000000000000000 | 0.5000000000000000 | 0.5000000000000000 | 0.0000000000000000 [0.0, 0.0] |
| static LR | **0.5389068809808808** | 0.49652226450484627 | 0.4981865211116222 | -0.04238461647603453 [-0.12124609295378166, 0.02773688376758098] |
| char-TFIDF LR | 0.5284907717433142 | **0.5814158858170438** | **0.5478674917657668** | +0.052925114073729684 [-0.04418436017058699, 0.15460114273445769] |

因此模型排序从 sibling 上的 `static_lr > char_tfidf > fixed > op` 变为 uniform 上的
`char_tfidf > fixed > op > static_lr`。这是 outcome 后观察到、未单独设门的描述性 rank reversal，不能升级为
确认性主张；但它比“所有模型统一被抬高”更准确地说明：headline pair accuracy 是
`predictor family × pair graph × task` 的交互量，不能脱离真实搜索决策分布比较。

char-TFIDF 的 total effect 在 20 tasks 中 14 个为正，范围从 spaceship-titanic 的
-0.34208906120146093 到 tweet-sentiment-extraction 的 +0.6726190476190477。这种异质性正是 task bootstrap
宽、微平均比 task-macro 更乐观的原因；禁止按正任务筛子集。

## 完整性、资源与归档

- 四个输入 SHA、OOF/pair 逐行映射、333 runs / 23 tasks / 2,293 parents / 5,499 endpoints、grade
  orientation/gap、endpoint score consistency、同 task/fold 且不同 run、finite 与 coverage 门全部通过；
- cards 单遍 allowlist loader 只保留 5,499 selected IDs 的 task/graded；code/obs/非 allowlist 保留数均为 0；
- producer runtime 5.02447647601366 秒；producer/verifier rc=0；0 GPU、0 API、0 底座更新；
- candidate population SHA-256：`b3db59bed974d0a7691ab21cfc5454efc2609e142799b36623a1d8fca1f179d5`；
- producer summary SHA-256：`56b84e51430ad706ef00c5a048e5d6aa6effbdf037f05c078fe5a5c960b30607`；
- stratum/per-task SHA-256：`1fd3667d19a703a63686b9f54eb2256251e82b85b4e9c6a091077dec59e8c266` /
  `13c394bbca697a2b07c04c0b2a6cd31051d535931f6378ecf3fe161cb28f245c`；
- artifact manifest 18/18 通过，高置信密钥文件与可疑文件名均为 0；完整包 SHA-256
  `5d75dc403cbe866b749e798947147b03cf248d003119da101a10fbfc2ffc675e`，60,636 bytes。

## 路线影响

关闭“全局 pairing 对所有 predictor 产生统一 inflation”的强版本，也不在同一数据上改 replication 门。
保留更可守的 benchmark 结论：真实 sibling 与全局跨 run pairing 不仅 gap 分布不同，还可能改变 predictor
family 的相对排序；因此发布物必须把 pair graph、task weighting、gap transport 和真实 decision utility
一起报告。下一次确认只允许使用本协议冻结之后的新 physical runs 和事先冻结的 scorer，不打开论文 frozen。
