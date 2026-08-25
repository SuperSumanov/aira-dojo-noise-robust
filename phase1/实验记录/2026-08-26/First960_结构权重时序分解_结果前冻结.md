# First-960 结构权重时序分解：结果前冻结

日期：2026-08-26

状态：`FROZEN_BEFORE_TRAJECTORY_OR_DECOMPOSITION_READ`

## 1. 已知事实与本次新增问题

在冻结本协议前已经知道：snapshot
`7cdaefcf2be7786442e1af1f4d0b4012edee708932f1fad31e174c0dcaf803a1` 的 first-240→first-339
比较中，run-weighted 任务集中度下降，而 endpoint/pair-weighted 集中度上升。因此，本分析不能把端点反转冒充成新的
预注册发现。

本次在读取中间 prefix、archive/task 删除诊断和机制分解结果之前，固定三个新增问题：

1. 反转是持续的累积轨迹，还是只由最后一个批次造成的端点现象？
2. pair 权重漂移主要来自任务 run 配比变化，还是每任务 decision-opportunity yield 的变化？
3. 结论能否在删除单个 archive / task 后保留；若不能，主张应收窄到哪个层级？

## 2. 输入与盲态边界

只允许读取以下结构文件，并逐项绑定 SHA-256：

- snapshot 的 `accumulator/provisional_first960_runs.jsonl`、`accumulator/summary.json` 与
  `intake_registry.jsonl`；
- registry 指向的每个 intake 的 `summary.json`、`source_provenance.json`、
  `eligible_blind_manifest.jsonl` 与 `eligible_structural_pairs.jsonl`。

禁止读取 `label_vault.jsonl`、outcome、grade、winner orientation、score registry、prediction values、checkpoint、
原始 tar/journal 字节。程序接口不得接受这些路径或 basename。GPU/API/base-LLM update 均为 0。

物理 run 按固定键 `(generation_started_at_utc, source_sha256, run_id)` 排序；当前 snapshot 固定为 339 runs，分析不改变
first-960 membership，也不参与后续语料摄取或停止决策。

## 3. 固定检查点与统计量

主要检查点固定为 `n = [120, 160, 200, 240, 260, 280, 300, 320, 339]`；此外输出 1..339 的完整轨迹供画图，
但不从完整轨迹中事后挑选 headline 时间点。first-240 是机制分解基线，first-339 是当前端点。

每个 prefix 固定输出：

- task 的 run / endpoint / decision-parent / canonical-pair counts 与 shares；
- 四种权重各自的 max share、HHI、inverse-HHI descriptive diversity、top-3 share、Shannon diversity 与 Gini；
- run→endpoint、run→parent、run→pair 的 total variation distance；
- 每任务 endpoints/run、decision parents/run、pairs/run，以及 pair-share / run-share amplification；
- pairs→parents→finite-decision-runs→tasks 的嵌套支持漏斗。

inverse-HHI 只解释为描述性 concentration-equivalent task count，不称为统计 ESS，不用于置信区间。raw pair count 不称为
独立样本量。

## 4. 固定机制分解

对 task `t`，pair count 恒等为 `P_t = R_t × Y_t`，其中 `R_t` 是 run 数，`Y_t=P_t/R_t` 是 observed
pair yield。令 `f(r,y)=normalize(r_t y_t)`，对 first-240→first-339 的 pair-HHI 和
`TV(run distribution, pair distribution)` 做两路径 Shapley 分解：

- run-composition contribution = 两种切换顺序下只更新 `r` 的平均增量；
- opportunity-yield contribution = 两种切换顺序下只更新 `y` 的平均增量；
- 两项必须在浮点容差内精确加总到观测总变化。

对 first-240 尚未出现、first-339 新出现的 task，固定令反事实 baseline yield 等于该 task 在 first-339 的 observed yield，
因此新任务进入的影响归入 run composition，而不会虚构一个零 yield。对 baseline 中 yield=0 的既有 task 保留真实零值。

同时输出 midpoint count decomposition，逐 task 验证：

`ΔP_t = ΔR_t × (Y0_t+Y1_t)/2 + ΔY_t × (R0_t+R1_t)/2`。

## 5. 固定稳健性攻击与主张等级

以下门只决定主张强度；失败不能被隐藏，也不能改阈值重跑：

1. **G1 时序持续性**：在 `[260, 280, 300, 320, 339]` 至少 4/5 个检查点，相对 first-240 同时满足
   run-HHI 不升、pair-HHI 上升。通过才可写“持续反转”；否则只能写“first-240→339 端点反转”。
2. **G2 单批次稳健性**：逐个删除 first-240 之后加入的一个 intake/drop 后，任一单 drop 对正向 pair-HHI 总增量的
   可归因比例不得达到 50%。通过才可写“不是单批次 artifact”。
3. **G3 单任务稳健性**：逐个删除一个 task，并同时从 baseline/current 删除它；至少 80% 的删除仍保留 run-HHI
   不升且 pair-HHI 上升，且删除当前 pair-dominant task 后也保留。通过才可写“跨任务普遍机制”；若失败，只能写
   “由特定高-yield task 驱动的 benchmark weighting case study”。
4. **G4 机制占比**：Shapley opportunity-yield contribution 至少解释 pair-HHI 正向增量的 50%，且对 run→pair TV
   正向增量也至少解释 50%。通过才可称“yield heterogeneity 是主要机制”；否则只报告分解，不作主因判断。

无论门是否通过，都不得推出 predictor accuracy、模型优越性或 search utility。最强允许结论是：真实搜索树产生的
decision opportunities 会内生改变 benchmark task mixture，因此 benchmark 必须显式固定抽样单位、estimand 与聚类层级。

## 6. 复验要求

- producer 与独立 verifier 不共享指标实现；
- 合成测试覆盖新任务进入、零 pair yield、多 sibling 组合、单 drop/task 删除、输入 hash 篡改和禁读 basename；
- 两次不同 `PYTHONHASHSEED` 运行必须逐字节一致；
- JSON + CSV 产物包含 snapshot、source commit、全部输入 SHA、精确命令、Python 版本及安全声明；
- 正式接纳前执行 focused/full tests、filename/content credential scan 与禁止路径访问审计。
