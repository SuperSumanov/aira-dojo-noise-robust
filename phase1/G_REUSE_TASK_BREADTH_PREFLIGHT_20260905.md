# G-reuse 逐任务图增益集中度：结果前预检

日期：2026-09-05。状态：结果前冻结的历史 train 结构压力测试。
本项不修改冻结 v2、历史开发 v1、G0 12377、训练池或模型；不授权 GPU/API/model fit。

## 1. 问题、假设与停止线

既有结果表明，在 L 的 4095 个 endpoint 上加入 3058 条 G-reuse 无向比较，整体 incidence rank 增加 924。
本项只问：这 924 是否分布在足够多任务上，而不是由少数任务制造。任务名只在进程内用于分组，输出只含匿名数值行。

结果前固定三个同时成立的支持门：

1. 至少 20 个任务的 incidence-rank gain 严格大于 0；
2. 最大单任务 gain / 总 gain 不超过 0.20；
3. 删除任一任务后保留的总 gain 比例不低于 0.80。

三门都过只称 `HISTORICAL_G_REUSE_TASK_BREADTH_STRUCTURALLY_SUPPORTED`；任一失败则称
`HISTORICAL_G_REUSE_TASK_BREADTH_NOT_SUPPORTED`。不调整阈值、删任务、改分组或增加 secondary rescue。
这不是 accuracy、有效独立样本量、clean scaling、训练收益或搜索收益。

## 2. Population、输入与单一分析

- 固定输入与 `historical_label_reuse_support.py` 完全相同：历史 L train、旧 G train、92a9651 grouped Cards；
  SHA 分别为 `0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e`、
  `d9163bbcde70d8fe1f6f2ead9db266eca7ced932682cdaed9d3a9ece6fa43010`、
  `5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb`。
- L 必须为 4689 个唯一 train 无向 pair；G source 必须为 14206 个；沿用既有、不按本轮结果修改的资格投影，
  G candidate=9392、两端均在 L 的 G-reuse=3058。
- 每个任务分别用 L 的全部 endpoint 建无向图；加入该任务 G-reuse 后，gain 定义为
  `components(L) - components(L union G-reuse)`，等价于固定节点集上的 incidence-rank 增量。
- 输出全部 28 个任务的匿名行：L pairs、reuse pairs、endpoints、前后 components、rank gain；按数值 tuple 排序。
  不输出 task/card/run ID、方向、score、gap、预测或代码。

## 3. 混杂、无效解释与负控

- 加边按定义不会降低 incidence rank；本项的非平凡问题只有跨任务 breadth/concentration，不把“总增益为正”当发现。
- G pair 构造可能继承 score/gap 选择，且重复 endpoint 使比较相关；本项不证明图效应、因果性或独立标签数。
- 同 task 不等于同完整执行配置；143 config-mismatch、193 source-unresolved 及 experiment-closed 门继续存在。
- synthetic tests 必须覆盖零增益、单任务主导、恰好 20% 边界、方向/输入次序不变和 producer/verifier 一致。

## 4. 执行、资源与复现

- Python 标准库、单 CPU 核；producer A/B 各最多 180 秒，独立、不 import producer 的 verifier 各最多 180 秒；
  预计总墙钟 10--20 分钟（含实现/复验），正式子进程通常更短。
- 三输入读取前逐字节 SHA + credential-shape 扫描，读取后再验 SHA；只读 audit hook 拒绝网络、子进程、未列数据和写入。
  Python hook 不是 OS sandbox，grouped JSON 解析仍会把未投影字段载入内存，不能声称底层 label/code 字节未读。
- A/B JSON 必须逐字节相同；独立 verifier 自己做 set/BFS 和门判断并与 receipt 精确相等。
- 新独占 `/tmp` 根；逐子进程 rc/elapsed/stdout/stderr SHA、源码/input hash 和最终 manifest 全记录。
- seed/warmup 不适用；硬件仅 CPU，数学线程固定 1。GPU/API/model-fit/base-model update=`0/0/0/0`。
- first960、Target300、Target522、dev/test/vault 均不得打开；不物化训练数据或 checkpoint。

## 5. 后续裁决

通过只加强 G-reuse 的结构必要条件，不解除来源、config、experiment split、G0 计价和正式 GPU·时批准。
失败则保留 G-reuse 总体结构结果，但把“跨任务广泛支持”撤回；不以其它结构指标救回训练优先级。
