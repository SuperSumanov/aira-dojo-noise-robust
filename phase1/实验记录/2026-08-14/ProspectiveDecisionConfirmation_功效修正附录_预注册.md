# Prospective decision confirmation：结构功效修正附录

日期：2026-08-14。协议：`prospective_decision_v1_power_addendum`。本文是
`ProspectiveDecisionConfirmation_预注册.md` 的 **outcome 前、append-only** 附录，不删除或改写原协议的
first-240 结果。写本文时没有读取任何 activation 后 run 的 label/outcome，也没有读取论文 frozen pairs。

## 1. 触发依据仅为 pre-activation 结构，不含 outcome

学长 0812 drop 在隔离提取、脱敏与 source-journal provenance 修正后，被封成
`temporal_blind_0812_v1`：805 endpoints、57 个真实 source journals/runs、9 tasks、103 个有至少两个可标注
child 的 sibling parents，因此只有 103 个 structural sibling pairs。dominant pair-task share 为
0.20388349514563106。label vault 已单独封存；本附录写入前 `labels_read_for_metrics=false`、
`label_values_printed=false`。

结构 seal：

- blind views SHA-256：`c0d6d207f39ea8d113a90c73e75c982ca9e77356d061ac8bffd8caa53e201dc9`；
- label vault SHA-256：`c58af056ba70ed5268b4f37fd8557a0b00728def19a881d55c458820afa4ee4a`；
- sibling structure SHA-256：`2c67ab3dae40c34b3eea233ae049afa2462d88e689b737b21421a7a1862c993b`；
- seal time：`2026-08-13T22:38:11.912275Z`。

结构产率为 1.8070175438596492 pairs/run。若未来生产机制相近，first-240 只期望约
433.6842105263158 个 structural pairs，明显低于原支持门的 1,500；约需 830.0970873786408 runs 才达到
1,500。这个判断完全不使用 pair label、scorer prediction 或 grade gap。

## 2. 两个固定报告点

1. **Cohort A：原始 first-240。** 保留原协议，固定报告其结构支持和所有原定指标；但不在 240 时查看 outcome，
   不据其结果停止、改模型、改阈值或选任务。如果原支持门失败，状态只能是
   `ORIGINAL_FIRST240_INSUFFICIENT_SUPPORT`，不能降低 1,500-pair / 15-task 门。
2. **Cohort B：功效修正 first-960。** 现在固定为唯一允许作确认性裁决的 accrual cohort。仍按
   `(generation_started_at_utc, source_sha256, physical_run_id)` 取 activation 后前 960 个合格 run；前 240
   是其前缀，不是独立样本。预计结构 pair 数为 1734.7368421052631，但该期望不替代最终支持审计。

禁止在 240、480、720 等中间点读取 outcome。只有 first-960 identity 清单冻结后才能一次性解封 label 并计算
结果；若生产在 960 前停止，记 `CONFIRMATORY_COHORT_INCOMPLETE`，不按已收样本改停止点。

## 3. 不变项

- active scorer、bundle SHA、代码 view、static/TF-IDF 参数、随机 seed 与激活时刻全部不变；
- primary interaction、task bootstrap、逐任务方向门与 actual-utility 双门全部不变；
- first-960 仍要求至少 1,500 finite non-tie sibling pairs、至少 150 finite-decision runs、至少 15 个支持任务、
  dominant task share `<=0.25`；任何一项不满足即 `INSUFFICIENT_SUPPORT`；
- 0812 是 pre-activation analyst-blind holdout，明确不计入 first-960；667 个 v11 run denylist 继续生效；
- 不微调底座 LLM，不调用 LLM/API，不打开论文 frozen pairs。

## 4. 对生产排程的可审计要求

为了让 15-task 门有可能通过，后续生产必须在 outcome 未知时预先排程至少 15 个任务，并避免任一任务超过预计
run 数的 25%。这是支持条件，不授权按 critic 表现挑任务。每个 run 必须在 flatten 前保存 source journal 身份、
generation start、source archive SHA 和 physical run ID；仅靠“有标签卡的 step 是否回落”不得再当 source truth。

本附录只修正由新生产机制导致的样本量错配，不宣称结果更可能为正；first-960 的确认门仍可能因任务异质性或
critic 无真实 utility 而失败。

