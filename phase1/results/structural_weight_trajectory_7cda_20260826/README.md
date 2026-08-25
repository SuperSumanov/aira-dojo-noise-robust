# First-960 结构权重时序与机会产率分解

日期：2026-08-26

状态：`FORMAL_STRUCTURAL_WEIGHT_TRAJECTORY_PASS`

固定 snapshot：`7cdaefcf2be7786442e1af1f4d0b4012edee708932f1fad31e174c0dcaf803a1`

正式源码 commit：`57561d8114e3e284c658e2733e1749cdfc1a4cd3`

## 结论

在 first-240→first-339 的 outcome-blind 时间序轨迹中，physical-run 层的任务集中度下降，pair 层的任务集中度却上升：

- run-HHI 变化：`-0.007095167549882084`；
- pair-HHI：`0.08303759912408124 → 0.1357471491993994`，变化
  `+0.05270955007531816`；
- run→pair task-distribution TV：`0.2750745424635 → 0.337082500713674`，变化
  `+0.06200795825017402`。

固定 Shapley 两路径分解表明，task-specific decision-opportunity yield 的变化解释了 pair-HHI 正向增量的
`0.6446576519060645`，也解释了 run→pair TV 增量的 `0.5951060527094302`。因此，真实搜索树每个任务产生多少可比较
sibling decision，不是无关的工程细节，而会内生重写 pair-micro benchmark 的任务混合。

最强严谨表述是：**该反转的符号可泛化，但幅度对单个高产率批次敏感；opportunity-yield heterogeneity 是主要机制。**

这是一项 Decision Corpus / benchmark-design 正结果，不是 predictor accuracy、模型优越性或 search utility 结果。

## 结果前固定的四个门

| 门 | 结果 | 观测值 | 允许解释 |
|---|---|---:|---|
| G1 时序持续性 | PASS | 260/280/300/320/339 共 `5/5` 个检查点保留反转 | 可称持续反转 |
| G2 无单批次 artifact | **FAIL** | 最大单 drop attribution=`0.9641733656841007` | 禁止称幅度不受单批次影响 |
| G3 单任务稳健性 | PASS | `30/30` 个 leave-one-task-out 保留反转；删除 OSIC 后也保留 | 反转符号不是只由一个任务决定 |
| G4 yield 为主要机制 | PASS | pair-HHI=`0.6446576519060645`；TV=`0.5951060527094302` | 可称 yield heterogeneity 为主因 |

G2 的失败批次是
`0820-osic-pulmonary-fibrosis-progression-8seeds-4c1127356fce21d7`。删除该批次的 5 个新增 runs 后，
pair-HHI 增量从 `0.05270955007531816` 降至 `0.001888405775504004`，但仍为正；run-HHI 增量仍为
`-0.007279189126736543`。删除整个 OSIC task 后，pair-HHI/run-HHI 增量仍分别为
`+0.0026450815411386136` / `-0.008064315542060704`。所以可以保留“方向性反转”，不能保留“幅度广泛稳定”。

## 机制与论文意义

当前 339 runs、10,196 endpoints、2,593 decision parents、2,635 canonical sibling pairs 覆盖 30 tasks。OSIC 只有
21 runs，却产生 823 pairs，平均 `39.19047619047619` pairs/run，其 pair share 相对 run share 放大
`5.041962591488208` 倍。这说明按 physical run 均衡采集并不能自动保证按 decision pair 均衡评测。

对论文最直接的贡献是：

1. 发布 run→endpoint→decision-parent→pair 的层级权重与时间序轨迹；
2. 把每任务 opportunity yield 作为 benchmark provenance 的一等字段；
3. headline 使用已在 outcome 前冻结的 task-macro/parent-macro estimand，并强制并列 pair-micro 敏感性；
4. 报告 drop-level leverage，避免一个小批次悄然主导总体 accuracy。

有限的定向检索未发现与“MLE-agent 搜索树中 decision-opportunity yield 随时间内生重写 pair benchmark task mixture”高度重合的
工作。最接近的相邻工作是 PALOMA 对静态 domain composition 与 macro/micro 汇总的处理、MixEval-X 对现实任务混合的重构、
Agentic Benchmark Checklist 对 agent benchmark 有效性的审计，以及 NAS predictor 的系统化 benchmark。它们提供定位参照，
但不等于不存在未检索到的近邻工作，因此当前只写“有差异化空间”，不写“首次”。

- PALOMA: https://arxiv.org/abs/2312.10523
- MixEval-X: https://arxiv.org/abs/2410.13754
- Agentic Benchmark Checklist: https://arxiv.org/abs/2507.02825
- NAS performance predictor study: https://arxiv.org/abs/2104.01177

## 正式复验与安全边界

- producer A/B 在不同 `PYTHONHASHSEED` 下逐字节一致；
- independent verifier A/B 逐字节一致，且不 import producer 实现；
- focused tests：`5 passed in 0.84s`；
- full tests：`1047 passed, 47 warnings in 82.62s`；
- exact-path syscall audit：forbidden open hits=`0`；
- prospective label/outcome/prediction/raw archive bytes：未打开；
- GPU/API/base-LLM update：`0/0/0`。

第一次远端启动因仓库 remote alias 不一致，在创建实验目录和读取数据前退出。正式 v1 已完成科学计算，但打包护栏把合法 task
名中的 `prediction` 子串误报为路径违规，故整次拒收并保留失败记录；v2 改为 exact allowed-path audit 后从头复跑并接纳。

关键文件 SHA-256：

- `trajectory.json`：`bbdb802711bd2f300725be156c5fd228a79fa0792f8d7317674a6a0bbb419f30`
- `independent_verification.json`：`8094e21acde877a67cdcc295c6decaaaf9e650c06fd55a91ed69026f877f9420`
- `headline_metrics.json`：`8d4041994f8998e5a04df0e2e18508ebf97915221303c14f62d9abb8d0e6b2b2`

`trajectory.json` 保存 1..339 的完整 prefix 轨迹、固定 milestones、Shapley/midpoint 分解、逐 drop 与逐 task 攻击；
`independent_verification.json` 是独立复算收据；其余文件保存 preflight、测试、路径审计与正式运行摘要。
