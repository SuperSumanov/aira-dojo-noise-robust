# Tree-structure audits：正式结果与正方向裁决

日期：2026-08-28

固定 outcome-blind snapshot：`887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697`

当前 first-960：435/960，closure=false，outcomes_read=false

## 一、执行摘要

本轮把 tree linearization 的三个问题分别做成 hash-bound producer、非 import 独立 verifier、A/B 重跑、完整测试和
访问审计。正式结果不是“三个都赢”：

1. **path split prefix risk：部分正结论。** 风险在 physical-run 维度广泛且不过度集中；task 维度虽覆盖广，
   最大贡献占比超过结果前上限，正式分类为 `RUN_ONLY_BROAD_PATH_SPLIT_PREFIX_LEAKAGE_RISK`。
2. **depth order：精确正结论，但属于后验解析。** path enumeration 对固定 observed forest 的 logged-depth
   分布形成严格 shallow FOSD；不能包装成预注册发现。
3. **within-stratum：正式失败。** 科学 breadth/anti-dominance profiles 全过，但一个 float-string round-trip
   完整性门失败；同一 snapshot 不得事后修门救回。其 profile 只能指导首个未见未来 snapshot 的 exact-rational 确认。

综合起来，最可守的正方向已更清楚：论文不应把 path records 当天然 i.i.d. benchmark rows，而应发布
canonical tree-native view、path-compatible inverse-multiplicity view、physical-run grouped split 和显式 estimand
firewall。我们现在有材料性、精确偏移、浅层偏置及跨 split shared-prefix risk 的一条一致证据链。

## 二、正式结果

### 2.1 Path-record split 的 shared-prefix crossing

- population：3,599 paths、10,895 canonical observed edges、26,107 path-edge occurrences。
- fixed-size 80/10/10 path split：2,879/360/360。
- expected train-test shared canonical edges：`1291.4019805907681`。
- expected unique-test edge contamination ratio：`0.63841797380705656`。
- expected test-occurrence contamination ratio：`0.71072159960645032`。
- physical run：339/435 达到 ratio reference 0.25；最大贡献 share=`0.14093310549689442`，通过 0.20 门。
- task：31/34 达到 reference；最大贡献 share=`0.45161151698862051`，未通过 0.40 门。
- fragment/run grouped split control：exact canonical-edge crossing=`0/1`。

正式分类没有使用 global ratio 的已知高值救门，也没有因 task 覆盖 31/34 就忽略 dominance failure。

### 2.2 Path enumeration 的 shallow-depth stochastic order

- canonical mean depth：`89213/10895=8.1884350619550261`。
- path-frequency mean depth：`183993/26107=7.0476500555406592`。
- mean shift：`-324480056/284435765=-1.1407850064143656`。
- path/canonical mean ratio：`0.86068339093086754`。
- shallow FOSD 在全部 37 个 observed depth levels 成立；非零 PMF 差恰交叉一次。
- max CDF gap=depth TV=`27231696/284435765=0.095739352609191045`，位于 depth 5。
- nearest-rank median/p90：`7/15 → 6/13`。

这些都是已见 aggregate 的 deterministic corollary；贡献是把偏置做成精确、可执行的 release audit，不是发现
shared-prefix 或 root bias 的一般理论。

### 2.3 Within-stratum decomposition 的失败与未来确认信号

正式 gate failure 是字符串表示不一致：上游保存 `0.1603376038171571`，exact rational 在 `.17g` 下为
`0.16033760381715709`。两个数代表同一 JSON double，但预注册协议要求 exact textual round-trip，故必须失败。

新 profile 只作描述性读数：

- task `W_p=0.34286096272939481`，32/34 groups 达 reference，最大贡献 share=`0.35387441357728333`；
- run `W_p=0.30840042995574296`，356/434 groups 达 reference，最大贡献 share=`0.10868797144906397`。

下一次确认协议应把所有已知 marginal 绑定为 numerator/denominator，并在首个未见稳定 snapshot 到来前公开；
不能重新运行 887 后把它升级为正式正结果。

## 三、与已有工作的边界

本轮检索没有发现直接量化 **MLE-agent observed forest 中 root-to-leaf path random split 的 expected exact
canonical-edge crossing，并同时给出匿名 task/run breadth 与可执行 release contract** 的工作。但下列一般思想已有
明确先例，不能申首创：

- [Tree Training](https://arxiv.org/abs/2511.00413)：shared-prefix trajectories 与重复线性片段计算；
- [Reward Generalization in RLHF: A Topological Perspective](https://aclanthology.org/2025.findings-acl.820.pdf)：
  root-to-leaf responses 共享 prefix，形成依赖的 tree-based data；
- [Contrastive Branch Policy Optimization](https://arxiv.org/abs/2608.24300)：exact-prefix grouping 与避免重复梯度；
- [TreeCredit](https://arxiv.org/abs/2608.02291)：分支级 credit；
- `mle-traj-v1` 已把少量 MLEvolve runs 线性化为 root-to-leaf branches。

因此不得声称“paths 不独立”“shared prefix”“group split”或 `1/m_e` 本身有算法 novelty。可守贡献是：

1. MLE-agent 搜索森林上的精确量化与严格 provenance；
2. canonical/path 双视图及 estimand firewall；
3. physical-run grouped split 的可执行发布规范；
4. outcome-blind、失败也保留的 audit protocol；
5. closure 后再验证这些结构选择是否改变 predictor ranking/utility，而不是提前窥视冻结结果。

## 四、当前正方向与下一步

### 可以进入论文主叙事

- tree-native benchmark representation 不是格式偏好：path-frequency view 对 canonical edge measure 的 TV 已达
  `0.38618771447395162`，且重复质量、task/run weight、depth 和 split contamination 均有一致材料性证据。
- 发布时应同时提供 canonical edge view 与兼容 path view；path consumer 必须使用 inverse multiplicity，split 必须按
  physical run（至少 fragment）分组。
- 这条线增强的是 dataset/benchmark 与 audit contribution，不依赖当前 critic 是否超过 0.55。

### 仍需未来数据确认

- 首个未见 snapshot 上确认 within-stratum breadth，采用 exact rational binding。
- first-960 + accrual closure 后，才允许按冻结协议打开 label/outcome 并做 predictor/effect/search utility。
- task-dominance 的 path-split 结果应在未来 snapshot 复验；当前不得通过调高 0.40 门补成双轴 broad。

### 明确不做

- 不恢复旧 HCE、多保真、Probe、score-channel effect 或 K≥1 lookahead；
- 不从结构风险外推真实 accuracy inflation；
- 不为追求正结论修改同 snapshot 门；
- 不在未批准前启动 GPU、付费 API 或模型训练。

## 五、复验与安全

三个 formal 的 focused/full 分别为 `49/1355`、`63/1369`、`90/1391 passed`，全套均有 47 warnings；
每条 producer A/B、verifier A/B 均逐字节一致，三个 manifests 在传输后全部通过。forbidden-open 与 credential
filename/content 均为 0；未读取 prospective label/grade/outcome/prediction 或 raw senior archives；
GPU/API/model-fit/base-update=`0/0/0/0`。

正式包：

- `phase1/results/tree_linearization_within_stratum_887_20260828_2363b68/`
- `phase1/results/tree_linearization_depth_order_887_20260828_333a3b6/`
- `phase1/results/tree_path_split_prefix_leakage_887_20260828_aec6356/`
