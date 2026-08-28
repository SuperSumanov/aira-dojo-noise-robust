# Tree linearization weight：887 结果前预注册

日期：2026-08-28。状态：`OUTCOME_BLIND_PROTOCOL_FROZEN_BEFORE_LINEARIZATION_AGGREGATES`。

## 1. 动机与唯一问题

mle-traj 的 canonical agent tables 把 13 个 MLEvolve physical runs 线性化成 189 条 root-to-leaf branches，同时其
gated raw layout 可能保留更多 tree 信息。因此本实验不对它的 raw release 作结论，只在我方固定 snapshot 上回答一个
可识别问题：**若把同一 observed search fragment 从“一条物理 edge 一次”改写成“枚举所有 root-to-leaf paths”，
共享前缀会被重复多少次，task/run 的 empirical weights 会移动多少？**

这不是 predictor 效果实验，也不是一般图论创新；价值只在把“tree linearization 改变 benchmark estimand”落到真实
MLE-agent 语料的确定性、可复建量化，并为 closure 后的 sibling/transition sensitivity 提供结构账本。

## 2. 固定人口与表示

- snapshot 固定为 `887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697`；已知结构人口为
  435 provisional runs、11,906 eligible endpoints、34 tasks，closure=false；
- 只读 append-only intake 的 `eligible_blind_manifest.jsonl`、registry、provisional run 与 accumulator summary；
- observed edge 仅在 child 与其声明 parent 都出现在固定 blind population 时成立；parent 缺失的 endpoint 是 fragment
  root，不把缺失 parent 补回，也不冒充 complete source tree；
- unique-edge 表示中每条 observed edge 权重为 1；branch-linearized 表示枚举每个 fragment root 到 fragment leaf 的
  path，因此一条 edge 的 multiplicity 精确等于其 descendant leaves 数；singleton fragments 不产生 edge；
- 不按 task、run、深度、operator、分支数或结果选择子集。

## 3. 结果前固定门与分类

完整性门：LATEST/hash/schema/run-card 对齐/同 run-task edge/acyclic 全过；parent-present endpoint fraction≥0.75；
observed unique edges≥1,500；有 edge 的 runs≥150、tasks≥15。任一失败直接
`LINEARIZATION_AUDIT_GATE_FAIL`。

材料阈值在任何新 aggregate 前固定：duplicate branch-occurrence fraction≥0.25；task TV≥0.05；run TV≥0.10。
ordered classification 为：

1. 三门全过：`MULTI_AXIS_MATERIAL_LINEARIZATION_REWEIGHTING`；
2. duplicate+run TV 过、task TV 未过：`RUN_LEVEL_MATERIAL_LINEARIZATION_REWEIGHTING`；
3. 有重复但未过上述材料门：`LINEARIZATION_DUPLICATION_WITHOUT_MATERIAL_WEIGHT_SHIFT`；
4. 重复恰为 0：`NO_OBSERVED_LINEARIZATION_DUPLICATION`；
5. 任一完整性/支持门失败：`LINEARIZATION_AUDIT_GATE_FAIL`。

TV=0.10 表示至少 10% 概率质量必须在 clusters 间移动；task 轴用更保守的 0.05 是因为只有 34 个任务且 run 内树形态
本就可能先在 run 轴显现。25% duplicate fraction 表示线性化 edge rows 至少四分之一不是新的物理 edge。三个阈值
只能按上述 ordered rule 使用，不能互相 rescue。

## 4. 必须输出与解释边界

输出只含 aggregate：fragment/root/leaf/edge 数、multiplicity 分布、重复质量、task/run concentration 与 TV、匿名化
per-task run-TV 分布、depth weighting diagnostic、全部 gate 和 classification。不得输出 task/run/card/parent/code 值。

即使最高档通过，也只允许称：在该固定、尚未 closure 的 outcome-blind MLE snapshot 上，root-to-leaf linearization
按预声明阈值改变了 empirical weights。禁止声称 mle-traj raw release 没有 tree、完整 source tree/choice set、predictor
accuracy、search utility、因果机制、一般 linearization 理论首创或 first-960 最终结论。

## 5. 独立性与资源

producer A/B 必须逐字节一致；verifier A/B 不 import producer，独立重建图、leaf descendants、multiplicity、全部
concentration/TV/gates/classification 后逐字节一致。synthetic tests 至少覆盖 chain、fork、shared-prefix、跨 run/task、
cycle、hash/schema tamper 与门槛边界。CPU-only；prospective label/grade/outcome/prediction、raw senior archive、
GPU/API/model-fit/base-update=`false/false/false/false/0/0/0/0`。

机器协议：`phase1/prospective_tree_linearization_weight_audit_v1.json`；正式 aggregate 前机器打印的 SHA-256 为
`95b49fd50b75dd16fd9eefbb34557da35daa52fcecc35fce45ac89948a697feb`。生产器、非导入式独立复算器与相邻回归的
本地结果为 `19 passed`；正式远端仍须重新执行 focused/full tests、A/B 字节一致与独立复验，不能用该本地结果替代。
