# Score-channel frozen cohort 结构支持审计（2026-08-18）

状态：`VERIFIED_OUTCOME_BLIND_COHORT_SUPPORT`。这是前瞻确认 cohort 的结构质量结果，不是 score-channel
科学效果结果，也不解除 Kaggle 数据门。

## 结果

冻结 `selection_a` 覆盖：

- 17 tasks、94 physical runs、158 selected parents、320 candidates；
- 320/320 candidate IDs 唯一，跨 parent duplicate membership=0；
- 最大候选任务 tgs-salt 为 48/320=`0.15`；
- 最大 parent 任务 tgs-salt 为 24/158=`0.1518987341772152`；
- 最大 run 任务 dogs-vs-cats 为 12/94=`0.1276595744680851`；
- candidate-mass HHI effective number=`102400/9296=11.015490533562822`；
- 154 个 parent 有 2 candidates，4 个 parent 有 3 candidates；30 个 run 选中 1 个 parent，64 个 run 选中
  2 个 parent。

这组数字的正面含义很窄但真实：将来的确认结果在结构上不会预先被一个任务或少量重复 candidate 主导。
这增强了 prospective replay 的外部可信度，但不能预测 effect 是否为正。

## 必须保留的限制

任务支持仍不均匀：cassava 与 google-quest 各只有 1 run/2 candidates，whale 只有 2 runs/4 candidates。
因此不声称 17 个任务都能独立稳定估计；正式分析继续以预注册的 run-cluster CI 为 primary、task-cluster CI
为 secondary，并保留 task LOTO。更不能把目前数据完整的 8 tasks / 74 candidates 当成 available-case
确认集，因为数据可得性不是随机缺失。

本审计没有打开 label vault、candidate code、replay manifest 或 replay outcome，且
`scientific_metrics_computed=[]`。它不能替代被冻结的 320-candidate replay；9 tasks / 246 candidates 的 Kaggle
规则阻塞仍须先解决。

## 复现与独立核验

- producer commit：`e0c5bcd6f9813afa7ced410d8f6b8d19da9edba5`；
- selected-parent SHA：`49e808747532034ae653e0fdb45a3144f5fe4545ae5b8d1755d79545d4c64b81`；
- producer 双跑逐字节一致，audit SHA：
  `82613e1cca4ce1f5b7370a8d5dc7e4d6ab3dbdbdb74ee137c9b9da728ec81b0a`；
- 不导入 producer 的 verifier 双跑逐字节一致，receipt SHA：
  `657b94eb51664aa8236622d1e932007b0de319f4b52802763c36bdf67d997528`；
- 聚焦测试连续两次通过，完整 suite：`384 passed in 32.19s`；
- 远端不可变证据根：
  `/research/d7/spc/yzyang4/score-channel-cohort-support-20260818-e0c5bcd`。
