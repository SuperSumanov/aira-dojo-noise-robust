# Tree linearization 的 depth-order 后验解析声明

日期：2026-08-28

状态：`POST_HOC_DETERMINISTIC_COROLLARY_DECLARED_AFTER_EXPLORATORY_DERIVATION`

## 1. 时间顺序必须写清楚

本声明不是结果前预注册。固定 887 snapshot 的 tree-linearization formal receipt 已经公开了 canonical-edge 与
root-to-leaf path-frequency 两套 depth counts 及 depth TV；随后我又探索性计算并看到了均值、CDF 顺序、交叉数和
分位数，才决定把它做成精确、可复验的确定性推论。

因此后续即使所有检查都通过，也只能称“已发布聚合量的后验确定性解析”，不能称预注册发现、独立确认或新假设检验。
冻结机器声明为 `phase1/tree_linearization_depth_order_corollary_v1.json`。

## 2. 已经看过的数值

- canonical unique-edge depth count=`10,895`，depth sum=`89,213`，mean=`89213/10895`；
- path-frequency depth count=`26,107`，depth sum=`183,993`，mean=`183993/26107`；
- path minus canonical mean depth=`-324480056/284435765`，即约 `-1.140785`；两者均值比约 `0.860683`；
- path CDF 在全部 observed integer depth 上均不低于 canonical CDF，最大 gap 在 depth=5；
- maximum CDF gap 与 depth TV 都是 `27231696/284435765`，约 `0.0957394`；
- 非零 PMF 差只有一次符号交叉；nearest-rank median 从 `7` 变为 `6`，p90 从 `15` 变为 `13`。

这些值已经被看过，不能再据此设计“材料阈值”。机器协议只要求精确重算并诚实分类。

## 3. 可守解释

若独立复算通过，可写：在这个固定、结果盲的 MLE-agent observed forest 上，把树枚举成全部 root-to-leaf paths，
不只是重复 edge；它把 logged edge-depth 的整个经验分布系统性推向浅层。该结论把此前 38.62pp 的 edge-measure
变化解释成一个具体、读者容易理解的方向性后果。

不能写：浅层步骤更重要、更难、因果上支配性能；predictor accuracy 已改变；完整 source tree 已恢复；或该规律已在
first-960 closure 上确认。`lineage.depth` 只是 logged structural position。

## 4. 防撞边界

- Tree Training 已明确讨论把 tree trajectories 拆成线性分支会重复 shared-prefix 计算；
- TreeAdv 已明确用 descendant-trajectory 数量归一化，避免 near-root advantages 因规模支配；
- TreePO、Tree-OPO、Tree-GRPO 等也已覆盖 tree-aware rollout、credit 与 prefix-conditioned learning。

所以这里不主张 shared-prefix、root dominance、tree-aware weighting 或 first-order stochastic dominance 的一般方法首创。
剩余价值是：在真实 Python MLE-agent search corpus 上给出 exact、outcome-blind、physical-run-bound 的经验量级和
可执行发布检查，并与 inverse-multiplicity remedy 一起交付。

## 5. 实现与安全合同

实现只能读取 hash-bound 的既有 aggregate receipt，不得读取 raw snapshot、身份、代码、label/outcome/prediction。
producer 与不 import producer 的 verifier 各跑两次并逐字节一致；所有分布、均值、CDF gap、TV、分位数和交叉均用
整数/Fraction 精确计算。GPU/API/model-fit/base-update=`0/0/0/0`。任何 hash、schema、算术、复现、安全或 manifest
不一致都 fail closed。
