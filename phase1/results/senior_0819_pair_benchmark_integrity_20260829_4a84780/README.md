# Senior 0819 mixed pair benchmark：正式完整性证书

正式分类：`HISTORICAL_PAIR_BENCHMARK_INTEGRITY_GATE_FAIL`

这次审计按结果前冻结的 13 个 hard gates 运行。12 个通过；唯一失败的是
`all_decision_pairs_share_recorded_parent_and_physical_run`。因此，现有数据可作为 run/endpoint/pair
隔离且依赖广度充足的历史 mixed pair benchmark 使用，但**不能**称为“同一 recorded parent 下的 sibling decision
benchmark”，也不能用模型分数或子组结果救回最强分类。

## 正式结构结果

- decision 数据共 7,644 对：两端均为 declared parent 的直接 children 为 `1270/7644`，declared parent 与两端同
  physical run 为 `3389/7644`，同 task 为 `7644/7644`；
- mixed 中 2,563 条 decision-schema rows：对应计数为 `537/2563`、`1389/2563`、`2563/2563`；
- mixed train/test 的 physical-run、endpoint、unordered-pair overlap 均为 0；
- mixed test 与 decision test 的 canonical multiset 完全相等，均为 1,160 rows；test unordered duplicates=0，
  全 mixed conflicting orientations=0；
- mixed train 14,715 rows 全部属于声明的 source-train union；其中 490 rows 同时属于两个 source pools，故只能认证
  source support，不能反推实际 sampling origin；
- test breadth：1,160 pairs、38 tasks、173 physical runs、1,705 endpoints、724 connected components；
- 最大 task/run/component pair share 分别为 `21/232`、`43/1160`、`23/1160`，八个 breadth gates 全部通过。

此前 v2 的一次临时匿名诊断把字符串 parent ID 与 Node 对象直接比较，错误报告 direct-child=`0`；该临时数字在正式
producer 前即撤回。正式 producer 与不导入 producer 的独立 verifier 均按 parent ID 重算，并一致得到上面的
`1270/7644` 与 `537/2563`。这个修正不改变 frozen gate、population、threshold 或最终 gate-fail 分类。

## 复验与安全

- protocol/source commit：`8991d3048761ebe3463c5b90e223c86648d2dbaa4bbfce5e1894cd329dcfeb30` /
  `f534114e60658043c07f7a15d6440492caffc8ad`；
- producer A/B 逐字节一致，SHA-256=`90e220ace013e8919a413b8e8a95524bfa374cc390c9bd0241d57b6ac9bb00cb`；
- 独立 verifier A/B 逐字节一致，SHA-256=`d01268f2ff5774ab16ed2a67dccb6fe31bae82f5ee4800ec08eddeca22dc5b49`；
- focused/full tests=`7/1463 passed`，full 有 47 个既有 deprecation warnings；
- forbidden file opens=0、network calls=0；remote formal manifest=
  `f5483cf2a2d7097fcd34342d93e5047bfaaec3498e545fe59e4e0d2487a47b17`；
- first-960/Target-300 前瞻值、raw senior archives、test accuracy、scaling 与 search utility 均未读取或计算；
- GPU/API/model-fit/base-update=`0/0/0/0`。

`formal_summary.json` 是匿名 aggregate 主结果；`verification.json` 是独立核验回执。该证书不把周期评估过的历史 test
升级为 untouched final test，也不证明 critic scaling 或端到端 search utility。
