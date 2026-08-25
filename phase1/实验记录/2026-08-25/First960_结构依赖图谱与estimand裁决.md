# First-960 结构依赖图谱与 estimand 裁决

日期：2026-08-25

状态：`OUTCOME_BLIND_STRUCTURAL_DEPENDENCY_ATLAS_READY`

## 1. 问题与边界

当前 snapshot 有 339 个 eligible physical runs、10,196 endpoints 和 2,635 canonical sibling pairs。三者不能
互换：pair 数取决于每个 run 生成多少 scoreable endpoints、多少 parent 形成至少两个 children，以及每个 sibling group
产生多少组合。若只报告 pair-micro accuracy，任务权重可能成为搜索树形状的副产物。

本轮只读两个已经存在的 aggregate receipt：prospective accumulator summary 与 independent structural gate；不接受
label vault、grade/outcome、winner orientation、prediction values 或 score 路径，不计算 accuracy/effect/search utility。
由于主要占比在运行前已经可见，所有结果明确标为 post-hoc 描述性审计，不伪装成预注册效果检验。

## 2. 固定指标

对 first-240 与当前 chronological first-960 prefix 各计算：

- 任务按 runs / endpoints / canonical pairs 三种权重的 max share、HHI、inverse-HHI descriptive diversity、
  Shannon diversity、Gini 与 top-k shares；
- 同一任务集合上不同权重分布的 total variation 与 share amplification；
- 2,635 pairs → decision parents → physical runs → tasks 的嵌套支持漏斗；
- first-240→当前的 concentration 漂移。

`1 / HHI` 仅表示“若完全均匀，相当于多少个等权任务”的描述性多样性，不是考虑 ICC 后的统计 ESS，也不用于构造
置信区间。

## 3. 结果

从 first-240 到当前 339 runs，run-weighted 最大任务占比从 `0.10833333333333334` 降至
`0.09144542772861357`，inverse-HHI 多样性从 `17.86600496277915` 升至 `20.459497952643762`。按 run 看，覆盖
确实更均衡。

但 endpoint-weighted 最大任务占比从 `0.16937168568214686` 升至 `0.269909768536681`，inverse-HHI 从
`14.06749911273803` 降至 `9.503775422255263`；pair-weighted 最大任务占比从 `0.1714990746452807` 升至
`0.31233396584440226`，inverse-HHI 从 `12.042737393041941` 降至 `7.366637206731296`。当前 run→pair 的
task-distribution TV distance=`0.337082500713674`，pair 主导任务相对它自己的 run share 放大
`5.041962591488208` 倍。

结构漏斗显示 2,635 pairs 来自 2,593 decision-parent groups、334 finite-decision runs、30 tasks。pairs/parent=
`1.0161974546856922`，高于 one-pair-per-parent baseline 的部分只有 42 pairs（`0.015939278937381403`）；因此集中度
不是主要由多 sibling 的组合展开造成，而是任务/run 产生的 endpoints 与 decision parents 数量不同。每个 decision run
平均 `7.889221556886228` pairs，中位数 `4.0`，也表明 pair 数不能代替 run 数。

## 4. 评估裁决

未来闭合后的 predictor 表必须把 task-macro 设为主要点估计，并给 task-clustered bootstrap 与 LOTO；run-macro /
run-clustered 和 pair-micro 为次级敏感性视图。这样不是为了“让结果更好看”，而是因为当前 outcome-blind 结构已经证明
三种权重对应不同 estimand，甚至随语料累积朝相反方向变化。

这强化而非替代 25% pair-share accrual guard：first-960 时间序 membership 不变，producer 只能根据实际观察到的
canonical pair yield 调整未来任务分配，不能删除、重排既有 run，也不能把 657-pair 债务换算成固定 run 数。

## 5. 复验与失败链

源码 commit=`b8ea5f7e3d30ced33043167ecaffcb363bb4e320`。合成测试同时覆盖输入 hash/snapshot 绑定、非盲 receipt 拒绝、
指标篡改拒绝、producer-source 篡改拒绝及跨 `PYTHONHASHSEED` 逐字节一致性。fresh Linux focused/full=
`7 passed in 0.39s` / `1033 passed, 47 warnings in 71.41s`。producer 与完全独立实现各双跑，atlas SHA=
`1c3e5c34...b1a5`、independent SHA=`634c5784...150f`，A/B 均逐字节一致。

失败历史没有覆盖：

1. e19 v1 错误收集仓库根部历史脚本式 tests，producer 未运行；
2. e19 v2 未限制 BLAS，pytest 达约 2777% CPU 后只终止本轮已核验 PID；
3. e19 v3 全测试通过但 A/B 的四个 TV 浮点末位不同，结果拒收，并增加排序与 hash-seed 攻击测试；
4. b8ea v1 科学结果双跑一致，但 `key_metrics.json` 命中强制 filename guard，整根不接纳；
5. b8ea v2 完整重跑通过，filename/content/forbidden-open hits=`0/0/0`。

正式根 `/research/d7/spc/yzyang4/prepush-structural-atlas/b8ea5f7-v2`；`SHA256SUMS` 自身 SHA=
`17f41f52...d221d`。GPU/API/base-model updates=`0/0/0`。

## 6. 主张上限

成立：pair weighting 会显著重写 task mixture；run coverage 改善不保证 pair-weighted benchmark 变均衡；因此搜索树
decision benchmark 必须报告并固定抽样单位、estimand 与聚类推断。

不成立：critic 已准确、任一模型更优、pair 之间完全相关、inverse-HHI 等于统计 ESS、task-macro 必然产生更高效果、
或 learned critic 已改善真实搜索。
