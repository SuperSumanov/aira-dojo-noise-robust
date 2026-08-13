# Target-Graph Connected Augmentation：正式裁决

日期：2026-08-14。协议：`tgca_v11_train_oof_discovery_v1`。正式代码 commit：
`2de878d60175f72ea41c31966206ab73245561f7`。

## 冻结裁决

producer 给出 **`TGCA_DISCOVERY_NO_UNLOCK`**，不导入 producer 的 verifier 从锁定输入重新枚举训练边、
重新拟合全部 20 个模型并逐 endpoint 比较分数，给出
**`VERIFIED_TGCA_DISCOVERY_NO_UNLOCK`**；最大重拟合 score 绝对差为 `0.0`。因此 TGCA 在本实现上关闭：
不改 ratio、gap bins、连接顺序、任务、seed、正则或通过门，不读取 0812 temporal label vault，也不把轻微的
微平均正点估计写成方法成功。

## 同池 OOF 结果

评测池固定为 4,263 个真实 sibling pairs、333 个 physical-run groups、23 tasks、2,293 parents、
2,259 complete parents 与 5,499 endpoints；五折按 physical run 隔离。

| arm | pair accuracy | complete-parent top-1 | parent-equal gap utility |
|---|---:|---:|---:|
| sibling only | 0.5219329110954727 | 0.4674634794156706 | 0.5310468507329235 |
| sibling reweight control | 0.5207600281491908 | 0.4665781319167773 | 0.5293520956830511 |
| uniform cross-run control | **0.5369458128078818** | **0.4794156706507304** | **0.5477536412901698** |
| TGCA | 0.5357729298615999 | 0.4718902169101372 | 0.5413575333235168 |

TGCA 相对 sibling-only 的 pair/top-1/utility 微平均增量分别为 `+0.01384001876612714`、
`+0.004426737494466578`、`+0.010310682590593189`。其中 utility 的 run-equal 估计为
`-0.002212900691262035`，95% CI `[-0.03841459412934916, 0.032223781746577584]`；task-equal 估计为
`-0.011302804940027606`，95% CI `[-0.04162144688735887, 0.020252900410588966]`。top-1 的 run/task
区间分别为 `[-0.03948280448801103, 0.0414619177520729]` 与
`[-0.0463816506658282, 0.012774683950622192]`。

相对等边数 sibling reweight，TGCA utility 微平均增量为 `+0.012005437640465622`；run/task 区间分别为
`[-0.031797080407755515, 0.03917436386732047]` 与
`[-0.02872550797464327, 0.02917496489302283]`。相对 uniform cross-run，TGCA utility 微平均反而为
`-0.00639610796665303`，但双聚类区间同样跨零。这里的微平均、run-equal 和 task-equal 是不同 estimand；
不能用微平均的小幅正值覆盖聚类估计的异质性。

## 操纵检查与失败门

图连接操纵确实生效。114 个 fold×task 图中，四臂在各自训练折合计加入的 augmentation rows 均按契约匹配：
TGCA 与两个增广控制各为 16,910。按 fold×task 等权：

| arm | mean components | mean largest-component share | 正代数连通度图数 | mean normalized connectivity |
|---|---:|---:|---:|---:|
| sibling / reweight | 80.45614035087719 | 0.04532943482666053 | 0/114 | 0.0 |
| uniform cross-run | 7.5 | 0.8688021307871628 | 25/114 | 0.01797145771702864 |
| TGCA | **5.780701754385965** | **0.9341349806051460** | **101/114** | **0.020443497412724106** |

所以本次失败不是“选边器没有连图”。它表明，在固定 char-TFIDF 表示、线性头、等边数和粗粒度 gap/task
控制下，更强的 comparison-graph connectivity 没有转化成可重复的真实 sibling 决策收益；这不外推为所有
表示或所有图方法都无效。

预注册门中，支持任务数 `20` 与 dominant-task share `0.211118930330753` 通过；完整性门全部通过。
但三个主要效果门全部失败，而且支持任务中 utility delta 非负仅 `11/20=0.55`，低于固定的 `0.60`。

## 完整性、资源与失败记录

- fit/valid physical run、endpoint 与 raw-code SHA 三层交集均为 0；五折、控制数量、OOF coverage、收敛与
  finite 门全部通过；`frozen_read=false`、`temporal_vault_read=false`；
- producer 用时 `1030.945998994168` 秒；0 GPU、0 API、0 base-LLM updates；
- summary SHA-256：`fefa9ce86554f0e3bcca9cff03427cbf77611b73654ecc4e3a682dbfd0187c83`；
- independent verifier SHA-256：`96c4293e1fa19613a36ab1c4b6aca5ce554c8c35076d69a6cdf453225341c010`；
- 完整远端包：`/research/d7/spc/yzyang4/archives/tgca_v11_20260814_2de878d60175_full.tar.gz`，
  6,151,411 bytes，SHA-256
  `6652812fc110f19a87b0e8bdf99b6b9d41079d555110142e139d48142e83f175`；
- 第一次 launcher 在 commit `096e875` 的预检第 1 项因 critic venv 没有 `pip` 而退出；它没有开始边枚举、
  拟合或 metric 计算。失败 log SHA-256 为
  `63e16e60307eff8699a182197f32464fac97383303b9872e71a43127c9995c1e`，已一并保留。

## 路线裁决

1. TGCA 不进入 0812 盲测或 prospective scorer；在同一 OOF 不做第二种连接启发式。
2. 主线回到 run-clean、decision-local 的 MLE-agent 数据集/benchmark，以及已经激活的 first-960
   prospective confirmation。
3. gap/parent-normalized loss 属于成熟 learning-to-rank/LambdaRank 类思路；若以后在新数据上补，只能作为
   utility-aligned 强基线，不作为论文方法 novelty，也不能在当前 OOF 上追门。
4. 本结果可作为机制消融：图连接被大幅改变但真实 sibling utility 未被可靠改善；论文主张仍以真实
   sibling graph、physical-run provenance、estimand transport、成本/噪声核算与前瞻复核为核心。
