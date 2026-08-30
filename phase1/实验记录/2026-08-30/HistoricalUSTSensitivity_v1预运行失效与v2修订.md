# Historical UST predictor sensitivity：v1 预运行失效与 v2 修订

## 裁决

v1 formal **作废且没有产生科学结果**。它在 exact commit
`52951ebfe80d4fdb28b13ac970ceff524a00ed22` 上通过 focused `11 passed`，但完整测试运行到最近一次可见的
`40%` 时被主动终止；此时 `result_a.json`、`result_b.json`、两份 independent verification 均不存在。
远端保留根：

`/research/d7/spc/yzyang4/historical-ust-predictor-sensitivity/formal-52951eb-v1`

并写入 `INVALID_PROTOCOL_MISSING_NESTED_TASK_PARENT_ESTIMAND_BEFORE_OUTCOME_AGGREGATION`。因此不能引用 v1
的 accuracy、UST shift、ranking 或任何效果分类；这些值在 v2 冻结前没有被计算或读取。

## 为什么必须停

2026-08-25 已冻结的 generic predictor headline 是
`task_macro_parent_macro_pair_accuracy`：pair credit 先在 physical decision parent 内聚合，再在 task 内等权平均
parents，最后 tasks 等权。v1 只实现了：

1. task 内把所有 pair 合并后的 task-pair macro；
2. 不做外层 task 平衡的 global parent macro。

当不同 task 的 parent 数不相等时，两者都不等于既有 headline。若继续执行，再看到结果后补 nested headline，会构成
结果后指标扩张，也会让新的 UST 审计与已有 benchmark contract 错位。

## v2 的唯一科学修订

v2 在任何 historical UST outcome aggregate 前加入既有 nested headline：

1. 每个 `(task,parent)` 内按 UST effective-resistance weight 聚合 pair credit；
2. 每个 task 内等权平均 parent points；
3. 最后等权平均 28 个 task points。

uniform reference 使用相同 parent→task 层级，只把 parent 内的 UST edge weight 换成 uniform pair-row weight。
原 task-pair macro 与 global parent macro 全部保留为 mandatory sensitivity，不能 rescue headline。primary ranking、
paired UST−raw shift、champion−TF-IDF delta、task bootstrap 和 LOTO 均改以 nested headline 为 authority；冻结的
`static_gbm_task` champion 不重选。

新增 synthetic control 明确构造两个 task、parent 数为 2:1 的例子：global parent macro=`2/3`，nested
task-parent macro=`1/2`。另新增完整 931-pair×12-model 端到端合成回归；它在开发中发现并修复 verifier 先于
TF-IDF 重建就求 paired delta 的顺序错误。修复是先重建全部模型，再统一做配对验证，不改变任何统计量。

v2 focused 最终打印 `13 passed`；协议：

- `phase1/historical_ust_predictor_sensitivity_v2.json`；
- producer：`phase1/analyze_historical_ust_predictor_sensitivity.py`；
- independent verifier：`phase1/verify_historical_ust_predictor_sensitivity.py`；
- formal runner：`phase1/scripts/run_historical_ust_predictor_sensitivity_formal_20260830.sh`。

## 边界

这是已揭盲历史 931-pair 同池 sensitivity，不是 prospective confirmation。GPU、付费 API、model fit、agent-base
update=`0/0/0/0`；first-960、Target-300、Target-522 的 label/outcome/prediction value 均未读。UST 数学本身不作
novelty 主张。
