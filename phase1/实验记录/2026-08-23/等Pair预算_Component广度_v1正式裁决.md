# 等 pair 预算的 component/run 广度 v1：正式裁决

日期：2026-08-23。正式状态：`RETROSPECTIVE_DEV_COMPONENT_BREADTH_NO_UNLOCK`。

## 1. 绑定与完整性

- exact scientific commit：`21186e036b41b35c087fd3cb02e99a88b241a4ed`；
- contract SHA-256：`1dc28d105922741d0c6a8263d9b2ebd2566d1a28de3dec1eb8f490116f7e6316`；
- 每臂每 seed 恰为 2,353 train pairs；broad=`127 components / 429 runs`，concentrated=
  `53 components / 223--224 runs`，random=`123--125 components / 425--426 runs`；
- dev=`551 pairs / 25 tasks / 41 components / 81 runs`，train/dev endpoint、pair、physical-run overlap 均为 0；
- 聚焦测试 8/8；完整 `phase1/tests` 874/874（33 warnings）；
- producer×2 与不 import producer 的 source-refit verifier×2 分别逐字节一致，最大数值差为 0；
- held-out test pairs、test predictions、prospective vault、score-channel truth 均未打开；pair orientation 未用于选择；
  GPU/API/base-LLM update=`0/0/0`，每个实现 9 个唯一 CPU fits。

## 2. 预注册结果

| arm | task-macro accuracy | task-macro log loss |
|---|---:|---:|
| broad | 0.5624400862785816 | 0.6773594555405009 |
| concentrated | 0.5292196471271629 | 0.6841291831000907 |
| random | 0.5527886403630491 | 0.6765865607703202 |

Broad−concentrated accuracy 点差=`+0.0332204391514186`，task-bootstrap 95% CI=
`[-0.010859355050261277,0.07987928182598769]`，LOTO 范围=
`[0.02245184633828326,0.041914565636528865]`。三 selection seed 的点差为
`+0.022169066955282535/+0.015669956068959934/+0.0618222944300133`。因此三 seed、点效应下限和 LOTO
均通过，唯一失败项是 CI 下界未高于 0；按冻结 conjunction，top-1 positive 必须判 false。

Broad−concentrated log-loss 点差=`-0.006769727559589795`，95% CI=
`[-0.025437665186368662,0.010856041904946215]`，LOTO 范围=
`[-0.010812454124275566,-0.0012116110917376282]`。三 seed 点差为
`-0.00036404630189446063/+0.000752789631084716/-0.020697926007959833`；seed 一致性、`-0.01` 下限和 CI
均失败，proper-score positive 为 false。

Random 是事前固定的 descriptive arm，不能 rescue。它相对 concentrated 的 accuracy/log-loss 为
`+0.0235689932358862/-0.007542622329770654`；broad 相对 random 为
`+0.00965144591553239/+0.000772894770180795`。换言之，broad 的 top-1 点估计最高，但 random 的 proper score
略好；数据更像“不要把预算过度集中在少数组件”而不是“最大化 breadth 独特最优”。

## 3. 裁决与后续边界

两个 headline gate 均失败，故不能称正结果突破、data-curation 方法成立或 component breadth 有因果收益。accuracy
的四个子门过三个，是值得保留的候选机制；但同池追加 selection seeds、改 bootstrap、只报 LOTO、移除某 task 或把
random 降格后重命名结论，都会是结果后追救，禁止执行。

合法下一步只有在未见结果的新独立 corpus/future cohort 上，事前冻结同一 broad/concentrated/random 选择器和主门。
若复现，论文价值仍是 MLE search-tree 数据采集的实证建议；ICML 2026
[*What Does Preference Learning Recover from Pairwise Comparison Data?*](https://arxiv.org/abs/2602.10286) 已直接讨论
comparison-graph connectivity，故不得声称首次发现 connectivity 影响 preference learning。

## 4. 打包审计

原 exact launcher 在内部 `SHA256SUMS` 后才写 live `run.log` 的四行 completion suffix。40 项中 39 项通过，唯一
mismatch 是 `run.log`：manifest 记录空文件 SHA-256=
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`，最终 170 bytes、SHA-256=
`89039f0e0d4328e2daf5cb157cc715ed5f4374df6b5a3d9a97b8ac3b24281b8c`。独立审计确认 suffix 精确、launcher
先 hash 后打印、root 未改写。该 packaging 缺陷不改变科学裁决；后续修正已由共享 overlay 16/16 聚焦与 874/874
全测试验证，不覆盖或重跑本 formal root。

## 5. 证据索引

审计包：`phase1/results/critic_component_breadth_equal_budget_20260823_21186e0/`。

- `formal_extract.json` SHA-256：`ad2b4c85fa35eaaeaa8289cb0130151a51d719014fcdf5ec17b0e7b106c79ab5`；
- `posthash_runlog_audit.json` SHA-256：`de985033d806ed39152d7841eea2524ba6c02076964e54d34b4ce64af0ecddf2`；
- `original_sha256_verify.txt` SHA-256：`3c23203348e7ef3df50d947d62ce23c957c036d55f860ab68ea5f0cdf422e362`；
- 原始远端 `ORIGINAL_BUNDLE_SHA256SUMS` SHA-256：
  `af142d7c7059d4c3960cc5286da1275342ac0f731e91b6aec934f4510dec4913`。
