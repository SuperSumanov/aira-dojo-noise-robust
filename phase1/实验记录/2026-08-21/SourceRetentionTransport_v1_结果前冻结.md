# Source Retention Transport v1：结果前冻结

日期：2026-08-21。状态：`PREREGISTERED_NOT_RUN`。

## 问题与边界

现有审计已确认：v11 的 3,252 个发布 parent 中有 870 个 source-incomplete；996 个可恢复缺失
identity 中的 902 个能找回 journal status，893 个是 execution error。这个结果说明完整 case 分析受到执行删失，
但尚未回答删失强度是否只是有限样本噪声，还是能在互不重叠的 physical runs 间按任务复现。

本审计只检验一个窄问题：**train 角色中估计的 task-level source-retention profile，能否迁移到 frozen 角色。**
它不训练 predictor，不读取候选代码、分数大小、better/worse、gap、self-report、first-960、prospective outcome
或任何模型预测；GPU=0、API=0、base-LLM update=0。

## 冻结输入与统计单位

- 唯一科学输入：既有 raw-choice-set completeness 正式产物 `per_parent.csv`；
- 输入 SHA-256 固定为
  `75c02200d1f9b8d87614762a9f2b71ba3c678d598ff28bc237c8a46a4bc36d03`；
- 预期 3,252 行，role counts 固定为 train/frozen/extension=`2293/845/114`；
- 分析单位先是 `(role, task, parent)`，headline 再对 task 等权；
- 主指标固定为 parent-level `finite_source_retention`，即 retained finite children / source-declared children。

所有行必须通过既有 source-size、context、endpoint 与 parent 结构约束；结构不一致时状态为 `INVALID_INPUT`，
不得删行追救。extension 只做描述，不参与 headline。

## 资格门、headline 与推断

共同任务资格在结果前固定为：train parents≥30 且 frozen parents≥15；至少 10 个共同任务，否则
`INSUFFICIENT_TASK_SUPPORT`。

在这些任务上：

1. 分别计算 train/frozen 的 task-equal mean retention；
2. headline 为两组 task profile 的 Spearman 相关；
3. permutation test 固定 100,000 次、seed=`20260821`，对 frozen task profile 整体置换，双侧
   `p=(extreme+1)/(B+1)`；
4. task-paired bootstrap 固定 20,000 次、seed=`20260822`，报告 percentile 95% CI；有效 bootstrap 比例必须
   ≥0.90；
5. 逐任务 leave-one-out 重算 Spearman，报告最小值；
6. 训练 profile 排序后固定 bottom/top tertile，在 frozen 上报告 task-equal retention 差，只作解释，不作解锁门；
7. `raw_source_retention` 与 `parent_card_present=true` 仅作预指定敏感性，不替换 headline。

## 冻结裁决

只有以下全部成立，才允许状态 `VERIFIED_TASK_CONDITIONED_SOURCE_RETENTION_TRANSPORT`：

- eligible common tasks≥10；
- headline Spearman rho≥0.50；
- permutation p<0.05；
- bootstrap 95% CI 下界>0，且有效比例≥0.90；
- 所有 leave-one-task-out rho>0。

否则统一为 `NO_VERIFIED_SOURCE_RETENTION_TRANSPORT`，不改支持阈值、metric、角色、task 子集或推断单位重跑。

通过时允许的主张仅为：在当前数据生成与发布管线中，source retention 具有可跨 disjoint-run release roles
复现的 task-conditioned structure，因此 benchmark 必须分任务报告删失/覆盖。仍禁止 missing-at-random、
因果 task effect、完整 choice set、可恢复数值 outcome、predictor/search utility、跨 agent 迁移和 first/only。

## 复现与独立验证

正式矩阵固定为 producer×2 + 不 import producer 的 verifier×2；两次同类输出必须逐字节一致。输出只含
task support/retention、相关统计、固定门、输入/协议哈希和 scope false flags。正式运行前跑 focused tests，
封存后跑全套 `phase1/tests`；所有产物与 staged/outgoing diff 均做文件名和高置信秘密扫描。
